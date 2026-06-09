"""
qdrant_store.py — Qdrant vector store abstraction.

Supports two modes (controlled by config):
  - "local": embedded Qdrant with on-disk persistence (no server needed).
  - "remote": connects to a Qdrant server via host:port (or cloud with API key).

The store handles collection lifecycle (create / recreate), upserting points
with payloads, and searching. It deliberately does NOT embed texts — that
responsibility stays with the embedding module, keeping concerns separated.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

_DISTANCE_MAP = {
    "cosine": Distance.COSINE,
    "euclid": Distance.EUCLID,
    "dot": Distance.DOT,
}


class QdrantStore:
    """
    Thin abstraction over qdrant-client.

    Parameters
    ----------
    mode : str
        "local" (embedded, file-backed) or "remote" (server).
    local_path : str | None
        Disk path for local mode.
    host : str
        Qdrant server host (remote mode).
    port : int
        Qdrant server port (remote mode).
    api_key : str | None
        API key for Qdrant Cloud (remote mode).
    collection_name : str
        Name of the vector collection.
    distance : str
        Distance metric ("cosine", "euclid", "dot").
    vector_dim : int
        Dimensionality of vectors to store.
    """

    def __init__(
        self,
        mode: str = "local",
        local_path: str | None = None,
        url: str | None = None,
        host: str = "localhost",
        port: int = 6333,
        api_key: str | None = None,
        collection_name: str = "documents",
        distance: str = "cosine",
        vector_dim: int = 384,
    ) -> None:
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self.distance = _DISTANCE_MAP.get(distance, Distance.COSINE)

        if mode == "local":
            logger.info("Connecting to Qdrant in local/embedded mode: %s", local_path)
            self._client = QdrantClient(path=local_path)
        elif url:
            logger.info("Connecting to Qdrant Cloud at %s", url)
            self._client = QdrantClient(url=url, api_key=api_key)
        else:
            logger.info("Connecting to Qdrant server at %s:%d", host, port)
            self._client = QdrantClient(host=host, port=port, api_key=api_key)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def ensure_collection(self, recreate: bool = False) -> None:
        """
        Create the collection if it doesn't exist.
        If *recreate* is True, drop and recreate it (useful during re-indexing).
        """
        exists = self._client.collection_exists(self.collection_name)

        if exists and recreate:
            logger.warning("Recreating collection '%s'", self.collection_name)
            self._client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dim,
                    distance=self.distance,
                ),
            )
            logger.info(
                "Created collection '%s' (dim=%d, distance=%s)",
                self.collection_name, self.vector_dim, self.distance,
            )
        else:
            logger.info("Collection '%s' already exists", self.collection_name)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_batch(
        self,
        ids: Sequence[str],
        vectors: np.ndarray,
        payloads: Sequence[dict[str, Any]],
    ) -> None:
        """
        Insert or update a batch of points.

        Parameters
        ----------
        ids : list of str
            Unique point identifiers (we use chunk_id).
        vectors : np.ndarray, shape (N, D)
            Embedding vectors.
        payloads : list of dict
            Metadata payloads (one per point).
        """
        points = [
            PointStruct(
                id=idx,       # Qdrant accepts str UUIDs or ints.
                vector=vec.tolist(),
                payload=pay,
            )
            for idx, (vec, pay) in enumerate(zip(vectors, payloads))
        ]

        # Qdrant's upsert with named IDs requires string UUID or int ids.
        # We'll use positional int IDs and store our chunk_id in the payload.
        # Instead, let's hash chunk_id to a stable int for the point ID.
        import hashlib
        points = []
        for cid, vec, pay in zip(ids, vectors, payloads):
            # Deterministic 64-bit int from chunk_id
            h = int(hashlib.sha256(cid.encode()).hexdigest()[:16], 16)
            points.append(
                PointStruct(id=h, vector=vec.tolist(), payload=pay)
            )

        self._client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.debug("Upserted %d points into '%s'", len(points), self.collection_name)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        score_threshold: float | None = None,
        query_filter: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Search the collection for nearest neighbours.

        Returns a list of dicts with keys: id, score, payload.
        The *query_filter* param is a placeholder for Qdrant filter objects
        (to be used when we add metadata filtering later).
        """
        results = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector.tolist(),
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        ).points

        hits: list[dict[str, Any]] = []
        for r in results:
            hits.append({
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            })
        return hits

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def collection_info(self) -> dict[str, Any]:
        info = self._client.get_collection(self.collection_name)
        result: dict[str, Any] = {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": str(info.status),
        }
        # vectors_count was removed in newer qdrant-client versions
        if hasattr(info, "vectors_count"):
            result["vectors_count"] = info.vectors_count
        return result

    def close(self) -> None:
        """Close the client connection (relevant for local mode flush)."""
        self._client.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_qdrant_store(cfg: dict, vector_dim: int | None = None) -> QdrantStore:
    """
    Build a QdrantStore from the config dict.

    If *vector_dim* is not given, uses the value from cfg["embeddings"]["dimension"].
    """
    q = cfg["qdrant"]
    dim = vector_dim or cfg["embeddings"]["dimension"]
    return QdrantStore(
        mode=q.get("mode", "local"),
        local_path=q.get("local_path"),
        host=q.get("host", "localhost"),
        port=q.get("port", 6333),
        api_key=q.get("api_key"),
        collection_name=q.get("collection_name", "documents"),
        distance=q.get("distance", "cosine"),
        vector_dim=dim,
    )
