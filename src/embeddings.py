"""
embeddings.py — Embedding interface backed by BAAI/bge-m3 (local or API).

Design:
  - EmbeddingModel (local) and APIEmbeddingModel (API) share duck-typed interface.
  - Local: runs fully offline via FlagEmbedding — no API calls.
  - API: OpenAI-compatible endpoint (EPFL RCP /v1/embeddings).
  - Query vs. document encoding are separate methods.
"""

from __future__ import annotations

import logging
from typing import Sequence

import httpx
import numpy as np

from src.models import Chunk

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Local embedding model using BAAI/bge-m3 via FlagEmbedding.

    Parameters
    ----------
    model_name : str
        HuggingFace model name or local path. Default: "BAAI/bge-m3".
    batch_size : int
        Batch size for encoding.
    dimension : int
        Dense embedding dimension (BGE-M3 = 1024).
    use_fp16 : bool
        Use fp16 precision for faster inference on GPU/CPU.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        batch_size: int = 32,
        dimension: int = 1024,
        use_fp16: bool = True,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.dimension = dimension

        logger.info("Loading BGE-M3 model: %s (dimension=%d)", model_name, dimension)
        from FlagEmbedding import BGEM3FlagModel
        self._model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        logger.info("BGE-M3 model loaded successfully.")

    # ------------------------------------------------------------------
    # Core encode
    # ------------------------------------------------------------------

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        """
        Encode a batch of texts into a (N, D) float32 numpy array using BGE-M3.
        """
        output = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return np.asarray(output["dense_vecs"], dtype=np.float32)

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query string → (D,) vector."""
        return self.encode_texts([query])[0]

    def encode_chunks(self, chunks: Sequence[Chunk]) -> np.ndarray:
        """Encode chunk texts → (N, D) array, aligned with the input list."""
        texts = [c.text for c in chunks]
        return self.encode_texts(texts)


class APIEmbeddingModel:
    """
    OpenAI-compatible embedding via HTTP API (e.g. EPFL RCP /v1/embeddings).

    Parameters
    ----------
    base_url : str
        API base URL, e.g. "https://inference.rcp.epfl.ch/v1".
    api_key : str
        Bearer token for Authorization header.
    model : str
        Model name sent in the request body, e.g. "BAAI/bge-m3".
    dimension : int
        Expected embedding dimension; stored as .dimension property.
    batch_size : int
        Max texts per API call.
    timeout : int
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "BAAI/bge-m3",
        dimension: int = 1024,
        batch_size: int = 32,
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self._dimension = dimension
        self._endpoint = f"{base_url}/embeddings"
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        logger.info("APIEmbeddingModel initialized: endpoint=%s, model=%s, dimension=%d",
                    self._endpoint, model, dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        """
        Encode texts using OpenAI-compatible /embeddings endpoint.

        Batches large inputs automatically per batch_size.
        Returns np.ndarray of shape (N, D).
        """
        texts = list(texts)
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                response = self._client.post(
                    self._endpoint,
                    json={"model": self.model, "input": batch},
                )
                response.raise_for_status()
            except httpx.TimeoutException as e:
                raise RuntimeError(f"Embedding API timeout: {e}") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"Embedding API error {e.response.status_code}: {e.response.text}"
                ) from e

            data = response.json()
            # Sort by index to guarantee order preservation across batches
            batch_embeddings = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            embeddings.extend([item["embedding"] for item in batch_embeddings])

        return np.asarray(embeddings, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query string → (D,) vector."""
        return self.encode_texts([query])[0]

    def encode_chunks(self, chunks: Sequence[Chunk]) -> np.ndarray:
        """Encode chunk texts → (N, D) array."""
        texts = [c.text for c in chunks]
        return self.encode_texts(texts)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_embedder(cfg: dict) -> EmbeddingModel | APIEmbeddingModel:
    """Build an EmbeddingModel (local or API) from the 'embeddings' section of config."""
    e = cfg["embeddings"]
    backend = e.get("backend", "local")

    if backend == "api":
        return APIEmbeddingModel(
            base_url=e["base_url"],
            api_key=e["api_key"],
            model=e.get("model_name", "BAAI/bge-m3"),
            dimension=e.get("dimension", 1024),
            batch_size=e.get("batch_size", 32),
            timeout=e.get("timeout", 120),
        )

    # default: "local"
    return EmbeddingModel(
        model_name=e.get("model_name", "BAAI/bge-m3"),
        batch_size=e.get("batch_size", 32),
        dimension=e.get("dimension", 1024),
        use_fp16=e.get("use_fp16", True),
    )
