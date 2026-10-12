import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI PDF Reader"
    API_V1_STR: str = "/api"
    
    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    
    # Database
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    
    # Qdrant
    QDRANT_URL: str = ""
    QDRANT_LOCAL_PATH: str = "./qdrant_data"
    QDRANT_COLLECTION_NAME: str = "pdf_chunks"
    
    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # Text-To-Speech (TTS) settings
    TTS_ENGINE: str = "edge"  # "edge" (giọng tự nhiên, có auto fallback) hoặc "gtts" (Google TTS siêu tốc <0.5s)
    TTS_VOICE: str = "vi-VN-HoaiMyNeural"
    TTS_RATE: str = "+10%"
    
    # RAG parameters
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.35
    
    # Upload settings
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf", "application/x-pdf"]
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.QDRANT_LOCAL_PATH, exist_ok=True)
