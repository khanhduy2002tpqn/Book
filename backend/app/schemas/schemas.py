from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ================= Citation & Source =================
class CitationSource(BaseModel):
    page: int
    chunk_id: str
    score: float
    chapter: Optional[str] = None
    text: Optional[str] = None


# ================= Document =================
class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_size: int
    page_count: int
    status: str
    grade: Optional[str] = "Chung"
    subject: Optional[str] = "Khác"
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(DocumentListItem):
    file_path: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    grade: Optional[str] = None
    subject: Optional[str] = None


class PageResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    text: str
    ocr_used: bool
    chapter: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    page: int
    chapter: Optional[str] = None
    text: str
    source_type: str
    token_count: int

    model_config = ConfigDict(from_attributes=True)


# ================= Chat =================
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, description="Nội dung câu hỏi của người dùng")
    top_k: Optional[int] = Field(default=5, ge=1, le=15)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: List[CitationSource]


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: List[CitationSource] = []
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    document_id: str
    title: str
    created_at: datetime
    messages: List[MessageResponse] = []


# ================= Summaries & Features =================
class SummaryRequest(BaseModel):
    summary_type: str = Field(
        default="full",
        description="Loại tóm tắt: 'full', 'chapter', 'key_points', 'explain', 'questions', 'flashcards'"
    )
    chapter_name: Optional[str] = None
    custom_query: Optional[str] = None


class SummaryResponse(BaseModel):
    document_id: str
    summary_type: str
    chapter_name: Optional[str] = None
    content: str
    from_cache: bool = False


class FlashcardItem(BaseModel):
    question: str
    answer: str
    page: Optional[int] = None


class FlashcardsResponse(BaseModel):
    flashcards: List[FlashcardItem]


class QuestionItem(BaseModel):
    question: str
    options: Optional[List[str]] = None
    answer: str
    explanation: Optional[str] = None
    page: Optional[int] = None


class QuestionsResponse(BaseModel):
    questions: List[QuestionItem]
