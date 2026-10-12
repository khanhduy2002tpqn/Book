import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "embedding_model" in data


def test_documents_list_empty_or_valid():
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_invalid_extension():
    # Attempt to upload a non-pdf file
    file_content = b"fake executable content"
    files = {"file": ("malicious.exe", io.BytesIO(file_content), "application/octet-stream")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Định dạng file không hỗ trợ" in response.json()["detail"]


def test_get_nonexistent_document():
    response = client.get("/api/documents/non-existent-id")
    assert response.status_code == 404
