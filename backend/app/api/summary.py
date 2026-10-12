from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.schemas import SummaryResponse, FlashcardsResponse, QuestionsResponse
from app.services.summary import SummaryPipeline

router = APIRouter(prefix="/documents", tags=["summary"])


class ExplainRequest(BaseModel):
    concept: str


@router.post("/{document_id}/summary", response_model=SummaryResponse)
def get_full_summary(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tài liệu chưa sẵn sàng (trạng thái: {doc.status})."
        )

    pipeline = SummaryPipeline(db)
    cached = pipeline.get_cached_summary(document_id, "full")
    if cached:
        return SummaryResponse(
            document_id=document_id,
            summary_type="full",
            content=cached,
            from_cache=True
        )

    content = pipeline.generate_full_document_summary(document_id)
    return SummaryResponse(
        document_id=document_id,
        summary_type="full",
        content=content,
        from_cache=False
    )


@router.post("/{document_id}/chapters/{chapter}/summary", response_model=SummaryResponse)
def get_chapter_summary(document_id: str, chapter: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    pipeline = SummaryPipeline(db)
    cached = pipeline.get_cached_summary(document_id, "chapter", chapter)
    if cached:
        return SummaryResponse(
            document_id=document_id,
            summary_type="chapter",
            chapter_name=chapter,
            content=cached,
            from_cache=True
        )

    content = pipeline.generate_chapter_summary(document_id, chapter)
    return SummaryResponse(
        document_id=document_id,
        summary_type="chapter",
        chapter_name=chapter,
        content=content,
        from_cache=False
    )


@router.post("/{document_id}/key-points", response_model=SummaryResponse)
def get_key_points(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    pipeline = SummaryPipeline(db)
    cached = pipeline.get_cached_summary(document_id, "key_points")
    if cached:
        return SummaryResponse(
            document_id=document_id,
            summary_type="key_points",
            content=cached,
            from_cache=True
        )

    content = pipeline.generate_key_points(document_id)
    return SummaryResponse(
        document_id=document_id,
        summary_type="key_points",
        content=content,
        from_cache=False
    )


@router.post("/{document_id}/explain", response_model=SummaryResponse)
def explain_concept(document_id: str, req: ExplainRequest, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    pipeline = SummaryPipeline(db)
    content = pipeline.explain_concept(document_id, req.concept)
    return SummaryResponse(
        document_id=document_id,
        summary_type="explain",
        content=content,
        from_cache=False
    )


@router.post("/{document_id}/flashcards", response_model=FlashcardsResponse)
def get_flashcards(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    pipeline = SummaryPipeline(db)
    cards = pipeline.generate_flashcards(document_id)
    return FlashcardsResponse(flashcards=cards)


@router.post("/{document_id}/questions", response_model=QuestionsResponse)
def get_questions(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    pipeline = SummaryPipeline(db)
    questions = pipeline.generate_questions(document_id)
    return QuestionsResponse(questions=questions)
