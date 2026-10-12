import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Document, Page, Chunk, Summary
from app.services.gemini import gemini_service

logger = logging.getLogger(__name__)


class SummaryPipeline:
    def __init__(self, db: Session):
        self.db = db

    def get_cached_summary(
        self,
        document_id: str,
        summary_type: str,
        chapter_name: Optional[str] = None
    ) -> Optional[str]:
        query = self.db.query(Summary).filter(
            Summary.document_id == document_id,
            Summary.summary_type == summary_type
        )
        if chapter_name:
            query = query.filter(Summary.chapter_name == chapter_name)
        record = query.first()
        return record.content if record else None

    def save_summary(
        self,
        document_id: str,
        summary_type: str,
        content: str,
        chapter_name: Optional[str] = None
    ):
        record = Summary(
            document_id=document_id,
            summary_type=summary_type,
            chapter_name=chapter_name,
            content=content
        )
        self.db.add(record)
        self.db.commit()

    def generate_full_document_summary(self, document_id: str) -> str:
        """
        Map-Reduce Summary Pipeline:
        1. Group chunks by chapter (or by 5-10 page buckets if chapters are not identified).
        2. Map: Summarize each section/chapter.
        3. Reduce: Summarize the collection of section summaries into a comprehensive executive summary.
        """
        cached = self.get_cached_summary(document_id, "full")
        if cached:
            return cached

        # Fetch all pages for document ordered by page_number
        pages = self.db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        if not pages:
            return "Tài liệu không có nội dung để tóm tắt."

        # Group by chapter or page blocks of 5 pages
        sections: Dict[str, List[str]] = {}
        for p in pages:
            sec_name = p.chapter if p.chapter else f"Phần {((p.page_number - 1) // 5) + 1} (Trang {p.page_number})"
            if sec_name not in sections:
                sections[sec_name] = []
            if p.text:
                sections[sec_name].append(f"[Trang {p.page_number}]: {p.text[:1500]}")

        # Map step: generate partial summaries
        partial_summaries = []
        for sec_name, texts in list(sections.items())[:12]:  # Limit to 12 sections to manage tokens
            combined_text = "\n".join(texts)[:4000]
            if not combined_text.strip():
                continue
            prompt = f"""Hãy tóm tắt ngắn gọn các ý quan trọng nhất của phần sau ({sec_name}) từ tài liệu:

{combined_text}

Tóm tắt súc tích, giữ nguyên các thuật ngữ quan trọng và nêu rõ số trang."""
            sec_summary = gemini_service.generate_text(prompt)
            partial_summaries.append(f"### {sec_name}\n{sec_summary}")

        # Reduce step: produce unified final summary
        all_partials = "\n\n".join(partial_summaries)
        reduce_prompt = f"""Dưới đây là các phần tóm tắt chi tiết của các chương/phần trong tài liệu:

{all_partials}

Hãy tổng hợp lại thành một BẢN TÓM TẮT TOÀN DIỆN VÀ CHUYÊN SÂU của toàn bộ tài liệu:
1. Tổng quan mục đích và chủ đề chính của tài liệu.
2. Các luận điểm hoặc nội dung trọng tâm qua từng chương/phần.
3. Kết luận hoặc thông điệp chính.
Định dạng markdown rõ ràng, đẹp mắt, có trích dẫn số trang/chương cụ thể."""

        final_summary = gemini_service.generate_text(reduce_prompt)
        self.save_summary(document_id, "full", final_summary)
        return final_summary

    def generate_chapter_summary(self, document_id: str, chapter_name: str) -> str:
        """
        Summarize a specific chapter.
        """
        cached = self.get_cached_summary(document_id, "chapter", chapter_name)
        if cached:
            return cached

        # Find chunks or pages for this chapter
        chunks = self.db.query(Chunk).filter(
            Chunk.document_id == document_id,
            Chunk.chapter == chapter_name
        ).all()

        if not chunks:
            # Fallback search by text match
            pages = self.db.query(Page).filter(
                Page.document_id == document_id,
                Page.chapter == chapter_name
            ).all()
            texts = [p.text for p in pages if p.text]
        else:
            texts = [c.text for c in chunks]

        combined_text = "\n\n".join(texts)[:6000]
        if not combined_text.strip():
            return f"Không tìm thấy nội dung cho chương: {chapter_name}"

        prompt = f"""Hãy tóm tắt chi tiết chương '{chapter_name}' từ tài liệu sau:

{combined_text}

Yêu cầu:
- Nêu rõ các luận điểm chính.
- Các chi tiết hoặc công thức, định nghĩa đáng chú ý.
- Trình bày dạng danh sách bullet rõ ràng."""

        summary_text = gemini_service.generate_text(prompt)
        self.save_summary(document_id, "chapter", summary_text, chapter_name)
        return summary_text

    def generate_key_points(self, document_id: str) -> str:
        """
        Extract bullet-point Key Points.
        """
        cached = self.get_cached_summary(document_id, "key_points")
        if cached:
            return cached

        chunks = self.db.query(Chunk).filter(Chunk.document_id == document_id).limit(10).all()
        text_sample = "\n\n".join([f"[Trang {c.page}]: {c.text}" for c in chunks])[:6000]

        prompt = f"""Từ nội dung tài liệu dưới đây, hãy trích xuất 5-10 ĐIỂM CỐT LÕI (Key Takeaways) quan trọng nhất:

{text_sample}

Định dạng:
- Mỗi điểm cốt lõi có tiêu đề in đậm và diễn giải ngắn gọn.
- Ghi kèm số trang tham chiếu [Trang ...]."""

        result = gemini_service.generate_text(prompt)
        self.save_summary(document_id, "key_points", result)
        return result

    def explain_concept(self, document_id: str, concept: str) -> str:
        """
        Explain a difficult concept from document context.
        """
        from app.services.rag import vector_store
        results = vector_store.search_similar_chunks(document_id, query=concept, top_k=5)
        context_str = "\n\n".join([f"[Trang {r['page']}]: {r['text']}" for r in results])

        prompt = f"""Người dùng cần giải thích khái niệm hoặc nội dung sau trong tài liệu: '{concept}'

Ngữ cảnh từ tài liệu:
{context_str}

Hãy giải thích khái niệm này một cách dễ hiểu, trực quan, có ví dụ minh họa (nếu có trong sách) và nêu rõ trang tài liệu nói về khái niệm này."""

        return gemini_service.generate_text(prompt)

    def generate_flashcards(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Generate flashcards (question + answer + page) in JSON format.
        """
        cached = self.get_cached_summary(document_id, "flashcards")
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        chunks = self.db.query(Chunk).filter(Chunk.document_id == document_id).limit(8).all()
        text_sample = "\n\n".join([f"[Trang {c.page}]: {c.text}" for c in chunks])[:5000]

        prompt = f"""Từ tài liệu dưới đây, hãy tạo 6-8 thẻ ghi nhớ (Flashcards) học tập.
Mỗi thẻ gồm:
- question: Câu hỏi ngắn gọn, trọng tâm
- answer: Câu trả lời chính xác, dễ nhớ
- page: Số trang tham chiếu (số nguyên, ví dụ 12)

Dữ liệu tài liệu:
{text_sample}

Chỉ trả về JSON thuần túy (không dùng markdown code blocks ```json):
[
  {{"question": "...", "answer": "...", "page": 1}}
]"""

        raw = gemini_service.generate_text(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            cards = json.loads(cleaned)
            self.save_summary(document_id, "flashcards", json.dumps(cards, ensure_ascii=False))
            return cards
        except Exception:
            # Fallback if json parsing fails
            fallback = [
                {"question": "Nội dung chính của tài liệu là gì?", "answer": "Xem chi tiết trong mục tóm tắt.", "page": 1}
            ]
            return fallback

    def generate_questions(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Generate practice test questions with answers and explanations.
        """
        cached = self.get_cached_summary(document_id, "questions")
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        chunks = self.db.query(Chunk).filter(Chunk.document_id == document_id).limit(8).all()
        text_sample = "\n\n".join([f"[Trang {c.page}]: {c.text}" for c in chunks])[:5000]

        prompt = f"""Từ tài liệu dưới đây, hãy tạo 5 câu hỏi ôn tập (trắc nghiệm hoặc tự luận ngắn) để kiểm tra mức độ hiểu tài liệu:
Mỗi câu hỏi gồm:
- question: Câu hỏi
- options: Danh sách 4 đáp án [A, B, C, D] (hoặc null nếu là câu tự luận)
- answer: Đáp án chính xác
- explanation: Lời giải thích ngắn gọn tại sao
- page: Số trang tham chiếu

Dữ liệu:
{text_sample}

Chỉ trả về JSON thuần túy (không dùng markdown code blocks ```json):
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "A. ...",
    "explanation": "...",
    "page": 1
  }}
]"""

        raw = gemini_service.generate_text(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            questions = json.loads(cleaned)
            self.save_summary(document_id, "questions", json.dumps(questions, ensure_ascii=False))
            return questions
        except Exception:
            return []
