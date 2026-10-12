import time
import os
import concurrent.futures
import pymupdf as fitz
from app.services.gemini.client import gemini_service

pdf_file = 'uploads/' + [f for f in os.listdir('uploads') if f.endswith('.pdf')][0]
pdf = fitz.open(pdf_file)

def ocr_page(idx):
    pix = pdf[idx].get_pixmap(dpi=100)
    t = gemini_service.extract_text_from_image(pix.tobytes('png'))
    return idx, t

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(ocr_page, [1, 2, 3]))
t1 = time.time()

print(f"3 pages processed in {t1-t0:.2f}s!")
for idx, text in results:
    print(f"Page {idx+1}: {len(text)} chars, sample: {repr(text[:60])}")
