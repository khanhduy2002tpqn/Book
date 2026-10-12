# AI PDF Reader 📚🤖

Ứng dụng web AI đọc và hỏi đáp thông minh với tài liệu PDF (hỗ trợ cả PDF có văn bản và PDF dạng scan/ảnh qua OCR). AI trả lời dựa trên nội dung thực tế của tài liệu và trích dẫn số trang chính xác, hạn chế tối đa ảo giác (anti-hallucination).

---

## 🌟 Tính năng nổi bật

1. **Đọc PDF thông minh & OCR**:
   - Tự động nhận diện PDF có text hoặc PDF ảnh/scan.
   - Trích xuất văn bản tốc độ cao bằng **PyMuPDF (`fitz`)**.
   - OCR tự động cho các trang dạng scan/ảnh (PaddleOCR / EasyOCR / Tesseract).
   - Nhận diện cấu trúc tài liệu, mục lục (TOC) và tên từng chương (`Chương X` / `Chapter Y`).

2. **Structure-Aware Chunking**:
   - Phân đoạn văn bản theo thứ bậc: `Chương` ➔ `Đoạn văn` ➔ `Câu`.
   - Giữ nguyên ranh giới câu, độ dài 500–1000 tokens kèm overlap 100–150 tokens.
   - Mỗi chunk lưu đầy đủ metadata: `document_id`, `chunk_id`, `page`, `chapter`, `source_type`.

3. **Local Embedding & Vector Search (BGE-M3 + Qdrant)**:
   - Sử dụng model đa ngôn ngữ tiên tiến **`BAAI/bge-m3`** chạy hoàn toàn local qua **Sentence Transformers**.
   - Lưu trữ và tìm kiếm vector bằng **Qdrant** (hỗ trợ cả remote Docker server lẫn embedded local file không cần Docker).
   - Tìm kiếm Cosine Similarity với ngưỡng lọc (threshold) chống trả lời lan man.

4. **Chống ảo giác (Anti-Hallucination) với Google Gemini**:
   - Tích hợp **Google Gemini API** (`gemini-1.5-flash` / `gemini-2.0-flash`).
   - System prompt chống hallucination nghiêm ngặt: chỉ trả lời dựa trên context trích xuất từ PDF.
   - Nếu không có thông tin, AI sẽ thông báo rõ: *"Không tìm thấy thông tin phù hợp trong tài liệu."*

5. **Trích dẫn nguồn & PDF Viewer đồng bộ (Citation Navigation)**:
   - Trích dẫn rõ ràng số trang `[Trang X]` kèm độ tương đồng và preview đoạn văn bản.
   - Nhấp vào trích dẫn ➔ PDF Viewer tự động chuyển đến đúng trang và hiển thị banner highlight.
   - Có nút xem trực tiếp văn bản trích xuất / kết quả OCR của từng trang.

6. **Bộ công cụ học tập nâng cao (Study Tools)**:
   - **Tóm tắt toàn bộ (Map-Reduce)**: Tóm tắt từng chương/phần rồi tổng hợp thành báo cáo hoàn chỉnh (lưu cache trong DB).
   - **Tóm tắt từng chương**: Tóm tắt chuyên sâu theo từng chương của sách.
   - **Ý chính (Key Points)**: Trích xuất các luận điểm cốt lõi kèm số trang.
   - **Giải thích thuật ngữ (Explain)**: Diễn giải các khái niệm khó hiểu trong sách.
   - **Flashcards**: Tạo thẻ ghi nhớ học tập tương tác (lật thẻ xem đáp án, dẫn link tới trang PDF).
   - **Bộ câu hỏi ôn tập (Quiz)**: Tạo câu hỏi trắc nghiệm/tự luận kiểm tra kiến thức kèm đáp án và giải thích.

7. **Giao diện hiện đại (Modern UI/UX)**:
   - Layout 3 cột chuyên nghiệp: Danh sách tài liệu ➔ PDF Viewer ➔ Trợ lý AI.
   - Hỗ trợ Dark Mode / Light Mode.
   - Responsive hoàn toàn trên thiết bị di động (chuyển sang dạng tab: `PDF | AI Chat | Công cụ`).
   - Drag & drop tải file kèm thanh tiến trình từng bước (`Uploading` ➔ `Processing` ➔ `OCR` ➔ `Embedding` ➔ `Ready`).

---

## 🛠️ Cấu trúc dự án

```text
ai-pdf-reader/
│
├── frontend/                     # React + Vite + TypeScript + Ant Design
│   ├── src/
│   │   ├── components/
│   │   │   ├── DocumentList.tsx  # Danh sách tài liệu & trạng thái
│   │   │   ├── PDFViewer.tsx     # Viewer PDF & điều hướng trang
│   │   │   ├── ChatPanel.tsx     # Giao diện chat RAG & trích dẫn
│   │   │   ├── StudyTools.tsx    # Tóm tắt, Flashcards, Quiz, Giải thích
│   │   │   ├── UploadModal.tsx   # Modal upload & tiến trình xử lý
│   │   │   └── Navbar.tsx        # Thanh điều hướng & theme toggle
│   │   ├── hooks/                # Custom React Hooks
│   │   ├── services/             # Axios API service
│   │   ├── types/                # TypeScript interfaces
│   │   ├── App.tsx               # Layout chính
│   │   └── index.css             # Theme & Markdown CSS
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                      # Python 3.11+ / FastAPI
│   ├── app/
│   │   ├── api/                  # API routers (documents, chat, summary)
│   │   ├── database/             # SQLAlchemy engine & session
│   │   ├── models/               # Database ORM models
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── services/
│   │   │   ├── pdf/              # PyMuPDF reader & structure chunker
│   │   │   ├── ocr/              # PaddleOCR / EasyOCR / Tesseract engine
│   │   │   ├── embedding/        # BAAI/bge-m3 sentence transformers
│   │   │   ├── rag/              # Qdrant vector store
│   │   │   ├── gemini/           # Google Gemini API client
│   │   │   └── summary/          # Map-Reduce summary & learning pipeline
│   │   ├── config.py             # Settings từ .env
│   │   └── main.py               # FastAPI entrypoint
│   ├── tests/                    # Pytest unit & integration tests
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml            # Chạy toàn bộ stack (Frontend, Backend, Postgres, Qdrant)
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Hướng dẫn chạy nhanh trên máy (100% KHÔNG CẦN DOCKER)

Dự án đã được cấu hình tối ưu để **chạy trực tiếp trên máy của bạn** bằng Python và Node.js, **hoàn toàn không cần Docker hay bất kỳ phần mềm ảo hóa nào**.
- **Cơ sở dữ liệu**: Tự động dùng SQLite local (`sql_app.db`).
- **Vector Database**: Tự động dùng Qdrant Embedded local lưu trữ trực tiếp vào thư mục `./qdrant_data`.

---

### Cách 1: Chạy 1-Click bằng file `run_local.bat` (Tiện lợi nhất trên Windows)

1. Mở file [backend/.env](file:///c:/Users/KHANHDUY-PC/Book/backend/.env) và điền `GEMINI_API_KEY` của bạn.
2. Nhấp đúp chuột vào file **`run_local.bat`** ở thư mục gốc của dự án.
3. Script sẽ tự động:
   - Khởi động **Backend** tại `http://localhost:8000`
   - Khởi động **Frontend** tại `http://localhost:5173`
   - Tự động mở trình duyệt để bạn sử dụng ngay!

---

### Cách 2: Chạy thủ công bằng dòng lệnh (Terminal)

#### Bước 1: Khởi động Backend
Mở Terminal thứ nhất:
```powershell
cd backend

# Kích hoạt môi trường ảo Python đã có sẵn:
.\venv\Scripts\activate

# Chạy server FastAPI:
uvicorn app.main:app --reload --port 8000
```
> Server Backend sẽ hoạt động tại `http://localhost:8000` (Tài liệu API Swagger tại `http://localhost:8000/docs`).

#### Bước 2: Khởi động Frontend
Mở Terminal thứ hai:
```powershell
cd frontend

# Khởi động giao diện Vite:
npm run dev
```
> Giao diện web sẽ mở tại: `http://localhost:5173`.

---

## 🐳 Hướng dẫn chạy bằng Docker Compose (Tùy chọn)

Nếu bạn muốn đóng gói và chạy toàn bộ dịch vụ (Frontend, Backend, PostgreSQL, Qdrant):

1. Sao chép file cấu hình:
   ```bash
   cp .env.example .env
   ```
   Điền `GEMINI_API_KEY` vào file `.env`.

2. Khởi chạy:
   ```bash
   docker compose up --build -d
   ```

- **Frontend**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Qdrant Dashboard**: `http://localhost:6333/dashboard`

---

## 🧪 Kiểm thử (Testing)

Để chạy bộ kiểm thử tự động của backend:

```bash
cd backend
venv\Scripts\activate
pytest tests -v
```

Bộ test bao gồm:
- `test_chunker.py`: Kiểm tra thuật toán chunking, bảo toàn câu và metadata (trang, chương).
- `test_pdf_reader.py`: Kiểm tra trích xuất text và nhận diện chương từ PDF.
- `test_api.py`: Kiểm tra xác thực upload (phần mở rộng, MIME type), health check, security.

---

## 🛡️ Bảo mật & Chống ảo giác

1. **Bảo mật file**:
   - Kiểm tra định dạng đuôi file (`.pdf`) và MIME type (`application/pdf`).
   - Giới hạn dung lượng tối đa 50MB.
   - Làm sạch tên file (`sanitize_filename`) ngăn chặn Path Traversal (`../`).
   - Không cho phép thực thi file nhị phân.
2. **Bảo mật API Key**:
   - `GEMINI_API_KEY` chỉ được lưu trữ và xử lý tại backend, hoàn toàn không gửi ra frontend client.
3. **Chống ảo giác (Anti-Hallucination)**:
   - Tìm kiếm vector tương đồng kèm ngưỡng cắt `SIMILARITY_THRESHOLD`.
   - Nếu câu hỏi không có đoạn trích liên quan trong tài liệu, hệ thống thông báo thẳng thắn thay vì tự phỏng đoán.
   - Buộc Gemini chỉ trả lời từ văn bản được cung cấp và đính kèm số trang trích dẫn.

---

## 📋 Hướng nâng cấp tiếp theo

- [ ] Chat đa tài liệu (Multi-Document Chat): Cho phép so sánh nội dung giữa nhiều cuốn sách cùng lúc.
- [ ] Export tóm tắt và ghi chú dưới dạng Markdown/PDF.
- [ ] Tích hợp Text-to-Speech (TTS) đọc sách thông minh.
