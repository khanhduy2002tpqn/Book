from fastapi import APIRouter
from .documents import router as documents_router
from .chat import router as chat_router
from .summary import router as summary_router

api_router = APIRouter(prefix="/api")
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(summary_router)
