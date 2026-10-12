import pymupdf as fitz
from app.database import SessionLocal
from app.models import Document

db = SessionLocal()
doc = db.query(Document).first()
if not doc:
    print("No document found in DB")
    exit(0)

pdf = fitz.open(doc.file_path)
print(f"Total pages: {len(pdf)}")
for i in range(min(10, len(pdf))):
    text = pdf[i].get_text().strip()
    print(f"Page {i+1}: length={len(text)}")
    if len(text) > 0:
        sample = text[:100].replace('\n', ' ')
        print(f"   Sample: {repr(sample.encode('ascii', 'backslashreplace').decode('ascii'))}")
