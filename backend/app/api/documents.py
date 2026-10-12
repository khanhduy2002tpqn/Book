import os
import re
import uuid
import logging
import urllib.parse
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document, Page, Chunk
from app.schemas import DocumentResponse, DocumentListItem, PageResponse, DocumentUpdate
from app.services.pdf import PDFReaderService, DocumentChunker
from app.services.ocr import OCREngineService
from app.services.rag import vector_store
from app.services.classifier import detect_grade_and_subject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

pdf_reader = PDFReaderService()
ocr_engine = OCREngineService()
chunker = DocumentChunker()


def sanitize_filename(filename: str) -> str:
    """Remove unsafe characters and directory traversal attempts."""
    clean = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_\-\.\u00C0-\u024F\u1EA0-\u1EF9]', '_', clean)
    return clean or "document.pdf"


def process_document_background(document_id: str, file_path: str):
    """
    Background worker that extracts text, runs parallel OCR with Gemini Vision,
    generates chunks, computes embeddings, and stores vectors in Qdrant.
    """
    import time
    import concurrent.futures
    import pymupdf as fitz
    from app.services.gemini.client import gemini_service
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        doc_record = db.query(Document).filter(Document.id == document_id).first()
        if not doc_record:
            return

        if not os.path.exists(file_path):
            doc_record.status = "failed"
            doc_record.error_message = f"File không tồn tại trên ổ đĩa: {file_path}"
            db.commit()
            return

        # 1. Open PDF & examine text layers
        doc_record.status = "processing_pdf"
        doc_record.error_message = "Đang phân tích cấu trúc PDF..."
        db.commit()

        initial_doc = fitz.open(file_path)
        total_pages = len(initial_doc)
        doc_record.page_count = total_pages
        toc_map = pdf_reader.extract_toc_map(initial_doc)
        initial_doc.close()
        db.commit()

        # Clean old pages and chunks if re-processing
        vector_store.delete_document_vectors(document_id)
        db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        db.query(Page).filter(Page.document_id == document_id).delete()
        db.commit()

        # 2. Check each page for text vs OCR
        doc_record.status = "running_ocr"
        doc_record.error_message = f"Đang OCR: 0/{total_pages} trang (0%)"
        db.commit()

        def process_page_task(idx):
            page_num = idx + 1
            # Thread-safe: open own document handle per thread
            thread_doc = fitz.open(file_path)
            try:
                page = thread_doc[idx]
                raw_text = page.get_text("text").strip()
                clean_text = re.sub(r'\s+', ' ', raw_text).strip()

                chapter = toc_map.get(page_num)
                if not chapter:
                    chapter = pdf_reader.detect_chapter_from_text(raw_text)

                ocr_used = False
                # If text is insufficient, run Gemini Vision OCR
                if len(clean_text) < 50:
                    pix = page.get_pixmap(dpi=110)
                    img_bytes = pix.tobytes("png")
                    ocr_text = gemini_service.extract_text_from_image(img_bytes)
                    clean_text = ocr_text or f"[Trang {page_num}]"
                    ocr_used = True

                    if not chapter:
                        for line in clean_text.split("\n")[:6]:
                            l_up = line.upper()
                            if any(k in l_up for k in ["CHƯƠNG", "CHAPTER", "MỤC LỤC", "BÀI "]):
                                chapter = line.strip()
                                break

                return {
                    "page_number": page_num,
                    "text": clean_text,
                    "chapter": chapter,
                    "ocr_used": ocr_used
                }
            finally:
                thread_doc.close()

        # Run parallel extraction/OCR with 3 workers
        results_map = {}
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_idx = {executor.submit(process_page_task, idx): idx for idx in range(total_pages)}
            for future in concurrent.futures.as_completed(future_to_idx):
                res = future.result()
                results_map[res["page_number"]] = res
                completed += 1
                if completed % 5 == 0 or completed == total_pages:
                    pct = int((completed / total_pages) * 100)
                    doc_record.error_message = f"Đang OCR: {completed}/{total_pages} trang ({pct}%)"
                    db.commit()

        # Insert Page records ordered
        processed_pages = []
        for page_num in range(1, total_pages + 1):
            p_data = results_map[page_num]
            page_obj = Page(
                document_id=document_id,
                page_number=page_num,
                text=p_data["text"],
                ocr_used=p_data["ocr_used"],
                chapter=p_data["chapter"]
            )
            db.add(page_obj)
            db.flush()
            processed_pages.append({
                "page_id": page_obj.id,
                "page_number": page_num,
                "text": p_data["text"],
                "chapter": p_data["chapter"],
                "source_type": "ocr" if p_data["ocr_used"] else "text"
            })
        db.commit()

        # 3. Structure-aware Chunking
        doc_record.status = "creating_embeddings"
        doc_record.error_message = "Đang phân đoạn ngữ cảnh..."
        db.commit()

        chunks = chunker.create_chunks_from_pages(document_id, processed_pages)

        # 4. Vector Embedding & Qdrant Indexing
        doc_record.status = "indexing"
        doc_record.error_message = f"Đang tạo vector embedding ({len(chunks)} chunks)..."
        db.commit()

        point_ids = vector_store.insert_chunks(document_id, chunks)

        # 5. Save chunks to SQLite
        for chunk, point_id in zip(chunks, point_ids):
            matched_page = next((p["page_id"] for p in processed_pages if p["page_number"] == chunk.page), None)
            chunk_obj = Chunk(
                id=chunk.chunk_id,
                document_id=document_id,
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

        doc_record.status = "ready"
        doc_record.error_message = None
        db.commit()
        logger.info(f"Document {document_id} processed successfully ({len(chunks)} chunks).")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        db.rollback()
        doc_record = db.query(Document).filter(Document.id == document_id).first()
        if doc_record:
            doc_record.status = "failed"
            doc_record.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    grade: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # 1. Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không hỗ trợ: {ext}. Chỉ chấp nhận file .pdf"
        )

    # 2. Validate MIME type
    if file.content_type and file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content-Type không hợp lệ: {file.content_type}"
        )

    # 3. Read and validate size
    content = await file.read()
    file_size = len(content)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dung lượng file vượt quá giới hạn ({settings.MAX_FILE_SIZE_MB}MB)."
        )

    # 4. Save file to disk
    doc_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    saved_filename = f"{doc_id}_{safe_name}"
    file_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Auto-detect Grade & Subject if not explicitly provided
    auto_g, auto_s = detect_grade_and_subject(file.filename)
    final_grade = grade.strip() if grade and grade.strip() else auto_g
    final_subject = subject.strip() if subject and subject.strip() else auto_s

    # 5. Create initial document record
    doc_record = Document(
        id=doc_id,
        filename=safe_name,
        file_path=file_path,
        file_size=file_size,
        page_count=0,
        status="uploaded",
        grade=final_grade,
        subject=final_subject
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # 6. Queue non-blocking background processing task
    background_tasks.add_task(process_document_background, doc_id, file_path)

    return doc_record


@router.post("/batch-upload", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    grade: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Tải lên và xếp hàng OCR/lập chỉ mục hàng loạt nhiều tài liệu PDF.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có file nào được tải lên.")

    created_docs: List[Document] = []
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            continue

        content = await file.read()
        file_size = len(content)
        if file_size > max_bytes or file_size == 0:
            continue

        doc_id = str(uuid.uuid4())
        safe_name = sanitize_filename(file.filename)
        saved_filename = f"{doc_id}_{safe_name}"
        file_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        auto_g, auto_s = detect_grade_and_subject(file.filename)
        final_grade = grade.strip() if grade and grade.strip() else auto_g
        final_subject = subject.strip() if subject and subject.strip() else auto_s

        doc_record = Document(
            id=doc_id,
            filename=safe_name,
            file_path=file_path,
            file_size=file_size,
            page_count=0,
            status="uploaded",
            grade=final_grade,
            subject=final_subject
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        background_tasks.add_task(process_document_background, doc_id, file_path)
        created_docs.append(doc_record)

    return created_docs


@router.get("", response_model=List[DocumentListItem])
def list_documents(
    grade: Optional[str] = Query(None, description="Lọc theo khối lớp"),
    subject: Optional[str] = Query(None, description="Lọc theo môn học"),
    db: Session = Depends(get_db)
):
    # Auto-backfill existing documents if grade is missing or generic
    try:
        null_docs = db.query(Document).filter(
            (Document.grade == None) | (Document.grade == "Chung") | (Document.grade == "")
        ).all()
        if null_docs:
            for d in null_docs:
                g, s = detect_grade_and_subject(d.filename)
                d.grade = g
                if not d.subject or d.subject == "Khác":
                    d.subject = s
            db.commit()
    except Exception:
        pass

    query = db.query(Document)
    if grade and grade != "Tất cả":
        query = query.filter(Document.grade == grade)
    if subject and subject != "Tất cả":
        query = query.filter(Document.subject == subject)

    return query.order_by(Document.created_at.desc()).all()


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: str, payload: DocumentUpdate, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    if payload.grade is not None:
        doc.grade = payload.grade
    if payload.subject is not None:
        doc.subject = payload.subject

    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")
    return doc


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    # 1. Delete file on disk
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {doc.file_path}: {e}")

    # 2. Delete vectors from Qdrant
    vector_store.delete_document_vectors(document_id)

    # 3. Delete from DB (cascades to pages, chunks, conversations, summaries)
    db.delete(doc)
    db.commit()

    return {"message": "Đã xóa tài liệu thành công.", "document_id": document_id}


@router.get("/{document_id}/pages/{page_number}", response_model=PageResponse)
def get_page(document_id: str, page_number: int, db: Session = Depends(get_db)):
    page = db.query(Page).filter(
        Page.document_id == document_id,
        Page.page_number == page_number
    ).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy trang {page_number}.")
    return page


@router.get("/{document_id}/file")
def get_pdf_file(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File PDF không tồn tại.")

    # Safe RFC 5987 / latin-1 header for Unicode/Vietnamese filenames
    ascii_filename = re.sub(r'[^\x00-\x7F]+', '_', doc.filename)
    encoded_filename = urllib.parse.quote(doc.filename)
    disposition = f'inline; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'

    return FileResponse(
        path=doc.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition}
    )


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(document_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File PDF không còn tồn tại trên ổ đĩa.")

    doc.status = "processing_pdf"
    doc.error_message = "Bắt đầu lập chỉ mục lại..."
    db.commit()

    background_tasks.add_task(process_document_background, document_id, doc.file_path)
    return doc
