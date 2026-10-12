import sys
import os
import time
import logging
import pymupdf as fitz

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import Document, Page, Chunk
from app.services.pdf import DocumentChunker
from app.services.ocr import OCREngineService
from app.services.rag import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

db = SessionLocal()
doc = db.query(Document).first()
if not doc:
    print("No document found in database.")
    sys.exit(0)

doc_id = doc.id
file_path = doc.file_path
print(f"Re-indexing document: {doc_id} ({doc.filename})")

# 1. Clear existing chunks and vectors
print("Clearing old dummy chunks from Qdrant and database...")
vector_store.delete_document_vectors(doc_id)
db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
db.query(Page).filter(Page.document_id == doc_id).delete()
db.commit()

# 2. Open PDF
pdf = fitz.open(file_path)
total_pages = len(pdf)
print(f"Total pages in PDF: {total_pages}")

ocr_engine = OCREngineService()
chunker = DocumentChunker()

processed_pages = []
# Process the first 30 pages with full OCR (covers Intro, Table of Contents, and full Chapter 1)
pages_to_process = min(35, total_pages)

for idx in range(pages_to_process):
    page_num = idx + 1
    t0 = time.time()
    page = pdf[idx]
    pix = page.get_pixmap(dpi=120)
    img_bytes = pix.tobytes("png")

    text, conf, boxes = ocr_engine.perform_ocr(img_bytes)
    t1 = time.time()
    print(f"[{page_num}/{pages_to_process}] OCR completed in {t1-t0:.2f}s ({len(text)} chars)")

    # Detect chapter if any
    chapter = None
    for line in text.split("\n")[:5]:
        if "CHƯƠNG" in line.upper() or "CHAPTER" in line.upper() or "MỤC LỤC" in line.upper():
            chapter = line.strip()
            break

    page_obj = Page(
        document_id=doc_id,
        page_number=page_num,
        text=text,
        ocr_used=True,
        chapter=chapter
    )
    db.add(page_obj)
    db.flush()

    processed_pages.append({
        "page_id": page_obj.id,
        "page_number": page_num,
        "text": text,
        "chapter": chapter,
        "source_type": "ocr"
    })

db.commit()

# 3. Create Chunks
print("Creating semantic chunks...")
chunks = chunker.create_chunks_from_pages(doc_id, processed_pages)
print(f"Created {len(chunks)} chunks.")

# 4. Embed & Index to Qdrant
print("Embedding chunks and indexing to Qdrant...")
point_ids = vector_store.insert_chunks(doc_id, chunks)

# 5. Save chunks to SQLite
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
print("Re-indexing completed successfully! Ready for AI question answering.")
