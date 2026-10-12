import asyncio
import json
import io
import wave
import sys
import websockets
import edge_tts
import miniaudio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


WS_URL = "ws://localhost:8000/api/ws/voice/6ac9f88a-e6ea-4f2d-8dcb-63ff81d1eab9"


async def generate_test_speech_pcm(text: str) -> bytes:
    """Tạo audio test tiếng Việt giả lập giọng người nói gửi từ mic ESP32 (16kHz 16-bit Mono PCM)."""
    comm = edge_tts.Communicate(text, "vi-VN-NamMinhNeural")
    mp3_buf = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            mp3_buf.extend(chunk["data"])
    
    decoded = miniaudio.decode(bytes(mp3_buf), nchannels=1, sample_rate=16000)
    return bytes(decoded.samples)


async def main():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as ws:
        # 1. Receive welcome message
        welcome = await ws.recv()
        print("<- Server:", welcome)

        # 2. Generate simulated speech from ESP32 mic
        question = "Hàm số lượng giác là gì?"
        print(f"\n[Mô phỏng ESP32] Người dùng bấm nút và hỏi: '{question}'")
        pcm_data = await generate_test_speech_pcm(question)
        print(f"Tổng dung lượng PCM 16kHz giả lập: {len(pcm_data)} bytes")

        # 3. Send START event
        await ws.send(json.dumps({"event": "start"}))

        # 4. Stream audio in chunks (simulate ESP32 I2S DMA streaming)
        chunk_size = 1024
        for i in range(0, len(pcm_data), chunk_size):
            await ws.send(pcm_data[i:i + chunk_size])
            await asyncio.sleep(0.01)

        # 5. Send STOP event (User releases button)
        print("[Mô phỏng ESP32] Nhả nút -> Gửi event STOP...")
        await ws.send(json.dumps({"event": "stop"}))

        # 6. Listen for response
        audio_received = bytearray()
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                print(f"<- [Status]: {data.get('status') or data.get('event')}: {data.get('message') or data.get('text') or ''}")
                if data.get("event") == "audio_end":
                    print(f"\n-> Đã nhận đủ {len(audio_received)} bytes audio PCM trả lời từ server!")
                    break
            elif isinstance(msg, bytes):
                audio_received.extend(msg)


if __name__ == "__main__":
    asyncio.run(main())
