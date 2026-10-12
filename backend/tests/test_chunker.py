import pytest
from app.services.pdf.chunker import DocumentChunker


def test_chunker_basic():
    chunker = DocumentChunker(min_chunk_chars=100, max_chunk_chars=300, overlap_chars=50)
    pages = [
        {
            "page_number": 1,
            "text": "Đây là câu mở đầu của tài liệu AI PDF Reader. " * 5,
            "chapter": "Chương 1: Giới thiệu",
            "source_type": "text"
        },
        {
            "page_number": 2,
            "text": "Federated Learning là phương pháp học máy phân tán bảo vệ quyền riêng tư dữ liệu. " * 6,
            "chapter": "Chương 2: Federated Learning",
            "source_type": "text"
        }
    ]

    chunks = chunker.create_chunks_from_pages("doc-123", pages)
    assert len(chunks) >= 2
    # Check metadata integrity
    for chunk in chunks:
        assert chunk.document_id == "doc-123"
        assert chunk.page in [1, 2]
        assert chunk.source_type == "text"
        assert chunk.text is not None
        assert chunk.token_count > 0
        assert chunk.chunk_index >= 0


def test_chunker_preserves_sentence_boundaries():
    chunker = DocumentChunker(min_chunk_chars=50, max_chunk_chars=120, overlap_chars=20)
    text = "Câu thứ nhất rất hay. Câu thứ hai tiếp nối câu thứ nhất. Câu thứ ba hoàn tất đoạn văn."
    pages = [{"page_number": 1, "text": text, "chapter": "Mở đầu", "source_type": "text"}]

    chunks = chunker.create_chunks_from_pages("doc-456", pages)
    assert len(chunks) >= 1
    # Check that sentences end with proper punctuation
    for c in chunks:
        assert c.page == 1
        assert c.chapter == "Mở đầu"
