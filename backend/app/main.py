import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    logger.info("Initializing database tables...")
    init_db()
    logger.info(f"App '{settings.PROJECT_NAME}' started successfully.")

    # Pre-warm embedding model to avoid search latency on first user/ESP32 query
    try:
        from app.services.embedding import embedding_service
        logger.info("Pre-warming local embedding model...")
        embedding_service._load_model()
        logger.info("Embedding model pre-warmed and ready.")
    except Exception as e:
        logger.error(f"Failed to pre-warm embedding model at startup: {e}", exc_info=True)

    # Auto-resume any interrupted document background processing
    try:
        import threading
        from app.database import SessionLocal
        from app.models import Document
        from app.api.documents import process_document_background

        db = SessionLocal()
        interrupted_docs = db.query(Document).filter(
            Document.status.in_(["uploaded", "processing_pdf", "extracting_text", "running_ocr", "creating_embeddings", "indexing"])
        ).all()
        for doc in interrupted_docs:
            logger.info(f"Auto-resuming interrupted document processing: {doc.id} ({doc.filename})")
            threading.Thread(
                target=process_document_background,
                args=(doc.id, doc.file_path),
                daemon=True
            ).start()
        db.close()
    except Exception as e:
        logger.warning(f"Error checking interrupted documents on startup: {e}")

    yield
    # Shutdown
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Backend API for AI PDF Reader (FastAPI, Qdrant, BGE-M3, Gemini)",
    lifespan=lifespan
)

# CORS Middleware
origins = settings.cors_origins
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Đã xảy ra lỗi máy chủ: {str(exc)}"}
    )


# Health check
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
        "gemini_model": settings.GEMINI_MODEL
    }


# Include all API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
