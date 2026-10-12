import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, Conversation, Message
from app.schemas import ChatRequest, ChatResponse, CitationSource, ConversationResponse, MessageResponse
from app.services.rag import vector_store
from app.services.gemini import gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/documents/{document_id}/chat", response_model=ChatResponse)
def chat_with_document(
    document_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    # 1. Verify document exists and is ready
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    if doc.status != "ready":
        status_messages = {
            "uploaded": "Tài liệu vừa được tải lên, đang chuẩn bị xử lý...",
            "processing_pdf": "Đang phân tích cấu trúc PDF...",
            "extracting_text": "Đang trích xuất nội dung văn bản...",
            "running_ocr": "Đang chạy OCR nhận dạng chữ từ trang ảnh...",
            "creating_embeddings": "Đang tạo vector embeddings...",
            "indexing": "Đang lập chỉ mục vào cơ sở dữ liệu vector...",
            "failed": f"Tài liệu xử lý thất bại: {doc.error_message or 'Lỗi không xác định'}"
        }
        msg = status_messages.get(doc.status, f"Tài liệu đang xử lý (trạng thái: {doc.status}).")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{msg} Vui lòng đợi hoàn tất trước khi đặt câu hỏi."
        )

    # 2. Get or create conversation
    conv = None
    if request.conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.document_id == document_id
        ).first()

    if not conv:
        conv = Conversation(
            document_id=document_id,
            title=request.message[:40] + ("..." if len(request.message) > 40 else "")
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # 3. Retrieve past messages for conversation context
    past_messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at).all()
    history = [{"role": m.role, "content": m.content} for m in past_messages]

    # 4. Semantic Search in Qdrant
    top_k = request.top_k or 5
    matched_chunks = vector_store.search_similar_chunks(
        document_id=document_id,
        query=request.message,
        top_k=top_k
    )

    # 5. Anti-hallucination check: if no relevant chunks found
    if not matched_chunks:
        answer = "Không tìm thấy thông tin phù hợp trong tài liệu để trả lời câu hỏi của bạn."
        citation_sources: List[CitationSource] = []
    else:
        # 6. Call Gemini LLM with context
        try:
            answer = gemini_service.generate_chat_answer(
                query=request.message,
                context_chunks=matched_chunks,
                conversation_history=history
            )
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi khi xử lý câu trả lời từ AI: {str(e)}"
            )

        # Build citation sources
        citation_sources = [
            CitationSource(
                page=chunk["page"],
                chunk_id=chunk["chunk_id"],
                score=round(chunk["score"], 4),
                chapter=chunk.get("chapter"),
                text=chunk.get("text", "")[:300]
            )
            for chunk in matched_chunks
        ]

    # 7. Persist messages
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=request.message
    )
    db.add(user_msg)

    sources_json_str = json.dumps([s.model_dump() for s in citation_sources], ensure_ascii=False)
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        sources_json=sources_json_str
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        conversation_id=conv.id,
        answer=answer,
        sources=citation_sources
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")

    messages_data = []
    for m in conv.messages:
        sources: List[CitationSource] = []
        if m.sources_json:
            try:
                raw_sources = json.loads(m.sources_json)
                sources = [CitationSource(**s) for s in raw_sources]
            except Exception:
                pass

        messages_data.append(
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                sources=sources,
                created_at=m.created_at
            )
        )

    return ConversationResponse(
        id=conv.id,
        document_id=conv.document_id,
        title=conv.title,
        created_at=conv.created_at,
        messages=messages_data
    )


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")

    db.delete(conv)
    db.commit()
    return {"message": "Đã xóa cuộc trò chuyện thành công.", "conversation_id": conversation_id}
