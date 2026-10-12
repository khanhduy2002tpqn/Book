import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    page: int
    chapter: Optional[str]
    text: str
    source_type: str  # 'text' or 'ocr'
    token_count: int


class DocumentChunker:
    """
    Structure-aware Chunker:
    - Splits text hierarchically: Chapter -> Paragraph -> Sentence.
    - Maintains target token/character size (500 - 1000 tokens ~ 2000 - 4000 characters).
    - Maintains overlap (100 - 150 tokens ~ 400 - 600 characters).
    - Preserves sentence boundaries.
    - Retains page number, chapter, document_id, and source_type.
    """

    def __init__(
        self,
        min_chunk_chars: int = 1200,
        max_chunk_chars: int = 3500,
        overlap_chars: int = 500,
    ):
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        self.sentence_split_regex = re.compile(r'(?<=[.!?。])\s+(?=[A-ZÀ-Ỹ0-9])')

    def split_into_sentences(self, text: str) -> List[str]:
        # Split on sentence boundaries, keeping non-empty stripped sentences
        raw = self.sentence_split_regex.split(text)
        return [s.strip() for s in raw if s.strip()]

    def estimate_tokens(self, text: str) -> int:
        # Heuristic: 1 token ~ 4 characters for English / Vietnamese syllables
        return max(1, len(text) // 4)

    def create_chunks_from_pages(
        self,
        document_id: str,
        pages_data: List[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """
        Takes pages data list:
        [{
            "page_number": 1,
            "text": "...",
            "chapter": "...",
            "source_type": "text" | "ocr"
        }]
        Returns list of DocumentChunk with accurate metadata.
        """
        all_chunks: List[DocumentChunk] = []
        global_chunk_idx = 0

        for page_info in pages_data:
            page_num = page_info["page_number"]
            page_text = page_info["text"].strip()
            chapter = page_info.get("chapter")
            source_type = page_info.get("source_type", "text")

            if not page_text:
                continue

            # First split by paragraphs
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [page_text]

            current_sentences: List[str] = []
            current_len = 0

            for para in paragraphs:
                sentences = self.split_into_sentences(para)
                if not sentences:
                    sentences = [para]

                for sentence in sentences:
                    sentence_len = len(sentence)

                    # If adding sentence exceeds max_chunk_chars and we have reached min_chunk_chars
                    if (current_len + sentence_len > self.max_chunk_chars) and (current_len >= self.min_chunk_chars):
                        chunk_text = " ".join(current_sentences).strip()
                        if chunk_text:
                            all_chunks.append(
                                DocumentChunk(
                                    chunk_id=str(uuid.uuid4()),
                                    document_id=document_id,
                                    chunk_index=global_chunk_idx,
                                    page=page_num,
                                    chapter=chapter,
                                    text=chunk_text,
                                    source_type=source_type,
                                    token_count=self.estimate_tokens(chunk_text)
                                )
                            )
                            global_chunk_idx += 1

                        # Compute overlap from end of current sentences
                        overlap_sentences = []
                        overlap_acc = 0
                        for s in reversed(current_sentences):
                            if overlap_acc + len(s) <= self.overlap_chars:
                                overlap_sentences.insert(0, s)
                                overlap_acc += len(s)
                            else:
                                break

                        current_sentences = overlap_sentences + [sentence]
                        current_len = sum(len(s) for s in current_sentences)
                    else:
                        current_sentences.append(sentence)
                        current_len += sentence_len

            # Flush remaining sentences for this page
            if current_sentences:
                chunk_text = " ".join(current_sentences).strip()
                if chunk_text:
                    all_chunks.append(
                        DocumentChunk(
                            chunk_id=str(uuid.uuid4()),
                            document_id=document_id,
                            chunk_index=global_chunk_idx,
                            page=page_num,
                            chapter=chapter,
                            text=chunk_text,
                            source_type=source_type,
                            token_count=self.estimate_tokens(chunk_text)
                        )
                    )
                    global_chunk_idx += 1

        return all_chunks
