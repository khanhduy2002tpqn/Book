import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant specialized in answering questions about uploaded documents.

Answer the user's question using only the provided document context.

Rules:
1. Do not invent information.
2. Do not use outside knowledge unless explicitly requested.
3. If the answer cannot be found in the document context, clearly say that the information could not be found in the document (ví dụ: "Không tìm thấy thông tin phù hợp trong tài liệu.").
4. Cite the page number whenever possible in the format [Trang X] or [Page X].
5. If multiple parts of the document support the answer, cite all relevant pages.
6. Distinguish between information explicitly stated in the document and reasonable interpretation.
7. Answer in the same language as the user's question.
8. For Vietnamese questions, answer in natural Vietnamese.
9. Keep answers clear and structured with markdown.
10. Mathematical formulas and symbols: Always format ALL mathematical formulas, variables, and expressions using standard LaTeX syntax. Use single dollar signs `$ ... $` for inline math (ví dụ: `$x$`, `$\\sin x$`, `$y = \\tan x$`, `$\\mathbb{R} \\setminus \\{\\frac{\\pi}{2} + k\\pi \\mid k \\in \\mathbb{Z}\\}$`), and double dollar signs `$$ ... $$` for block display equations. Ensure LaTeX syntax is clean and standard for KaTeX rendering.
"""

VOICE_SYSTEM_PROMPT = """Bạn là trợ lý học tập AI giao tiếp bằng giọng nói qua loa thông minh của học sinh.
Nhiệm vụ: Trả lời câu hỏi của học sinh dựa trên tài liệu sách giáo khoa được cung cấp.
Quy tắc BẮT BUỘC dành cho giao tiếp bằng GIỌNG NÓI:
1. Trả lời trực tiếp, cô đọng, súc tích (chỉ từ 2 đến 3 câu văn ngắn, tối đa khoảng 40 đến 60 từ).
2. Đi thẳng vào bản chất câu trả lời. TUYỆT ĐỐI KHÔNG mở đầu bằng các câu thừa như "Dựa trên tài liệu được cung cấp...", "Theo sách giáo khoa...", v.v.
3. TUYỆT ĐỐI KHÔNG dùng ký tự Markdown, không dùng gạch đầu dòng, dấu hoa thị (**), số trang ([Trang 41]), bảng biểu hay công thức toán LaTeX phức tạp.
4. Diễn đạt bằng câu văn trọn vẹn, rành mạch, dễ hiểu khi đọc thành tiếng qua loa.
5. Nếu không có thông tin trong tài liệu, trả lời ngắn gọn: "Thông tin này chưa có trong sách giáo khoa."
"""


class GeminiService:
    def __init__(self):
        self._local = threading.local()

    def _get_client_and_sdk(self):
        if hasattr(self._local, "client") and self._local.client is not None:
            return self._local.client, self._local.use_new_sdk

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("GEMINI_API_KEY is not configured in .env!")
            raise ValueError("GEMINI_API_KEY chưa được cấu hình. Vui lòng thiết lập GEMINI_API_KEY trong file .env.")

        # Try modern google-genai SDK first
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            self._local.client = client
            self._local.use_new_sdk = True
            return client, True
        except Exception:
            pass

        # Fallback to legacy google.generativeai
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            self._local.client = legacy_genai
            self._local.use_new_sdk = False
            return legacy_genai, False
        except Exception as e:
            raise RuntimeError(f"Could not initialize any Gemini SDK: {e}")

    def _get_model_candidates(self) -> List[str]:
        candidates = [
            settings.GEMINI_MODEL,
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]
        seen = set()
        result = []
        for c in candidates:
            clean = c.replace("models/", "").strip()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result

    def generate_chat_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate grounded answer with citations using Gemini API.
        """
        if not context_chunks:
            return "Không tìm thấy thông tin phù hợp trong tài liệu."

        # Build context string with explicit page and chapter labels
        context_blocks = []
        for idx, chunk in enumerate(context_chunks, 1):
            page = chunk.get("page", "?")
            chapter = chunk.get("chapter", "")
            chapter_info = f" (Chương: {chapter})" if chapter else ""
            text = chunk.get("text", "").strip()
            context_blocks.append(f"--- Đoạn {idx} [Trang {page}{chapter_info}] ---\n{text}")

        context_str = "\n\n".join(context_blocks)

        prompt = f"""Dưới đây là các đoạn trích từ tài liệu liên quan đến câu hỏi:

=== NỘI DUNG TÀI LIỆU ===
{context_str}
=========================

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}

Hãy trả lời câu hỏi dựa trên các đoạn trích trên và trích dẫn rõ số trang [Trang ...] cho từng ý."""

        last_error = None
        for model_name in self._get_model_candidates():
            try:
                client, use_new_sdk = self._get_client_and_sdk()
                if use_new_sdk:
                    from google.genai import types
                    contents = []
                    if conversation_history:
                        for msg in conversation_history[-6:]:
                            role = "user" if msg["role"] == "user" else "model"
                            contents.append(types.Content(
                                role=role,
                                parts=[types.Part.from_text(text=msg["content"])]
                            ))
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)]
                    ))

                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT
                        )
                    )
                    return response.text.strip()
                else:
                    legacy_genai = client
                    model = legacy_genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=SYSTEM_PROMPT
                    )
                    if conversation_history:
                        history_formatted = []
                        for msg in conversation_history[-6:]:
                            role = "user" if msg["role"] == "user" else "model"
                            history_formatted.append({"role": role, "parts": [msg["content"]]})
                        chat = model.start_chat(history=history_formatted)
                        response = chat.send_message(prompt)
                    else:
                        response = model.generate_content(prompt)
                    return response.text.strip()
            except Exception as e:
                err_str = str(e)
                last_error = e
                if "closed" in err_str.lower():
                    self._local.client = None
                if "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower():
                    logger.warning(f"Model '{model_name}' not available, trying next model candidate...")
                    continue
                else:
                    logger.error(f"Gemini API error with model '{model_name}': {e}")
                    raise RuntimeError(f"Lỗi khi gọi Gemini API: {str(e)}")

        raise RuntimeError(f"Không thể kết nối đến model Gemini nào khả dụng: {str(last_error)}")

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        General prompt runner for summaries, questions, flashcards, etc.
        """
        sys_inst = system_instruction or SYSTEM_PROMPT
        last_error = None

        for model_name in self._get_model_candidates():
            try:
                client, use_new_sdk = self._get_client_and_sdk()
                if use_new_sdk:
                    from google.genai import types
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_inst
                        )
                    )
                    return response.text.strip()
                else:
                    legacy_genai = client
                    model = legacy_genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=sys_inst
                    )
                    response = model.generate_content(prompt)
                    return response.text.strip()
            except Exception as e:
                err_str = str(e)
                last_error = e
                if "closed" in err_str.lower():
                    self._local.client = None
                if "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower():
                    logger.warning(f"Model '{model_name}' not available, trying next model candidate...")
                    continue
                else:
                    logger.error(f"Gemini text generation error with model '{model_name}': {e}")
                    raise RuntimeError(f"Lỗi Gemini: {str(e)}")

        raise RuntimeError(f"Không thể kết nối đến model Gemini nào khả dụng: {str(last_error)}")

    def generate_voice_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a concise, spoken answer specifically for Voice Assistant (ESP32 speaker).
        Under 60 words, direct, no Markdown, no citations, so TTS can synthesize in ~1s.
        """
        if not context_chunks:
            return "Thông tin này chưa được tìm thấy trong sách giáo khoa."

        context_texts = [c.get("text", "").strip() for c in context_chunks if c.get("text")]
        context_str = "\n\n".join(context_texts[:3])

        prompt = f"""Dưới đây là nội dung trích xuất từ sách giáo khoa:
===
{context_str}
===

Câu hỏi của học sinh: {query}

Hãy trả lời câu hỏi trên thật ngắn gọn, súc tích (khoảng 2 đến 3 câu văn) bằng ngôn từ tự nhiên để đọc ra loa cho học sinh nghe."""

        try:
            return self.generate_text(prompt, system_instruction=VOICE_SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"Error in generate_voice_answer: {e}")
            return "Đã xảy ra lỗi khi tạo câu trả lời giọng nói."

    def extract_text_from_image(self, image_bytes: bytes) -> str:
        """
        Multimodal Vision OCR: Extract text from image page using Gemini.
        Thread-safe via thread-local client.
        """
        ocr_prompt = (
            "Trích xuất chính xác toàn bộ văn bản (text) có trong trang ảnh này "
            "(bao gồm tiếng Việt và tiếng Anh). Giữ nguyên đầy đủ nội dung, dấu câu và bố cục. "
            "Chỉ trả về nội dung văn bản trích xuất được mà không kèm giải thích hoặc chào hỏi."
        )

        for model_name in self._get_model_candidates():
            for retry in range(2):
                try:
                    client, use_new_sdk = self._get_client_and_sdk()
                    if use_new_sdk:
                        from google.genai import types
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                ocr_prompt,
                            ],
                        )
                        return response.text.strip() if response.text else ""
                    else:
                        legacy_genai = client
                        model = legacy_genai.GenerativeModel(model_name)
                        response = model.generate_content([
                            {"mime_type": "image/png", "data": image_bytes},
                            ocr_prompt,
                        ])
                        return response.text.strip() if response.text else ""
                except Exception as e:
                    err_str = str(e)
                    if "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower():
                        break
                    if "closed" in err_str.lower():
                        self._local.client = None
                    time.sleep(1)
                    if retry == 1:
                        logger.warning(f"Gemini Vision OCR retry failed with model '{model_name}': {e}")

        return ""


gemini_service = GeminiService()
