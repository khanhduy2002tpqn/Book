import os
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pymupdf as fitz


@dataclass
class ExtractedPageData:
    page_number: int  # 1-indexed
    text: str
    chapter: Optional[str] = None
    needs_ocr: bool = False
    ocr_used: bool = False
    confidence: Optional[float] = None
    image_bytes: Optional[bytes] = None


class PDFReaderService:
    def __init__(self, min_text_chars: int = 50):
        self.min_text_chars = min_text_chars
        # Regex patterns for Vietnamese and English chapter/section headers
        self.chapter_pattern = re.compile(
            r'^(?:Chương|Chuong|Chapter|Phần|Phan|Part|Bài|Bai|Section)\s+([0-9IVXLCDM]+|[A-Z])[:\.\-\s]*(.*)$',
            re.IGNORECASE
        )

    def extract_toc_map(self, doc: fitz.Document) -> Dict[int, str]:
        """
        Extract Table of Contents from PDF metadata if available.
        Maps page_number (1-indexed) -> Chapter title
        """
        toc_map: Dict[int, str] = {}
        try:
            toc = doc.get_toc()  # [[lvl, title, page], ...]
            if toc:
                current_title = ""
                # Sort toc items by page
                sorted_toc = sorted(toc, key=lambda x: x[2])
                for item in sorted_toc:
                    lvl, title, page_num = item
                    if lvl <= 2:  # Chapter or major section
                        current_title = title.strip()
                    if page_num > 0:
                        toc_map[page_num] = current_title
        except Exception:
            pass
        return toc_map

    def detect_chapter_from_text(self, text: str) -> Optional[str]:
        """
        Detect chapter title from page text using heuristic regex.
        """
        # Search lines and sentence starts
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:8]:
            match = self.chapter_pattern.match(line)
            if match:
                return line.strip()

        # Also search inline if text was single-line
        search_match = re.search(
            r'(?:Chương|Chuong|Chapter|Phần|Phan|Part|Bài|Bai|Section)\s+[0-9IVXLCDM]+[:\.\-\s]*[^\n\.\?]{0,60}',
            text,
            re.IGNORECASE
        )
        if search_match:
            return search_match.group(0).strip()

        return None

    def read_pdf(self, file_path: str) -> Tuple[List[ExtractedPageData], int]:
        """
        Process a PDF file page by page:
        - Determine if page has clean selectable text or needs OCR.
        - Track chapters via TOC and regex headings.
        - Render page to image bytes if OCR is needed.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ValueError(f"Không thể mở file PDF (có thể bị mã hóa hoặc lỗi định dạng): {str(e)}")

        if doc.is_encrypted:
            raise ValueError("File PDF được bảo vệ bằng mật khẩu. Vui lòng mở khóa trước khi upload.")

        page_count = len(doc)
        toc_map = self.extract_toc_map(doc)
        pages_data: List[ExtractedPageData] = []
        current_chapter: Optional[str] = None

        for page_idx in range(page_count):
            page_num = page_idx + 1  # 1-indexed
            page = doc[page_idx]

            # Update chapter from TOC if defined for this page
            if page_num in toc_map:
                current_chapter = toc_map[page_num]

            # Extract raw text from PyMuPDF
            raw_text = page.get_text("text").strip()

            # Detect chapter title inside text if TOC didn't have one
            detected_ch = self.detect_chapter_from_text(raw_text)
            if detected_ch:
                current_chapter = detected_ch

            # Check if page has sufficient text content
            clean_text = re.sub(r'\s+', ' ', raw_text).strip()
            needs_ocr = len(clean_text) < self.min_text_chars

            image_bytes = None
            if needs_ocr:
                # Render page to high-quality image pixmap for OCR
                pix = page.get_pixmap(dpi=150)
                image_bytes = pix.tobytes("png")

            pages_data.append(
                ExtractedPageData(
                    page_number=page_num,
                    text=clean_text if not needs_ocr else "",
                    chapter=current_chapter,
                    needs_ocr=needs_ocr,
                    ocr_used=False,
                    image_bytes=image_bytes
                )
            )

        doc.close()
        return pages_data, page_count
