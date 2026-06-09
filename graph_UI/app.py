"""
GESDA Knowledge Graph Explorer — Streamlit entry point.

Run with:
    streamlit run graphrag_UI/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure graphrag_UI/ is on the path for relative imports inside the package
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import streamlit as st

import config  # noqa: F401 — bootstraps project paths + loads .env
from config import APP_TITLE, APP_ICON
from db.neo4j_client import get_neo4j_resources, get_graph_summary
from db.vector_client import get_vector_resources
from queries.schema import NODE_COLORS
from ui.styles import inject_css
import ui.tab_vector_search as tab_vs
import ui.tab_hardcoded as tab_hq
import ui.tab_query_builder as tab_qb

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="padding: 16px 0 8px 0;">
        <span style="font-size:28px; font-weight:800; color:#1a1e2a;">
            🔬 GESDA Knowledge Graph Explorer
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — connection status
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Connection")

    # Neo4j
    summary = get_graph_summary()
    if summary.get("connected"):
        st.markdown(
            '<span class="status-dot ok"></span> **Neo4j** connected',
            unsafe_allow_html=True,
        )
        with st.expander("Graph statistics", expanded=False):
            st.metric("Total nodes", f'{summary["total_nodes"]:,}')
            st.metric("Total relationships", f'{summary["total_relationships"]:,}')
            nt = summary.get("node_types", {})
            if nt:
                rows = sorted(nt.items(), key=lambda x: x[1], reverse=True)
                for label, cnt in rows:
                    color = NODE_COLORS.get(label, "#888")
                    st.markdown(
                        f'<span style="color:{color}; font-size:12px;">● {label}: {cnt:,}</span>',
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            f'<span class="status-dot err"></span> **Neo4j** — {summary.get("error", "unavailable")}',
            unsafe_allow_html=True,
        )

    # Vector search
    _, _, vec_err = get_vector_resources()
    if not vec_err:
        st.markdown(
            '<span class="status-dot ok"></span> **Vector search** ready',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-dot warn"></span> **Vector search** unavailable',
            unsafe_allow_html=True,
        )
        with st.expander("Details", expanded=False):
            st.caption(vec_err)

    st.divider()
    st.markdown(
        """
        **Tabs**
        - **Hardcoded Queries** - examples of graph capabilities and explore the relationships
        - **Vector Search** — find nodes using non-jargon language
        - **Query Builder** — interactive Cypher builder
        """,
        unsafe_allow_html=False,
    )
    st.divider()
    st.caption("GESDA · EPFL · 2026")

# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------

tab_hard, tab_vec, tab_build = st.tabs([
    "🔎 Hardcoded Queries",
    "🔭 Vector Search",
    "🛠️ Query Builder",
])

with tab_hard:
    tab_hq.render()

with tab_vec:
    tab_vs.render()

with tab_build:
    tab_qb.render()
