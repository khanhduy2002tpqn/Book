import sys
import os
import time
import logging
import concurrent.futures
import pymupdf as fitz

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Document, Page, Chunk
from app.services.pdf import DocumentChunker
from app.services.gemini.client import gemini_service
from app.services.rag import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def index_entire_document():
    db = SessionLocal()
    doc = db.query(Document).first()
    if not doc:
        print("Không tìm thấy tài liệu trong database.")
        return

    doc_id = doc.id
    file_path = doc.file_path
    print(f"Bắt đầu xử lý toàn bộ tài liệu: {doc.filename} ({doc_id})")

    pdf = fitz.open(file_path)
    total_pages = len(pdf)
    print(f"Tổng số trang cần OCR và lập chỉ mục: {total_pages} trang.")

    # 1. OCR all pages using parallel workers
    print("Đang tiến hành OCR đa luồng với Gemini Vision...")
    
    def process_single_page(idx):
        page_num = idx + 1
        page = pdf[idx]
        pix = page.get_pixmap(dpi=110)
        img_bytes = pix.tobytes("png")
        
        # Retry logic for Gemini OCR
        text = ""
        for attempt in range(3):
            try:
                text = gemini_service.extract_text_from_image(img_bytes)
                break
            except Exception as e:
                time.sleep(2 * (attempt + 1))
        
        # Fallback if empty
        if not text:
            text = f"[Trang {page_num}]"

        # Detect chapter
        chapter = None
        for line in text.split("\n")[:6]:
            l_up = line.upper()
            if "CHƯƠNG" in l_up or "CHAPTER" in l_up or "MỤC LỤC" in l_up or "BÀI " in l_up:
                chapter = line.strip()
                break

        return {
            "page_number": page_num,
            "text": text,
            "chapter": chapter
        }

    # Use 3 concurrent workers to stay well within Gemini API limits
    results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_idx = {executor.submit(process_single_page, idx): idx for idx in range(total_pages)}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_idx):
            res = future.result()
            results_map[res["page_number"]] = res
            completed += 1
            if completed % 10 == 0 or completed == total_pages:
                print(f"Tiến độ OCR: {completed}/{total_pages} trang hoàn thành ({(completed/total_pages)*100:.1f}%)")

    # Sort pages by page number
    ordered_pages = [results_map[p] for p in range(1, total_pages + 1)]

    # 2. Clear old chunks & pages from DB & Qdrant
    print("Xóa dữ liệu cũ và chuẩn bị nạp 134 trang mới...")
    vector_store.delete_document_vectors(doc_id)
    db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
    db.query(Page).filter(Page.document_id == doc_id).delete()
    db.commit()

    # 3. Insert Page objects into SQLite
    processed_pages = []
    for p in ordered_pages:
        page_obj = Page(
            document_id=doc_id,
            page_number=p["page_number"],
            text=p["text"],
            ocr_used=True,
            chapter=p["chapter"]
        )
        db.add(page_obj)
        db.flush()
        processed_pages.append({
            "page_id": page_obj.id,
            "page_number": p["page_number"],
            "text": p["text"],
            "chapter": p["chapter"],
            "source_type": "ocr"
        })
    db.commit()

    # 4. Create Chunks
    print(f"Đang phân đoạn ngữ cảnh (chunking) cho {len(processed_pages)} trang...")
    chunker = DocumentChunker()
    chunks = chunker.create_chunks_from_pages(doc_id, processed_pages)
    print(f"Đã tạo {len(chunks)} chunks ngữ cảnh.")

    # 5. Embed and Index to Qdrant with BGE-M3
    print("Đang tạo vector embeddings (BGE-M3) và lưu vào Qdrant...")
    point_ids = vector_store.insert_chunks(doc_id, chunks)

    # 6. Save chunks to SQLite
    for chunk, point_id in zip(chunks, point_ids):
        matched_page = next((p["page_id"] for p in processed_pages if p["page_number"] == chunk.page), None)
        chunk_obj = Chunk(
            id=chunk.chunk_id,
            document_id=doc_id,
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
    db.commit()
    print(f"Hoàn thành xuất sắc! Đã lập chỉ mục toàn bộ {total_pages} trang ({len(chunks)} chunks).")

if __name__ == "__main__":
    t0 = time.time()
    index_entire_document()
    print(f"Tổng thời gian: {time.time()-t0:.2f}s")
