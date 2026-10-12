import pymupdf as fitz
from app.database import SessionLocal
from app.models import Document
from app.services.ocr.engine import OCREngineService

db = SessionLocal()
doc = db.query(Document).first()
pdf = fitz.open(doc.file_path)

# Test on page 3 (usually contains TOC or Introduction)
pix = pdf[2].get_pixmap(dpi=150)
img_bytes = pix.tobytes("png")

ocr = OCREngineService()
text, conf, boxes = ocr.perform_ocr(img_bytes)

print(f"Page 3 OCR length: {len(text)}")
print("Sample lines:")
for line in text.split("\n")[:10]:
    print("  ", line.encode("ascii", "backslashreplace").decode("ascii"))
