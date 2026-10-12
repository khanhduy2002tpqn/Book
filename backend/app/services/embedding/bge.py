import logging
from typing import List
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {settings.EMBEDDING_MODEL}")
                self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info("Embedding model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load embedding model {settings.EMBEDDING_MODEL}: {e}")
                # Fallback to standard lightweight model if bge-m3 is not yet cached or fails
                try:
                    from sentence_transformers import SentenceTransformer
                    fallback_name = "sentence-transformers/all-MiniLM-L6-v2"
                    logger.warning(f"Falling back to {fallback_name}...")
                    self._model = SentenceTransformer(fallback_name)
                except Exception as fallback_err:
                    logger.error(f"Failed to load fallback embedding model: {fallback_err}")
                    raise RuntimeError(f"Could not initialize any embedding model: {e}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of text strings into normalized vectors.
        """
        if not texts:
            return []

        self._load_model()
        # SentenceTransformers encode with normalize_embeddings=True for cosine similarity
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single search query string.
        """
        results = self.embed_texts([query])
        return results[0] if results else []

    @property
    def vector_dimension(self) -> int:
        self._load_model()
        if self._model:
            return self._model.get_sentence_embedding_dimension()
        return 1024


embedding_service = EmbeddingService()
