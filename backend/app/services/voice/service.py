import io
import wave
import logging
import asyncio
import re
from typing import Optional, List, AsyncGenerator
import edge_tts
import miniaudio
from google.genai import types

from app.config import settings
from app.services.gemini.client import gemini_service

logger = logging.getLogger(__name__)


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Đóng gói dữ liệu PCM thô thành file WAV hoàn chỉnh trong bộ nhớ RAM."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def clean_text_for_tts(text: str) -> str:
    """Lọc bỏ ký tự markdown, LaTeX, trích dẫn [Trang X] và ký tự thừa trước khi đọc."""
    # Bỏ citations: [Trang 24]
    t = re.sub(r'\[Trang\s+\d+\]', '', text, flags=re.IGNORECASE)
    t = re.sub(r'\[Page\s+\d+\]', '', text, flags=re.IGNORECASE)
    # Bỏ Markdown symbols: **, *, #, `, $, $$
    t = t.replace('**', '').replace('__', '').replace('#', '').replace('`', '')
    t = re.sub(r'\$\$?', '', t)
    # Bỏ bullets, số thứ tự ở đầu dòng (ví dụ: * , - , 1. )
    t = re.sub(r'^\s*[\d\.\-\*\+•]+\s*', '', t, flags=re.MULTILINE)
    # Gộp khoảng trắng thừa
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def split_into_sentences(text: str) -> List[str]:
    """Tách văn bản thành các câu tự nhiên có độ dài hợp lý để stream TTS ngay lập tức."""
    raw = re.split(r'(?<=[.?!;\n])\s+', text.strip())
    sentences = []
    buffer = ""
    for s in raw:
        s = s.strip()
        if not s:
            continue
        buffer = (buffer + " " + s).strip() if buffer else s
        # Nếu câu đã có dấu ngắt và đạt độ dài tối thiểu (>= 20 ký tự) thì xuất ra
        if len(buffer) >= 20:
            sentences.append(buffer)
            buffer = ""
    if buffer:
        sentences.append(buffer)
    return sentences


class VoiceService:
    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or getattr(settings, "TTS_VOICE", "vi-VN-HoaiMyNeural")

    async def transcribe_audio(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Dùng Gemini Multimodal Audio để nhận diện giọng nói tiếng Việt từ luồng PCM của ESP32.
        """
        if not pcm_bytes or len(pcm_bytes) < 3200:  # Ít hơn 0.1s
            return ""

        wav_bytes = pcm_to_wav_bytes(pcm_bytes, sample_rate=sample_rate, channels=1, sampwidth=2)

        prompt = (
            "Chuyển đổi file âm thanh này thành văn bản tiếng Việt. "
            "Chỉ trả về nội dung câu nói chính xác của người dùng mà không kèm bất kỳ giải thích, chào hỏi hay dấu ngoặc nào."
        )

        for model_name in gemini_service._get_model_candidates():
            try:
                client, use_new_sdk = gemini_service._get_client_and_sdk()
                if use_new_sdk:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                            prompt
                        ]
                    )
                    text = response.text.strip() if response.text else ""
                    if text:
                        return text
            except Exception as e:
                logger.warning(f"Voice STT retry with model '{model_name}' failed: {e}")

        return ""

    def _synthesize_gtts(self, text: str, target_sample_rate: int = 44100) -> Optional[bytes]:
        """Tổng hợp âm thanh siêu tốc bằng Google TTS (khoảng 0.3s - 0.5s/câu)."""
        try:
            from gtts import gTTS
            tts = gTTS(text, lang='vi')
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            mp3_bytes = buf.getvalue()
            if not mp3_bytes:
                return None
            decoded = miniaudio.decode(mp3_bytes, nchannels=1, sample_rate=target_sample_rate)
            return bytes(decoded.samples)
        except Exception as e:
            logger.warning(f"gTTS error for text '{text[:25]}...': {e}")
            return None

    async def _synthesize_edge_tts(self, text: str, target_sample_rate: int = 44100) -> Optional[bytes]:
        """Tổng hợp âm thanh truyền cảm bằng Edge-TTS (Microsoft Neural Voice)."""
        try:
            rate = getattr(settings, "TTS_RATE", "+10%")
            communicate = edge_tts.Communicate(text, self.voice, rate=rate)
            mp3_buf = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buf.extend(chunk["data"])
            if not mp3_buf:
                return None
            decoded = miniaudio.decode(bytes(mp3_buf), nchannels=1, sample_rate=target_sample_rate)
            return bytes(decoded.samples)
        except Exception as e:
            logger.warning(f"Edge-TTS error for text '{text[:25]}...': {e}")
            return None

    async def synthesize_sentence_pcm(self, sentence: str, target_sample_rate: int = 44100) -> Optional[bytes]:
        """
        Tổng hợp một câu đơn lẻ thành dữ liệu PCM 16-bit Mono.
        Tự động ưu tiên Edge-TTS, nếu quá 2.5s hoặc lỗi thì fallback ngay sang gTTS siêu tốc.
        """
        engine = getattr(settings, "TTS_ENGINE", "edge").lower()
        pcm = None

        if engine == "edge":
            try:
                # Giới hạn 2.5s: Nếu Edge-TTS bị nghẽn mạng từ Microsoft thì fallback ngay lập tức
                pcm = await asyncio.wait_for(
                    self._synthesize_edge_tts(sentence, target_sample_rate),
                    timeout=2.5
                )
            except Exception as e:
                logger.info(f"[Voice TTS] Edge-TTS không phản hồi kịp ({e}), tự động chuyển sang Google TTS...")
                pcm = None

        if not pcm:
            pcm = await asyncio.to_thread(self._synthesize_gtts, sentence, target_sample_rate)

        return pcm

    async def stream_speech_pcm(
        self,
        text: str,
        target_sample_rate: int = 44100,
        chunk_size: int = 2048
    ) -> AsyncGenerator[bytes, None]:
        """
        STREAMING AUDIO THEO TỪNG CÂU VỀ ESP32 ĐỂ PHÁT LUÔN RA LOA.
        Ngay khi câu đầu tiên sẵn sàng (chỉ mất ~0.4s - 1.2s), dữ liệu PCM sẽ được
        yield ngay lập tức cho WebSocket. Trong khi loa đang phát câu trước,
        câu sau đã được tổng hợp xong trong nền, đảm bảo không có độ trễ gián đoạn.
        """
        clean_text = clean_text_for_tts(text)
        if not clean_text:
            return

        sentences = split_into_sentences(clean_text)
        if not sentences:
            sentences = [clean_text]

        logger.info(f"[Voice TTS] Bắt đầu stream {len(sentences)} câu âm thanh tới ESP32...")

        for idx, sentence in enumerate(sentences, 1):
            t0 = asyncio.get_event_loop().time()
            pcm = await self.synthesize_sentence_pcm(sentence, target_sample_rate)
            if not pcm:
                continue

            dur = len(pcm) / (target_sample_rate * 2)
            gen_time = asyncio.get_event_loop().time() - t0
            logger.info(f"[Voice TTS] Câu {idx}/{len(sentences)} sẵn sàng trong {gen_time:.2f}s (thời lượng phát: {dur:.1f}s)")

            # Yield từng khối nhỏ theo luồng với flow-control nhịp nhàng
            for offset in range(0, len(pcm), chunk_size):
                yield pcm[offset:offset + chunk_size]
                # Sleep 12ms để phù hợp tốc độ tiêu thụ DMA của loa ESP32 (không làm tràn RAM)
                await asyncio.sleep(0.012)

    async def synthesize_speech_pcm(self, text: str, target_sample_rate: int = 44100) -> bytes:
        """Hàm dự phòng gom toàn bộ văn bản thành 1 buffer PCM duy nhất nếu cần."""
        full_pcm = bytearray()
        async for chunk in self.stream_speech_pcm(text, target_sample_rate=target_sample_rate):
            full_pcm.extend(chunk)
        return bytes(full_pcm)


voice_service = VoiceService()
