"""Cached vector-search client for Streamlit (Qdrant + EPFL API embedder)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as _cfg  # noqa: F401

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def get_vector_resources():
    """Return cached (embedder, qdrant_store, error_msg)."""
    try:
        from src.config import load_config
        from src.embeddings import build_embedder
        from src.qdrant_store import QdrantStore

        cfg = load_config(config_path=str(_cfg.PROJECT_ROOT / "config" / "config.yaml"))

        embedder = build_embedder(cfg)
        qdrant = QdrantStore(
            mode=cfg["qdrant"].get("mode", "local"),
            local_path=cfg["qdrant"].get("local_path"),
            url=cfg["qdrant"].get("url"),
            host=cfg["qdrant"].get("host", "localhost"),
            port=cfg["qdrant"].get("port", 6333),
            api_key=cfg["qdrant"].get("api_key"),
            collection_name=_cfg.KG_NODES_COLLECTION,
            distance=cfg["qdrant"].get("distance", "cosine"),
            vector_dim=cfg["embeddings"]["dimension"],
        )
        return embedder, qdrant, ""
    except Exception as exc:
        logger.warning("Vector search unavailable: %s", exc)
        return None, None, str(exc)


def vector_search(
    query: str,
    top_k: int = 20,
    threshold: float = 0.5,
    node_label: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Run a vector similarity search against the kg_nodes Qdrant collection.

    Returns (results, error_message). Results are empty on error.
    If node_label is provided, filters results to that label only.
    """
    embedder, qdrant, err = get_vector_resources()
    if embedder is None:
        return [], err

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_filter = None
        if node_label:
            query_filter = Filter(
                must=[FieldCondition(key="node_type", match=MatchValue(value=node_label))]
            )

        query_vec = embedder.encode_query(query)
        hits = qdrant.search(
            query_vec,
            top_k=top_k,
            score_threshold=threshold,
            query_filter=query_filter,
        )

        results = []
        for h in hits:
            p = h.get("payload", {})
            results.append({
                "score": round(h["score"], 4),
                "node_type": p.get("node_type", ""),
                "node_id": p.get("node_id", ""),
                "attribute_name": p.get("attribute_name", ""),
                "original_text": p.get("original_text", ""),
                "pref_label_en": p.get("pref_label_en", ""),
                "radar_version": p.get("radar_version"),
            })
        return results, ""
    except Exception as exc:
        return [], str(exc)
