"""Cached Neo4j connection for Streamlit."""
from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap paths before any project imports
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as _cfg  # noqa: F401  (side-effect: registers paths + loads .env)

import streamlit as st

from neo4j_graph import Neo4jConnection, QueryExecutor


@st.cache_resource(show_spinner=False)
def get_neo4j_resources() -> tuple[Neo4jConnection | None, QueryExecutor | None, str]:
    """Return a cached (connection, executor, error_msg) triple."""
    try:
        conn = Neo4jConnection()
        conn.connect()
        executor = QueryExecutor(conn.driver)
        return conn, executor, ""
    except Exception as exc:
        return None, None, str(exc)


def get_graph_summary() -> dict:
    conn, _, err = get_neo4j_resources()
    if conn is None:
        return {"connected": False, "error": err}
    try:
        summary = conn.get_summary()
        return {"connected": True, **summary}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
