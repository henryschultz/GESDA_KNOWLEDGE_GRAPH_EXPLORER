"""
Search term mappings — applied before embedding wherever vector search occurs.

Keys are lowercase; the lookup is case-insensitive.
When a user's query matches a key, the mapped value is sent to the embedder
instead, so abbreviations and acronyms get a richer representation.

Edit QUERY_MAPPINGS freely — no other file needs to change.
"""
from __future__ import annotations

QUERY_MAPPINGS: dict[str, str] = {
    "ai":       "artificial intelligence",
    "ki":       "Künstliche Intelligenz",
    "ml":       "machine learning",
    "dl":       "deep learning",
    "nlp":      "natural language processing",
    "cv":       "computer vision",
    "rl":       "reinforcement learning",
    "llm":      "large language model",
    "crispr":   "gene editing",
}


def apply_mapping(term: str) -> tuple[str, bool]:
    """
    Return (mapped_term, was_mapped).

    Looks up term.strip().lower() in QUERY_MAPPINGS.
    If found, returns the mapped value and True.
    Otherwise returns the original stripped term and False.
    """
    stripped = term.strip()
    mapped = QUERY_MAPPINGS.get(stripped.lower())
    if mapped:
        return mapped, True
    return stripped, False
