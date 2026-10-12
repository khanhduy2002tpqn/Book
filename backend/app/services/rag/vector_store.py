import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from app.config import settings
from app.services.embedding import embedding_service
from app.services.pdf.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    _instance = None
    _client: Optional[QdrantClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantVectorStore, cls).__new__(cls)
        return cls._instance

    def _get_client(self) -> QdrantClient:
        if self._client is not None:
            return self._client

        # Try connecting to Qdrant URL if configured
        if settings.QDRANT_URL:
            try:
                client = QdrantClient(url=settings.QDRANT_URL, timeout=5)
                # Test connectivity
                client.get_collections()
                logger.info(f"Connected to remote Qdrant server at {settings.QDRANT_URL}")
                self._client = client
                return self._client
            except Exception as e:
                logger.warning(
                    f"Remote Qdrant server at {settings.QDRANT_URL} is unreachable ({e}). "
                    f"Falling back to embedded local storage at '{settings.QDRANT_LOCAL_PATH}'."
                )

        # Fallback to local on-disk embedded Qdrant storage (No Docker required!)
        os.makedirs(settings.QDRANT_LOCAL_PATH, exist_ok=True)
        self._client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
        logger.info(f"Initialized local embedded Qdrant storage at {settings.QDRANT_LOCAL_PATH}")
        return self._client

    def ensure_collection(self, vector_size: int = 1024):
        client = self._get_client()
        collections = client.get_collections().collections
        exists = any(c.name == settings.QDRANT_COLLECTION_NAME for c in collections)
        if not exists:
            logger.info(f"Creating Qdrant collection: {settings.QDRANT_COLLECTION_NAME} (size={vector_size})")
            client.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=rest.VectorParams(
                    size=vector_size,
                    distance=rest.Distance.COSINE
                )
            )

    def insert_chunks(self, document_id: str, chunks: List[DocumentChunk]) -> List[str]:
        """
        Embed and insert document chunks into Qdrant collection.
        Returns list of point IDs.
        """
        if not chunks:
            return []

        client = self._get_client()
        dim = embedding_service.vector_dimension
        self.ensure_collection(vector_size=dim)

        texts = [c.text for c in chunks]
        embeddings = embedding_service.embed_texts(texts)

        points = []
        point_ids = []
        for chunk, vector in zip(chunks, embeddings):
            p_id = str(uuid.uuid4())
            point_ids.append(p_id)
            payload = {
                "document_id": document_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "page": chunk.page,
                "chapter": chunk.chapter or "",
                "text": chunk.text,
                "source_type": chunk.source_type,
                "token_count": chunk.token_count
            }
            points.append(
                rest.PointStruct(
                    id=p_id,
                    vector=vector,
                    payload=payload
                )
            )

        # Batch upsert in sizes of 64
        batch_size = 64
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=batch
            )

        logger.info(f"Upserted {len(points)} chunks into Qdrant for document {document_id}")
        return point_ids

    def search_similar_chunks(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for top K chunks relevant to query for a specific document.
        Filter by document_id.
        """
        if threshold is None:
            threshold = settings.SIMILARITY_THRESHOLD

        client = self._get_client()
        query_vector = embedding_service.embed_query(query)

        filter_condition = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="document_id",
                    match=rest.MatchValue(value=document_id)
                )
            ]
        )

        if hasattr(client, "query_points"):
            query_response = client.query_points(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query=query_vector,
                query_filter=filter_condition,
                limit=top_k,
                score_threshold=threshold
            )
            hits = query_response.points
        elif hasattr(client, "search"):
            hits = client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=filter_condition,
                limit=top_k,
                score_threshold=threshold
            )
        else:
            hits = []

        matched_chunks: List[Dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            matched_chunks.append({
                "point_id": hit.id,
                "chunk_id": payload.get("chunk_id", ""),
                "page": payload.get("page", 1),
                "chapter": payload.get("chapter"),
                "text": payload.get("text", ""),
                "source_type": payload.get("source_type", "text"),
                "score": float(hit.score)
            })

        return matched_chunks

    def delete_document_vectors(self, document_id: str):
        """
        Remove all vectors associated with a document_id.
        """
        try:
            client = self._get_client()
            client.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="document_id",
                                match=rest.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            logger.info(f"Deleted vectors for document {document_id} from Qdrant")
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")


vector_store = QdrantVectorStore()
