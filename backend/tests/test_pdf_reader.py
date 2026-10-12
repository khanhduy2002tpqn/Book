import os
import pytest
import pymupdf as fitz
from app.services.pdf.reader import PDFReaderService


def test_pdf_reader_detects_chapter_and_text(tmp_path):
    pdf_path = os.path.join(tmp_path, "sample_book.pdf")
    doc = fitz.open()

    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Chapter 1: Artificial Intelligence Fundamentals\nArtificial Intelligence is a branch of computer science.")

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Chapter 2: Deep Learning Architecture\nDeep learning models use multiple neural network layers to extract hierarchical features.")

    doc.save(pdf_path)
    doc.close()

    service = PDFReaderService(min_text_chars=20)
    pages, count = service.read_pdf(pdf_path)

    assert count == 2
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Chapter 1" in (pages[0].chapter or "")
    assert pages[0].needs_ocr is False
    assert "Artificial Intelligence" in pages[0].text

    assert pages[1].page_number == 2
    assert "Chapter 2" in (pages[1].chapter or "")
    assert "Deep learning" in pages[1].text
