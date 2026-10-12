import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Document
from app.services.voice import voice_service
from app.services.rag import vector_store
from app.services.gemini import gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])


@router.websocket("/ws/voice/{document_id}")
async def voice_websocket_endpoint(websocket: WebSocket, document_id: str):
    await websocket.accept()
    logger.info(f"[WebSocket Voice] ESP32 connected for document_id: {document_id}")

    db: Session = SessionLocal()
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        # Fallback to the latest ready document if provided id doesn't match
        doc = db.query(Document).filter(Document.status == "ready").order_by(Document.created_at.desc()).first()

    current_doc_id = doc.id if doc else document_id
    current_doc_name = doc.filename if doc else "Tài liệu"
    db.close()

    # Send initial welcome frame
    await websocket.send_text(json.dumps({
        "status": "connected",
        "document_id": current_doc_id,
        "document_name": current_doc_name,
        "message": f"Đã kết nối thành công tới sách: {current_doc_name}"
    }))

    pcm_buffer = bytearray()
    is_recording = False

    try:
        while True:
            message = await websocket.receive()

            # 1. Received Text Frame (Control commands)
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    event = data.get("event")

                    if event == "start":
                        pcm_buffer.clear()
                        is_recording = True
                        logger.info(f"[Voice WS] ESP32 started recording...")
                        await websocket.send_text(json.dumps({
                            "status": "recording",
                            "message": "Đang lắng nghe âm thanh từ ESP32..."
                        }))

                    elif event == "stop":
                        is_recording = False
                        total_pcm_len = len(pcm_buffer)
                        logger.info(f"[Voice WS] ESP32 stopped recording. Received {total_pcm_len} bytes PCM.")

                        if total_pcm_len < 3200:
                            await websocket.send_text(json.dumps({
                                "status": "error",
                                "message": "Âm thanh quá ngắn hoặc không có tiếng nói. Vui lòng thử lại."
                            }))
                            continue

                        # A. Transcribe speech using Gemini Multimodal Audio
                        await websocket.send_text(json.dumps({
                            "status": "transcribing",
                            "message": "Đang nhận diện giọng nói tiếng Việt..."
                        }))

                        user_query = await voice_service.transcribe_audio(bytes(pcm_buffer), sample_rate=16000)
                        logger.info(f"[Voice WS] Transcribed text: '{user_query}'")

                        if not user_query:
                            await websocket.send_text(json.dumps({
                                "status": "error",
                                "message": "Không nhận diện được giọng nói rõ ràng. Vui lòng nói to hơn."
                            }))
                            continue

                        await websocket.send_text(json.dumps({
                            "status": "user_query",
                            "text": user_query
                        }))

                        # B. Query RAG context from Book
                        await websocket.send_text(json.dumps({
                            "status": "searching",
                            "message": "Đang tra cứu nội dung trong sách giáo khoa..."
                        }))

                        context_chunks = await asyncio.to_thread(
                            vector_store.search_similar_chunks,
                            current_doc_id,
                            user_query,
                            top_k=4
                        )

                        # C. Generate concise spoken answer via Gemini (dành riêng cho loa)
                        await websocket.send_text(json.dumps({
                            "status": "generating",
                            "message": "Đang tổng hợp câu trả lời..."
                        }))

                        answer_text = await asyncio.to_thread(
                            gemini_service.generate_voice_answer,
                            user_query,
                            context_chunks
                        )

                        await websocket.send_text(json.dumps({
                            "status": "answer",
                            "text": answer_text,
                            "sources_count": len(context_chunks)
                        }))

                        # D. Stream Audio PCM về ESP32 phát luôn ra loa theo thời gian thực
                        await websocket.send_text(json.dumps({
                            "status": "synthesizing",
                            "message": "Đang truyền giọng nói về loa phát..."
                        }))

                        audio_started = False
                        total_streamed_bytes = 0

                        async for pcm_chunk in voice_service.stream_speech_pcm(answer_text, target_sample_rate=44100):
                            if not audio_started:
                                audio_started = True
                                logger.info("[Voice WS] Câu đầu tiên sẵn sàng! Gửi audio_start tới ESP32 để phát loa ngay...")
                                await websocket.send_text(json.dumps({
                                    "event": "audio_start",
                                    "sample_rate": 44100
                                }))

                            total_streamed_bytes += len(pcm_chunk)
                            await websocket.send_bytes(pcm_chunk)

                        if audio_started:
                            logger.info(f"[Voice WS] Đã truyền xong toàn bộ {total_streamed_bytes} bytes PCM ra loa.")
                            await websocket.send_text(json.dumps({
                                "event": "audio_end",
                                "message": "Đã phát xong toàn bộ câu trả lời."
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                "status": "audio_error",
                                "message": "Không tạo được âm thanh trả lời."
                            }))

                    elif event == "select_doc":
                        new_doc_id = data.get("document_id")
                        if new_doc_id:
                            current_doc_id = new_doc_id
                            await websocket.send_text(json.dumps({
                                "status": "doc_switched",
                                "document_id": current_doc_id
                            }))

                except Exception as err:
                    logger.error(f"[Voice WS] Error processing control frame: {err}", exc_info=True)
                    await websocket.send_text(json.dumps({
                        "status": "error",
                        "message": str(err)
                    }))

            # 2. Received Binary Frame (Audio chunks from ESP32 mic)
            elif "bytes" in message:
                if is_recording:
                    pcm_buffer.extend(message["bytes"])

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"[WebSocket Voice] ESP32 đã ngắt kết nối: {current_doc_id}")
    except Exception as e:
        logger.error(f"[WebSocket Voice] Lỗi kết nối WebSocket: {e}", exc_info=True)
