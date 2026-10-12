import sys
import os
import time
import logging
import concurrent.futures
import pymupdf as fitz
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Document, Page, Chunk
from app.services.pdf import DocumentChunker, PDFReaderService
from app.services.gemini.client import gemini_service
from app.services.rag import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def process_van9():
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == "e8d3d326-5e5b-4026-bd82-3bbc6eb74c21").first()
    if not doc:
        print("Document not found!")
        return

    file_path = doc.file_path
    print(f"Bắt đầu OCR và lập chỉ mục SGK Văn 9: {doc.filename}")
    
    pdf = fitz.open(file_path)
    total_pages = len(pdf)
    pdf_reader = PDFReaderService()
    toc_map = pdf_reader.extract_toc_map(pdf)
    pdf.close()

    print(f"Tổng số trang: {total_pages}. Chạy song song 3 luồng...")

    # Clear old
    vector_store.delete_document_vectors(doc.id)
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(Page).filter(Page.document_id == doc.id).delete()
    doc.status = "running_ocr"
    doc.error_message = f"Đang OCR: 0/{total_pages} trang (0%)"
    db.commit()

    def ocr_page(idx):
        page_num = idx + 1
        thread_doc = fitz.open(file_path)
        try:
            page = thread_doc[idx]
            pix = page.get_pixmap(dpi=110)
            img_bytes = pix.tobytes("png")
            
            chapter = toc_map.get(page_num)
            text = gemini_service.extract_text_from_image(img_bytes)
            if not text:
                text = f"[Trang {page_num}]"

            if not chapter:
                for line in text.split("\n")[:6]:
                    l_up = line.upper()
                    if any(k in l_up for k in ["BÀI ", "CHƯƠNG", "BÀI HỌC", "VĂN BẢN"]):
                        chapter = line.strip()
                        break

            return {
                "page_number": page_num,
                "text": text,
                "chapter": chapter
            }
        finally:
            thread_doc.close()

    results_map = {}
    completed = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_idx = {executor.submit(ocr_page, idx): idx for idx in range(total_pages)}
        for future in concurrent.futures.as_completed(future_to_idx):
            res = future.result()
            results_map[res["page_number"]] = res
            completed += 1
            if completed % 10 == 0 or completed == total_pages:
                pct = int((completed / total_pages) * 100)
                elapsed = time.time() - t0
                speed = completed / elapsed if elapsed > 0 else 0
                eta = (total_pages - completed) / speed if speed > 0 else 0
                print(f"Tiến độ OCR: {completed}/{total_pages} trang ({pct}%) | Tốc độ: {speed:.1f} trang/s | Còn lại: ~{eta:.0f}s")
                doc.error_message = f"Đang OCR: {completed}/{total_pages} trang ({pct}%)"
                db.commit()

    print("Hoàn tất OCR 154 trang! Đang lưu các trang vào SQLite...")
    processed_pages = []
    for page_num in range(1, total_pages + 1):
        p_data = results_map[page_num]
        page_obj = Page(
            document_id=doc.id,
            page_number=page_num,
            text=p_data["text"],
            ocr_used=True,
            chapter=p_data["chapter"]
        )
        db.add(page_obj)
        db.flush()
        processed_pages.append({
            "page_id": page_obj.id,
            "page_number": page_num,
            "text": p_data["text"],
            "chapter": p_data["chapter"],
            "source_type": "ocr"
        })
    db.commit()

    print("Đang tạo chunks...")
    chunker = DocumentChunker()
    chunks = chunker.create_chunks_from_pages(doc.id, processed_pages)
    print(f"Tạo được {len(chunks)} chunks.")

    print("Đang tạo vector embeddings và lưu vào Qdrant...")
    doc.status = "indexing"
    doc.error_message = f"Đang lập chỉ mục {len(chunks)} chunks..."
    db.commit()

    point_ids = vector_store.insert_chunks(doc.id, chunks)

    for chunk, point_id in zip(chunks, point_ids):
        matched_page = next((p["page_id"] for p in processed_pages if p["page_number"] == chunk.page), None)
        chunk_obj = Chunk(
            id=chunk.chunk_id,
            document_id=doc.id,
            page_id=matched_page,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            chapter=chunk.chapter,
            page=chunk.page,
            qdrant_point_id=point_id,
            token_count=chunk.token_count,
            source_type=chunk.source_type
        )
        db.add(chunk_obj)

    doc.status = "ready"
    doc.error_message = None
    db.commit()
    print(f"HOÀN TẤT THÀNH CÔNG toàn bộ 154 trang SGK Văn 9 trong {time.time()-t0:.2f}s!")

if __name__ == "__main__":
    process_van9()
