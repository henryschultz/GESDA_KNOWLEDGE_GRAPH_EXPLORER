"""
Query Builder tab — iterative multi-hop Cypher explorer with optional vector search.

Each node in the path (start + every hop target) has an optional
'🔍 Filter this node' expander that runs a vector search and pins a specific
node value as a WHERE equality filter in the generated query.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from db.neo4j_client import get_neo4j_resources
from db.vector_client import vector_search
from queries.schema import NODE_SCHEMA, available_rels_from, cypher_label
from ui.styles import node_badge

MAX_HOPS = 5
_VALID = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")

_THRESHOLDS: dict[str, float] = {
    "UNESCOconcept":  0.55,
    "Breakthrough":   0.60,
    "Platform":       0.55,
    "Emerging topic": 0.55,
    "SDGtarget":      0.55,
    "SDGgoal":        0.45,
    "SDGindicator":   0.50,
    "OECDfield":      0.50,
}

_PLACEHOLDERS: dict[str, str] = {
    "UNESCOconcept":  "e.g. artificial intelligence",
    "Breakthrough":   "e.g. quantum computing",
    "Platform":       "e.g. digital",
    "Emerging topic": "e.g. AI governance",
    "SDGtarget":      "e.g. poverty reduction",
    "SDGgoal":        "e.g. quality education",
    "OECDfield":      "e.g. computer science",
}


def _alias(label: str, idx: int) -> str:
    slug = "".join(c if c in _VALID else "_" for c in label.lower())
    return f"n{idx}_{slug}"


def _display_prop(label: str) -> str:
    return NODE_SCHEMA.get(label, {}).get("display_prop", "name")


def _target_for(source: str, rel_type: str) -> str:
    for r in available_rels_from(source):
        if r["type"] == rel_type:
            return r["to"]
    return ""


def _first_hop(node: str) -> dict | None:
    rels = available_rels_from(node)
    if not rels:
        return None
    rel = rels[0]["type"]
    return {"rel": rel, "target": _target_for(node, rel)}


def _clear_vs_from(idx: int) -> None:
    """Drop vector-search session state for nodes at position idx and above."""
    for i in range(idx, MAX_HOPS + 2):
        st.session_state.pop(f"qb_vs_sel_{i}", None)
        st.session_state.pop(f"qb_vs_res_{i}", None)


def _read_vs_filters(n_nodes: int) -> dict[int, str]:
    """Read pinned vector-search values from session state for all current nodes."""
    return {
        i: v
        for i in range(n_nodes)
        if (v := st.session_state.get(f"qb_vs_sel_{i}", ""))
    }


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state() -> None:
    anchor = list(NODE_SCHEMA.keys())[0]
    hop = _first_hop(anchor)
    defaults: dict = {
        "qb_start": anchor,
        "qb_hops":  [hop] if hop else [],
        "qb_limit": 25,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Cypher generation
# ---------------------------------------------------------------------------

def _build_cypher(
    start: str,
    hops: list[dict],
    limit: int,
    vs_filters: dict[int, str],
) -> str:
    if not hops:
        return f"MATCH (n0:{cypher_label(start)})\nRETURN n0\nLIMIT {limit}"

    nodes = [start] + [h["target"] for h in hops]

    # MATCH chain
    chain = f"(n0:{cypher_label(nodes[0])})"
    for i, h in enumerate(hops):
        chain += f"-[r{i}:{h['rel']}]->(n{i+1}:{cypher_label(nodes[i+1])})"

    # WHERE from pinned vector-search values
    where_parts = []
    for idx in sorted(vs_filters):
        val = vs_filters[idx]
        if val and idx < len(nodes):
            safe = val.replace("'", "\\'")
            where_parts.append(f"n{idx}.{_display_prop(nodes[idx])} = '{safe}'")

    # RETURN
    ret_parts = [f"n0.{_display_prop(nodes[0])} AS {_alias(nodes[0], 0)}"]
    for i, h in enumerate(hops):
        ret_parts.append(f"type(r{i}) AS relationship_{i + 1}")
        ret_parts.append(f"n{i+1}.{_display_prop(nodes[i+1])} AS {_alias(nodes[i+1], i+1)}")

    lines = [f"MATCH {chain}"]
    if where_parts:
        lines.append("WHERE " + "\n  AND ".join(where_parts))
    lines.append(f"RETURN {', '.join(ret_parts)}")
    lines.append(f"LIMIT {limit}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _node_badge_line(label: str) -> None:
    st.markdown(f"→ {node_badge(label)}", unsafe_allow_html=True)


def _render_node_search(node_type: str, node_idx: int) -> None:
    """
    Render an optional vector-search picker for a node.
    Writes the selected value to qb_vs_sel_{node_idx} in session state.
    """
    sel_key = f"qb_vs_sel_{node_idx}"
    res_key = f"qb_vs_res_{node_idx}"
    selected = st.session_state.get(sel_key, "")

    # ── Already selected: show pinned badge + clear ─────────────────────────
    if selected:
        display  = st.session_state.get(f"{sel_key}_display", selected)
        version  = st.session_state.get(f"{sel_key}_version")
        version_suffix = f" ({version})" if version else ""
        col_val, col_clr = st.columns([5, 1])
        with col_val:
            st.success(f"🔍 **{display}**{version_suffix}")
        with col_clr:
            if st.button("✕", key=f"qb_vs_clr_{node_idx}"):
                st.session_state.pop(sel_key, None)
                st.session_state.pop(f"{sel_key}_display", None)
                st.session_state.pop(f"{sel_key}_version", None)
                st.session_state.pop(res_key, None)
                st.rerun()
        return

    # ── Not yet selected: expander with search UI ────────────────────────────
    with st.expander("🔍 Filter this node (optional)", expanded=False):
        search_term = st.text_input(
            "Search",
            placeholder=_PLACEHOLDERS.get(node_type, "keyword"),
            key=f"qb_vs_inp_{node_idx}",
            label_visibility="collapsed",
        )
        if st.button("Search", key=f"qb_vs_btn_{node_idx}", disabled=not search_term.strip()):
            threshold = _THRESHOLDS.get(node_type, 0.50)
            with st.spinner(f"Searching {node_type}…"):
                hits, err = vector_search(
                    search_term.strip(),
                    top_k=105,
                    threshold=threshold,
                    node_label=node_type,
                )
            if err:
                st.error(f"Search error: {err}")
            else:
                groups: dict[str, tuple[float, str | None, str | None]] = {}
                for r in hits:
                    lbl = r.get("pref_label_en") or r.get("original_text", "")
                    if lbl:
                        prev_score = groups.get(lbl, (0.0, None, None))[0]
                        if r["score"] > prev_score:
                            groups[lbl] = (r["score"], r.get("radar_version"), r.get("node_id"))
                top = sorted(groups.items(), key=lambda x: x[1][0], reverse=True)[:7]
                st.session_state[res_key] = top

        # Node types where node_id is a meaningful short identifier to show
        _SHOW_NODE_ID_TYPES = {"SDGtarget", "SDGgoal", "SDGindicator"}
        show_node_id = node_type in _SHOW_NODE_ID_TYPES

        top = st.session_state.get(res_key)
        if top is not None:
            if top:
                with st.container(height=180):
                    for j, (lbl, (score, version, node_id)) in enumerate(top):
                        version_suffix  = f"  ({version})" if version else ""
                        node_id_prefix  = f"[{node_id}]  " if show_node_id and node_id else ""
                        if st.button(
                            f"{node_id_prefix}{lbl}{version_suffix}  ·  {score:.3f}",
                            key=f"qb_vs_pick_{node_idx}_{j}",
                            use_container_width=True,
                        ):
                            st.session_state[sel_key] = lbl
                            st.session_state[f"{sel_key}_display"] = f"[{node_id}] {lbl}" if show_node_id and node_id else lbl
                            st.session_state[f"{sel_key}_version"] = version
                            st.session_state.pop(res_key, None)
                            st.rerun()
            else:
                st.caption("No results found above threshold.")


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render() -> None:
    st.subheader("Cypher Query Builder")
    st.caption(
        "Build a multi-hop path query step by step — up to 5 relationships. "
        "Optionally pin any node to a specific value via semantic search. "
        "The Cypher preview updates live."
    )

    _init_state()

    _, executor, neo4j_err = get_neo4j_resources()
    if executor is None:
        st.error(f"Neo4j unavailable: {neo4j_err}")
        return

    left, right = st.columns([2, 3])

    with left:
        # ── Starting node ────────────────────────────────────────────────────
        st.markdown("##### Starting node")
        labels = list(NODE_SCHEMA.keys())
        start = st.selectbox(
            "Node type", labels,
            index=labels.index(st.session_state.qb_start),
            key="qb_start_sel",
            label_visibility="collapsed",
        )
        if start != st.session_state.qb_start:
            st.session_state.qb_start = start
            hop = _first_hop(start)
            st.session_state.qb_hops = [hop] if hop else []
            _clear_vs_from(0)
            st.rerun()

        st.markdown(node_badge(start), unsafe_allow_html=True)
        _render_node_search(start, 0)

        hops: list[dict] = st.session_state.qb_hops

        if not hops:
            st.divider()
            st.warning(f"No outgoing relationships defined for **{start}** in the schema.")
        else:
            source = start
            for i, hop in enumerate(hops):
                st.divider()

                # Heading + ✕ on the last hop (not hop 0)
                if i > 0 and i == len(hops) - 1:
                    h_col, rm_col = st.columns([5, 1])
                    with h_col:
                        st.markdown(f"##### Relationship {i + 1}")
                    with rm_col:
                        if st.button("✕", key=f"qb_rm_{i}"):
                            st.session_state.qb_hops = hops[:i]
                            _clear_vs_from(i + 1)
                            st.rerun()
                else:
                    st.markdown(f"##### Relationship {i + 1}")

                rel_opts = [r["type"] for r in available_rels_from(source)]
                if not rel_opts:
                    st.warning(f"No outgoing relationships from **{source}**.")
                    break

                cur = hop["rel"] if hop["rel"] in rel_opts else rel_opts[0]
                new_rel = st.selectbox(
                    "rel", rel_opts,
                    index=rel_opts.index(cur),
                    key=f"qb_rel_{i}",
                    label_visibility="collapsed",
                )
                if new_rel != hop["rel"]:
                    st.session_state.qb_hops[i] = {
                        "rel": new_rel,
                        "target": _target_for(source, new_rel),
                    }
                    st.session_state.qb_hops = st.session_state.qb_hops[:i + 1]
                    _clear_vs_from(i + 1)
                    st.rerun()

                target = hop["target"]
                if target not in NODE_SCHEMA:
                    st.warning("Target not found in schema.")
                    break

                _node_badge_line(target)
                _render_node_search(target, i + 1)
                source = target

            # ── ADD RELATIONSHIP ─────────────────────────────────────────────
            last_target = hops[-1]["target"]
            next_rels = available_rels_from(last_target)

            if len(hops) >= MAX_HOPS:
                st.divider()
                st.caption(f"Maximum of {MAX_HOPS} relationships reached.")
            elif next_rels and last_target in NODE_SCHEMA:
                st.divider()
                st.markdown("##### ＋ Add relationship")
                next_opts = [r["type"] for r in next_rels]
                next_rel = st.selectbox(
                    "rel", next_opts,
                    key="qb_next_rel",
                    label_visibility="collapsed",
                )
                next_tgt = _target_for(last_target, next_rel)
                if next_tgt in NODE_SCHEMA:
                    _node_badge_line(next_tgt)
                if st.button("Add →", key="qb_add_hop") and next_tgt in NODE_SCHEMA:
                    st.session_state.qb_hops.append({"rel": next_rel, "target": next_tgt})
                    st.rerun()

        # ── Limit ─────────────────────────────────────────────────────────────
        st.divider()
        limit = st.number_input(
            "Limit", min_value=1, max_value=500,
            value=st.session_state.qb_limit,
            key="qb_limit_input",
        )
        st.session_state.qb_limit = int(limit)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    with right:
        st.markdown("##### Query preview")

        hops = st.session_state.qb_hops
        n_nodes = len(hops) + 1
        vs_filters = _read_vs_filters(n_nodes)
        cypher = _build_cypher(start, hops, int(st.session_state.qb_limit), vs_filters)
        st.code(cypher, language="cypher")

        col_run, col_reset = st.columns([2, 1])
        with col_run:
            run = st.button("▶ Run query", type="primary", key="qb_run")
        with col_reset:
            if st.button("↺ Reset", key="qb_reset"):
                for k in ["qb_start", "qb_hops", "qb_limit"]:
                    st.session_state.pop(k, None)
                _clear_vs_from(0)
                st.rerun()

        if run:
            with st.spinner("Running query…"):
                try:
                    results = executor.query_custom(cypher)
                except Exception as exc:
                    st.error(f"Query error: {exc}")
                    return

            if not results:
                st.info("Query returned no results.")
                return

            st.success(f"**{len(results)}** row(s) returned")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True, height=400)

            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
            )
