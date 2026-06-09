"""Custom CSS for the GESDA KG Explorer."""
from __future__ import annotations

import streamlit as st

from queries.schema import NODE_COLORS


def inject_css() -> None:
    badge_rules = "\n".join(
        f'.badge-{label.replace(" ", "-")} '
        f'{{ background-color: {color}22; color: {color}; border: 1px solid {color}55; }}'
        for label, color in NODE_COLORS.items()
    )

    st.markdown(
        f"""
        <style>
        /* ── Global ── */
        [data-testid="stAppViewContainer"] {{
            background-color: #f5f7fa;
        }}
        [data-testid="stSidebar"] {{
            background-color: #eef1f6;
        }}
        h1, h2, h3 {{
            font-weight: 700 !important;
            color: #1a1e2a !important;
        }}

        /* ── Node-type badges ── */
        .badge {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.4px;
            margin-right: 4px;
        }}
        {badge_rules}

        /* ── Score bar ── */
        .score-bar-wrap {{
            background: #dde2ec;
            border-radius: 4px;
            height: 6px;
            overflow: hidden;
        }}
        .score-bar {{
            height: 6px;
            border-radius: 4px;
            background: linear-gradient(90deg, #3498db, #2ecc71);
        }}

        /* ── Result card ── */
        .result-card {{
            background: #ffffff;
            border: 1px solid #dde2ec;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
        }}
        .result-card:hover {{
            border-color: #3498db88;
            box-shadow: 0 2px 8px rgba(52,152,219,0.08);
        }}
        .result-title {{
            font-size: 14px;
            font-weight: 600;
            color: #1a1e2a;
            margin-bottom: 4px;
        }}
        .result-meta {{
            font-size: 12px;
            color: #6b7280;
        }}

        /* ── Concept group card ── */
        .concept-group {{
            background: #ffffff;
            border: 1px solid #dde2ec;
            border-left: 3px solid #3498DB;
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 6px;
        }}
        .concept-label {{
            font-size: 14px;
            font-weight: 600;
            color: #1a1e2a;
        }}
        .concept-attrs {{
            font-size: 12px;
            color: #6b7280;
            margin-top: 4px;
        }}

        /* ── Cypher block ── */
        .cypher-block {{
            background: #f0f2f8;
            border: 1px solid #dde2ec;
            border-left: 3px solid #f39c12;
            border-radius: 6px;
            padding: 12px 16px;
            font-family: 'Fira Mono', 'Consolas', monospace;
            font-size: 13px;
            color: #1a1e2a;
            white-space: pre-wrap;
            word-break: break-all;
        }}

        /* ── Section header ── */
        .section-header {{
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #6b7280;
            margin: 16px 0 8px 0;
        }}

        /* ── Status dot ── */
        .status-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }}
        .status-dot.ok   {{ background-color: #2ecc71; }}
        .status-dot.err  {{ background-color: #e74c3c; }}
        .status-dot.warn {{ background-color: #f39c12; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def node_badge(label: str) -> str:
    css_class = f"badge badge-{label.replace(' ', '-')}"
    return f'<span class="{css_class}">{label}</span>'


def score_bar(score: float, color: str = "#3498db") -> str:
    pct = int(score * 100)
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar" style="width:{pct}%; background:{color};"></div>'
        f'</div>'
    )
