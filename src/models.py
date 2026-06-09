"""
models.py — Core data models for the RAG pipeline.

Uses dataclasses for clarity and minimal overhead. These models define the
contracts between pipeline stages (loader → chunker → embedder → store → retriever).

Design note: We use dataclasses rather than Pydantic here because the pipeline
is internal Python; if we later expose an HTTP API, Pydantic models can wrap
these or replace them with minimal effort.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Document — output of the document loader
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """A single ingested document before chunking."""

    doc_id: str
    source_path: str
    title: str
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_id() -> str:
        return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Chunk — output of the chunker
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A text chunk derived from a Document, ready for embedding."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_id(doc_id: str, chunk_index: int) -> str:
        """Deterministic chunk ID from doc + index."""
        return f"{doc_id}::{chunk_index}"


# ---------------------------------------------------------------------------
# RetrievalResult — a single retrieved chunk with its similarity score
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """One retrieved chunk returned by the vector store search."""

    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# GeneratedAnswer — the generator's output for one query
# ---------------------------------------------------------------------------

@dataclass
class GeneratedAnswer:
    """Wraps the generator response together with provenance info."""

    query: str
    answer: str
    retrieved_chunks: list[RetrievalResult]
    prompt_text: str | None = None       # stored when debug=True
    model: str | None = None
    usage: dict[str, Any] | None = None  # token counts if returned by API


# ---------------------------------------------------------------------------
# EvalExample — one row of an evaluation dataset
# ---------------------------------------------------------------------------

@dataclass
class EvalExample:
    """Schema for a single evaluation question."""

    question: str
    expected_answer: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    reference_context_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# EvalResult — one evaluated example (question + answer + metrics)
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    """Stores the pipeline output and basic metrics for one eval example."""

    question: str
    expected_answer: str | None
    generated_answer: str
    retrieved_chunk_ids: list[str]
    retrieved_scores: list[float]
    keyword_hits: dict[str, bool] = field(default_factory=dict)
    context_recall: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
