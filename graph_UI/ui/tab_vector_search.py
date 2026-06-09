"""Vector Search tab — free-text similarity search across all KG node types."""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from db.vector_client import get_vector_resources, vector_search
from queries.schema import NODE_SCHEMA, NODE_COLORS
from queries.mappings import apply_mapping

_ALL_LABELS = ["All"] + list(NODE_SCHEMA.keys())

# Similarity threshold per node type.
# Edit these values to tune recall vs. precision for each label.
_THRESHOLDS: dict[str, float] = {
    "Breakthrough":   0.60,
    "UNESCOconcept":  0.60,
    "Platform":       0.6,
    "Emerging topic": 0.6,
    "SDGtarget":      0.6,
    "SDGgoal":        0.6,
    "SDGindicator":   0.6,
    "OECDfield":      0.6,
}

_NODE_ICONS: dict[str, str] = {
    "Breakthrough":   "💡",
    "UNESCOconcept":  "📚",
    "Platform":       "🏗️",
    "Emerging topic": "🌱",
    "SDGtarget":      "🎯",
    "SDGgoal":        "🌐",
    "SDGindicator":   "📊",
    "OECDfield":      "🔬",
}


def _group_by_concept(results: list[dict]) -> list[dict]:
    """Collapse UNESCOconcept results by pref_label_en, keeping max score."""
    groups: dict[str, dict] = {}
    for r in results:
        key = r.get("pref_label_en") or r.get("original_text", "—")
        if key not in groups:
            groups[key] = {"pref_label_en": key, "score": r["score"], "attrs": []}
        groups[key]["score"] = max(groups[key]["score"], r["score"])
        groups[key]["attrs"].append(
            {"attribute": r["attribute_name"], "text": r["original_text"], "score": r["score"]}
        )
    for g in groups.values():
        g["attrs"].sort(key=lambda a: a["score"], reverse=True)
    return sorted(groups.values(), key=lambda g: g["score"], reverse=True)


def _render_concept_groups(groups: list[dict], color: str) -> None:
    for g in groups:
        st.markdown(
            f'<div style="background:#fff; border:1px solid #dde2ec; border-radius:8px; padding:10px 14px; margin-bottom:8px;">'
            f'<div style="font-weight:600; margin-bottom:4px;">📚 {g["pref_label_en"]}'
            f'<span style="float:right; font-size:12px; color:#6b7280;">{g["score"]:.3f}</span></div>'
            + "".join(
                f'<div style="margin-top:4px; font-size:12px; color:#6b7280;">'
                f'<span style="color:{color};">{a["attribute"]}</span>'
                f' — {a["text"]}'
                f' <span style="float:right;">{a["score"]:.3f}</span></div>'
                for a in g["attrs"][:10]
            )
            + "</div>",
            unsafe_allow_html=True,
        )


_SHOW_NODE_ID_TYPES = {"SDGtarget", "SDGgoal", "SDGindicator"}


def _render_flat(results: list[dict]) -> None:
    for r in results:
        nt      = r["node_type"]
        color   = NODE_COLORS.get(nt, "#888")
        icon    = _NODE_ICONS.get(nt, "•")
        text    = r["original_text"] or "—"
        version = r.get("radar_version")
        node_id = r.get("node_id", "")
        version_tag = (
            f' <span style="font-size:11px; font-weight:400; color:#6b7280;">({version})</span>'
            if version else ""
        )
        node_id_tag = (
            f' <span style="font-size:11px; font-weight:400; color:#6b7280;">[{node_id}]</span>'
            if nt in _SHOW_NODE_ID_TYPES and node_id else ""
        )
        st.markdown(
            f'<div style="background:#fff; border:1px solid #dde2ec; border-radius:8px; padding:10px 14px; margin-bottom:8px;">'
            f'<div style="font-weight:600; margin-bottom:4px;">{icon} {text}{node_id_tag}{version_tag}'
            f'<span style="float:right; font-size:12px; color:#6b7280;">{r["score"]:.3f}</span></div>'
            f'<div style="font-size:12px; color:#6b7280;">'
            f'<b>type</b>: {nt} &nbsp;|&nbsp; '
            f'<b>attr</b>: {r["attribute_name"]} &nbsp;|&nbsp; '
            f'<b>id</b>: {r["node_id"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render() -> None:
    st.subheader("Vector Similarity Search")
    st.caption("Explore and find nodes in the graph using non-expert terms, works with most languages.")

    _, _, vec_err = get_vector_resources()
    if vec_err:
        st.error(f"Vector search unavailable: {vec_err}")
        return

    # ── Controls ──────────────────────────────────────────────────────────
    col_query, col_label = st.columns([3, 1])
    with col_query:
        query = st.text_input(
            "Natural language query",
            placeholder="e.g. climate change adaptation, neural interfaces, food security …",
            key="vs_query",
        )
    with col_label:
        label_choice = st.selectbox("Node type", _ALL_LABELS, key="vs_label")

    top_k = 5  # results shown per node type after grouping

    if not st.button("Search", type="primary", key="vs_run") or not query.strip():
        if not query.strip():
            st.info("Enter a query above and press **Search**.")
        return

    # ── Apply term mapping ────────────────────────────────────────────────
    search_term, was_mapped = apply_mapping(query)
    if was_mapped:
        st.caption(f"Searching as: *{search_term}*")

    # ── Run search ────────────────────────────────────────────────────────
    with st.spinner("Searching…"):
        if label_choice == "All":
            # Search each node type separately so no single type dominates the
            # global ranking (UNESCOconcept alone has ~10 embeddings per node).
            all_results: list[dict] = []
            errors: list[str] = []
            for nt in NODE_SCHEMA:
                nt_thresh = _THRESHOLDS.get(nt, 0.50)
                nt_res, nt_err = vector_search(
                    search_term,
                    top_k=top_k * 15,
                    threshold=nt_thresh,
                    node_label=nt,
                )
                if nt_err:
                    errors.append(f"{nt}: {nt_err}")
                else:
                    all_results.extend(nt_res)
            results = all_results
            err = "; ".join(errors) if errors else ""
        else:
            threshold = _THRESHOLDS.get(label_choice, 0.50)
            results, err = vector_search(
                search_term,
                top_k=top_k * 15,
                threshold=threshold,
                node_label=label_choice,
            )

    if err:
        st.error(err)
        return
    if not results:
        st.warning("No results above the similarity threshold.")
        return

    # ── Split and cap per node type ────────────────────────────────────────
    concept_results = [r for r in results if r["node_type"] == "UNESCOconcept"]
    other_results   = [r for r in results if r["node_type"] != "UNESCOconcept"]

    other_by_type: dict[str, list] = defaultdict(list)
    for r in other_results:
        if len(other_by_type[r["node_type"]]) < top_k:
            other_by_type[r["node_type"]].append(r)

    # ── Render ────────────────────────────────────────────────────────────
    if concept_results:
        groups = _group_by_concept(concept_results)[:top_k]
        color  = NODE_COLORS["UNESCOconcept"]
        st.markdown(
            f'<div class="section-header">📚 UNESCO Concepts — {len(groups)} result(s)</div>',
            unsafe_allow_html=True,
        )
        _render_concept_groups(groups, color)

    for nt, items in other_by_type.items():
        color = NODE_COLORS.get(nt, "#888")
        icon  = _NODE_ICONS.get(nt, "•")
        st.markdown(
            f'<div class="section-header" style="color:{color};">'
            f'{icon} {nt} — {len(items)} result(s)</div>',
            unsafe_allow_html=True,
        )
        _render_flat(items)
