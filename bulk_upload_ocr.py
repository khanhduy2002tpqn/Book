#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tool Tải lên & OCR Hàng Loạt Sách Giáo Khoa (Bulk Upload & OCR Tool)
Dành cho hệ thống AI PDF Reader / RAG Assistant.
"""

import os
import sys
import time
import argparse
import urllib.request
import urllib.parse
import json

# Force UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add backend to path to import classifier
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
try:
    from app.services.classifier import detect_grade_and_subject
except ImportError:
    import re
    def detect_grade_and_subject(fn):
        return "Chung", "Khác"

API_BASE = "http://localhost:8000/api"


def check_backend_alive():
    try:
        req = urllib.request.Request(f"{API_BASE}/health")
        with urllib.request.urlopen(req, timeout=3) as res:
            data = json.loads(res.read())
            return data.get("status") == "healthy"
    except Exception:
        return False


def upload_single_file(file_path: str, grade: str = None, subject: str = None):
    filename = os.path.basename(file_path)
    if not grade or not subject:
        auto_g, auto_s = detect_grade_and_subject(filename)
        grade = grade or auto_g
        subject = subject or auto_s

    boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
    body = bytearray()

    # Form field: grade
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="grade"\r\n\r\n')
    body.extend(f"{grade}\r\n".encode("utf-8"))

    # Form field: subject
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="subject"\r\n\r\n')
    body.extend(f"{subject}\r\n".encode("utf-8"))

    # Form field: file
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/pdf\r\n\r\n")
    with open(file_path, "rb") as f:
        body.extend(f.read())
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        f"{API_BASE}/documents/upload",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def poll_document_status(doc_id: str):
    req = urllib.request.Request(f"{API_BASE}/documents/{doc_id}")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


def main():
    print("=" * 65)
    print("      TOOL TẢI LÊN & OCR HÀNG LOẠT SÁCH GIÁO KHOA")
    print("=" * 65)

    parser = argparse.ArgumentParser(description="Upload and OCR multiple PDF textbooks")
    parser.add_argument("--folder", "-f", type=str, help="Đường dẫn thư mục chứa các file PDF")
    parser.add_argument("--grade", "-g", type=str, default="", help="Gán cứng khối lớp (để trống để tự nhận diện)")
    parser.add_argument("--subject", "-s", type=str, default="", help="Gán cứng môn học (để trống để tự nhận diện)")
    args = parser.parse_args()

    # 1. Kiểm tra Backend
    print("\n[1/3] Đang kiểm tra kết nối Backend FastAPI (http://localhost:8000)...")
    if not check_backend_alive():
        print("[LỖI] Không thể kết nối đến Backend tại http://localhost:8000!")
        print("Vui lòng khởi động backend trước bằng file 'run_local.bat'.")
        sys.exit(1)
    print("  -> Kết nối Backend thành công! Dịch vụ đang sẵn sàng.")

    # 2. Xác định thư mục chứa file PDF
    target_folder = args.folder
    if not target_folder:
        print("\n[2/3] Nhập đường dẫn thư mục chứa sách PDF:")
        target_folder = input("  Đường dẫn: ").strip().strip('"').strip("'")

    if not target_folder or not os.path.exists(target_folder):
        print(f"[LỖI] Thư mục không tồn tại: {target_folder}")
        sys.exit(1)

    # 3. Quét danh sách file PDF
    pdf_files = []
    for root, _, files in os.walk(target_folder):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, f))

    if not pdf_files:
        print(f"\n[CẢNH BÁO] Không tìm thấy file .pdf nào trong thư mục: {target_folder}")
        sys.exit(0)

    print(f"\n  -> Tìm thấy {len(pdf_files)} file PDF sách giáo khoa.\n")
    print("-" * 65)
    print(f"{'STT':<4} | {'Tên File':<32} | {'Khối Lớp':<10} | {'Môn':<10}")
    print("-" * 65)

    preview_items = []
    for idx, fpath in enumerate(pdf_files, 1):
        fname = os.path.basename(fpath)
        auto_g, auto_s = detect_grade_and_subject(fname)
        grade = args.grade or auto_g
        subject = args.subject or auto_s
        preview_items.append((fpath, fname, grade, subject))
        short_name = (fname[:29] + '...') if len(fname) > 32 else fname
        print(f"{idx:<4} | {short_name:<32} | {grade:<10} | {subject:<10}")

    print("-" * 65)
    confirm = input(f"\nBạn có muốn bắt đầu tải lên và OCR {len(pdf_files)} sách này? (Y/n): ").strip().lower()
    if confirm and confirm != 'y' and confirm != 'yes':
        print("Đã hủy thao tác.")
        sys.exit(0)

    # 4. Tải lên và xếp hàng OCR
    print("\n[3/3] Đang tải lên hệ thống...")
    uploaded_docs = []
    for idx, (fpath, fname, grade, subject) in enumerate(preview_items, 1):
        fsize_mb = os.path.getsize(fpath) / (1024 * 1024)
        print(f"[{idx}/{len(preview_items)}] Đang gửi: {fname} ({fsize_mb:.1f} MB)...", end="", flush=True)
        try:
            doc = upload_single_file(fpath, grade, subject)
            uploaded_docs.append(doc)
            print(" -> Xong! (Đã xếp hàng OCR)")
        except Exception as e:
            print(f" -> [LỖI]: {e}")

    print("\n" + "=" * 65)
    print(f"   ĐÃ GỬI THÀNH CÔNG {len(uploaded_docs)}/{len(preview_items)} SÁCH VÀO HÀNG ĐỢI XỬ LÝ")
    print("=" * 65)
    print("Hệ thống Backend đang tiến hành OCR (Gemini Vision) và lập chỉ mục")
    print("ngữ nghĩa BAAI/bge-m3 trong nền. Bạn có thể mở giao diện web tại:")
    print("👉 http://localhost:5173 để theo dõi tiến trình và sử dụng ngay!")
    print("=" * 65)


if __name__ == "__main__":
    main()
