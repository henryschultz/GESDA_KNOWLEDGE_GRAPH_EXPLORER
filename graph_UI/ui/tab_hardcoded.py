"""
Hardcoded Queries tab — runs QueryExecutor methods against Neo4j.

Query definitions live in queries/hardcoded.py.  Each entry declares which
QueryExecutor method to call and what UI inputs to render.  No code changes
are needed here when adding new queries.

Special input type "node_picker":
    Runs a vector search on the user's term for a given node_type, shows a
    scrollable list of matches, and on click loads the selected label and
    auto-triggers the main query.

    Required field in input spec:
        node_type : Neo4j label to search (e.g. "UNESCOconcept", "Breakthrough")
    Optional fields:
        top_k     : number of candidates shown (default 7)
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from db.neo4j_client import get_neo4j_resources
from db.vector_client import vector_search
from queries.hardcoded import HARDCODED_QUERIES
from queries.mappings import apply_mapping


# Per-type defaults used by the node picker
_PICKER_ICONS: dict[str, str] = {
    "UNESCOconcept":  "📚",
    "Breakthrough":   "💡",
    "Platform":       "🏗️",
    "Emerging topic": "🌱",
    "SDGtarget":      "🎯",
    "SDGgoal":        "🌐",
    "SDGindicator":   "📊",
    "OECDfield":      "🔬",
}

_PICKER_THRESHOLDS: dict[str, float] = {
    "UNESCOconcept":  0.55,
    "Breakthrough":   0.60,
    "Platform":       0.55,
    "Emerging topic": 0.55,
    "SDGtarget":      0.55,
    "SDGgoal":        0.45,
    "SDGindicator":   0.50,
    "OECDfield":      0.50,
}


# ---------------------------------------------------------------------------
# Node picker (vector search → scrollable results → click to select)
# ---------------------------------------------------------------------------

def _render_node_picker(inp: dict, query_id: str) -> str:
    """
    Render a vector-search-backed node picker for any node_type.
    Returns the selected label string, or '' if nothing is selected yet.
    Side-effect: sets session_state[f"hq_{query_id}_auto_run"] = True on click.
    """
    node_type = inp["node_type"]
    icon      = _PICKER_ICONS.get(node_type, "•")
    threshold = _PICKER_THRESHOLDS.get(node_type, 0.50)

    key_base     = f"hq_{query_id}_{inp['key']}"
    selected_key = f"{key_base}_selected"
    results_key  = f"{key_base}_results"

    selected = st.session_state.get(selected_key, "")

    # ── Already selected → show badge + clear button ──────────────────────
    if selected:
        display = st.session_state.get(f"{selected_key}_display", selected)
        version = st.session_state.get(f"{selected_key}_version")
        version_suffix = f" ({version})" if version else ""
        col_sel, col_clr = st.columns([5, 1])
        with col_sel:
            st.success(f"{icon} **{display}**{version_suffix}")
        with col_clr:
            if st.button("✕ Clear", key=f"{key_base}_clear"):
                st.session_state.pop(selected_key, None)
                st.session_state.pop(f"{selected_key}_display", None)
                st.session_state.pop(f"{selected_key}_version", None)
                st.session_state.pop(results_key, None)
                st.rerun()
        return selected

    # ── Search input ──────────────────────────────────────────────────────
    search_term = st.text_input(
        inp.get("label", f"Search for a {node_type}"),
        placeholder=inp.get("placeholder", ""),
        key=f"{key_base}_search_input",
    )

    if st.button("Search", key=f"{key_base}_search_btn", disabled=not search_term.strip()):
        mapped_term, was_mapped = apply_mapping(search_term)
        st.session_state[f"{key_base}_mapped"] = mapped_term if was_mapped else ""
        with st.spinner(f"Searching {node_type}…"):
            results, err = vector_search(
                mapped_term,
                top_k=inp.get("top_k", 7) * 15,
                threshold=threshold,
                node_label=node_type,
            )
        if err:
            st.error(f"Vector search error: {err}")
            return ""
        # Deduplicate: prefer pref_label_en, fall back to original_text
        # Store (score, radar_version, node_id) per label
        value_prop    = inp.get("value_prop")      # if set, use this field as stored value
        display_node_id = inp.get("display_node_id", False)  # show node_id as prefix in button/badge
        groups: dict[str, tuple[float, str | None, str | None]] = {}
        for r in results:
            lbl = r.get("pref_label_en") or r.get("original_text", "")
            if lbl:
                prev_score = groups.get(lbl, (0.0, None, None))[0]
                if r["score"] > prev_score:
                    groups[lbl] = (r["score"], r.get("radar_version"), r.get("node_id"))
        top = sorted(groups.items(), key=lambda x: x[1][0], reverse=True)[: inp.get("top_k", 7)]
        st.session_state[results_key] = top

    # ── Scrollable results ────────────────────────────────────────────────
    value_prop      = inp.get("value_prop")
    display_node_id = inp.get("display_node_id", False)
    mapped_label = st.session_state.get(f"{key_base}_mapped", "")
    if mapped_label:
        st.caption(f"Searched as: *{mapped_label}*")

    top = st.session_state.get(results_key)
    if top is not None:
        if top:
            with st.container(height=220):
                for i, (lbl, (score, version, node_id)) in enumerate(top):
                    version_suffix  = f"  ({version})" if version else ""
                    node_id_prefix  = f"[{node_id}]  " if display_node_id and node_id else ""
                    stored_value    = node_id if value_prop == "node_id" and node_id else lbl
                    if st.button(
                        f"{icon} {node_id_prefix}{lbl}{version_suffix}  ·  {score:.3f}",
                        key=f"{key_base}_pick_{i}",
                        use_container_width=True,
                    ):
                        st.session_state[selected_key] = stored_value
                        st.session_state[f"{selected_key}_display"] = f"[{node_id}] {lbl}" if display_node_id and node_id else lbl
                        st.session_state[f"{selected_key}_version"] = version
                        st.session_state[f"hq_{query_id}_auto_run"] = True
                        st.rerun()
        else:
            st.warning(f"No {node_type} nodes found above threshold.")

    return ""


# ---------------------------------------------------------------------------
# Generic input collection
# ---------------------------------------------------------------------------

def _collect_inputs(query_def: dict) -> tuple[dict, bool]:
    """Render input widgets and return (collected_kwargs, all_required_filled)."""
    collected: dict = {}
    all_filled = True

    concept_inputs = [i for i in query_def["inputs"] if i["type"] == "node_picker"]
    text_inputs    = [i for i in query_def["inputs"] if i["type"] == "text"]
    other_inputs   = [i for i in query_def["inputs"] if i["type"] not in ("text", "node_picker")]

    # Node pickers (full width, vector-search backed)
    for inp in concept_inputs:
        val = _render_node_picker(inp, query_def["id"])
        collected[inp["key"]] = val
        if not val:
            all_filled = False

    # Plain text inputs
    for inp in text_inputs:
        val = st.text_input(
            inp["label"],
            placeholder=inp.get("placeholder", ""),
            help=inp.get("help"),
            key=f'hq_{query_def["id"]}_{inp["key"]}',
        )
        collected[inp["key"]] = val
        if not val.strip():
            all_filled = False

    # Selects / checkboxes / numbers — rendered in a single row of columns
    if other_inputs:
        cols = st.columns(len(other_inputs))
        for col, inp in zip(cols, other_inputs):
            with col:
                if inp["type"] == "select":
                    opts = inp["options"]
                    idx = opts.index(inp["default"]) if inp["default"] in opts else 0
                    opt_labels = inp.get("option_labels", {})
                    collected[inp["key"]] = st.selectbox(
                        inp["label"], opts, index=idx,
                        format_func=lambda v, _m=opt_labels: _m.get(v, str(v)),
                        help=inp.get("help"),
                        key=f'hq_{query_def["id"]}_{inp["key"]}',
                    )
                elif inp["type"] == "checkbox":
                    collected[inp["key"]] = st.checkbox(
                        inp["label"], value=inp["default"],
                        help=inp.get("help"),
                        key=f'hq_{query_def["id"]}_{inp["key"]}',
                    )
                elif inp["type"] == "number":
                    collected[inp["key"]] = int(st.number_input(
                        inp["label"],
                        min_value=inp.get("min", 1),
                        max_value=inp.get("max", 500),
                        value=inp["default"],
                        help=inp.get("help"),
                        key=f'hq_{query_def["id"]}_{inp["key"]}',
                    ))

    return collected, all_filled


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _flatten_results(results: list[dict]) -> list[dict]:
    """Convert list values to comma-separated strings for dataframe display.
    Also folds radar_version into breakthrough_name where present."""
    flat = []
    for row in results:
        flat_row = {
            k: (", ".join(str(x) for x in v) if isinstance(v, list) else v)
            for k, v in row.items()
        }
        version = flat_row.pop("radar_version", None)
        if version is not None and "breakthrough_name" in flat_row:
            flat_row["breakthrough_name"] = f"{flat_row['breakthrough_name']} ({version})"
        flat.append(flat_row)
    return flat


_SKOS_COLORS = {
    "IS_BROADER":          "#3498DB",
    "IS_NARROWER":         "#9B59B6",
    "IS_BROADER_CONCEPT":  "#3498DB",
    "IS_NARROWER_CONCEPT": "#9B59B6",
    "IS_RELATED_CONCEPT":  "#F39C12",
}
_REL_COLORS = {"ADVANCES": "#2ECC71", "REQUIRES": "#E74C3C"}


def _rel_badge(rel: str, color: str) -> str:
    return (f'<span style="font-size:10px; background:{color}22; color:{color}; '
            f'border:1px solid {color}66; border-radius:4px; padding:1px 5px; '
            f'margin:0 3px; white-space:nowrap;">{rel}</span>')


def _node_span(label: str, icon: str, bold: bool = False) -> str:
    weight = "700" if bold else "400"
    return f'<span style="font-weight:{weight}; color:#1a1e2a;">{icon} {label}</span>'


def _path_card(parts: list[str]) -> None:
    st.markdown(
        '<div style="background:#fff; border:1px solid #dde2ec; border-radius:8px; '
        'padding:8px 12px; margin-bottom:6px; line-height:2;">'
        + " ".join(parts) + '</div>',
        unsafe_allow_html=True,
    )


def _is_bridge_result(results: list[dict]) -> bool:
    if not results:
        return False
    keys = set(results[0].keys())
    return "b1_name" in keys and "b2_name" in keys and "rel_type_1" in keys


def _is_sdg_contributor_result(results: list[dict]) -> bool:
    if not results:
        return False
    keys = set(results[0].keys())
    return "sdg_target_id" in keys and "breakthrough_name" in keys


def _is_neighborhood_result(results: list[dict]) -> bool:
    if not results:
        return False
    keys = set(results[0].keys())
    return "center_concept" in keys and "relationship_1" in keys


def _breakthrough_label(name: str, version) -> str:
    return f"{name} ({version})" if version else name


def _render_bridge_results(results: list[dict]) -> None:
    for row in results:
        parts: list[str] = []
        parts.append(_node_span(_breakthrough_label(row["b1_name"], row.get("b1_radar_version")), "💡", bold=True))
        parts.append(_rel_badge(row.get("rel_type_1", "→"),
                                _REL_COLORS.get(row.get("rel_type_1", ""), "#888")))
        i = 1
        while f"concept_{i}" in row:
            v = row[f"concept_{i}"]
            if v is not None:
                parts.append(_node_span(v, "📚"))
            sr_key = f"skos_rel_{i}"
            if sr_key in row and row[sr_key] is not None:
                sr = row[sr_key]
                parts.append(_rel_badge(sr, _SKOS_COLORS.get(sr, "#888")))
            i += 1
        parts.append(_rel_badge(row.get("rel_type_2", "→"),
                                _REL_COLORS.get(row.get("rel_type_2", ""), "#888")))
        parts.append(_node_span(_breakthrough_label(row["b2_name"], row.get("b2_radar_version")), "💡", bold=True))
        _path_card(parts)


def _render_sdg_contributor_results(results: list[dict]) -> None:
    _CONTRIBUTES_TO_COLOR = "#9B59B6"
    for row in results:
        parts: list[str] = []
        # Breakthrough on the left
        parts.append(_node_span(_breakthrough_label(row["breakthrough_name"], row.get("radar_version")), "💡", bold=True))
        b_rel = row.get("b_rel", "→")
        parts.append(_rel_badge(b_rel, _REL_COLORS.get(b_rel, "#888")))
        # Intermediate concepts — stored in reverse order (concept_1 is closest to target,
        # concept_N is closest to breakthrough), so walk from highest to lowest index
        max_i = sum(1 for k in row if k.startswith("concept_") and row[k] is not None)
        for i in range(max_i, 0, -1):
            v = row.get(f"concept_{i}")
            if v is not None:
                parts.append(_node_span(v, "📚"))
            if i > 1:
                sr = row.get(f"skos_rel_{i - 1}")
                if sr is not None:
                    parts.append(_rel_badge(sr, _SKOS_COLORS.get(sr, "#888")))
        # CONTRIBUTES_TO → SDGtarget on the right
        parts.append(_rel_badge("CONTRIBUTES_TO", _CONTRIBUTES_TO_COLOR))
        parts.append(_node_span(row["sdg_target_id"], "🎯", bold=True))
        dist = row.get("distance", "")
        parts.append(f'<span style="font-size:11px; color:#6b7280; margin-left:6px;">dist={dist}</span>')
        _path_card(parts)


def _render_neighborhood_results(results: list[dict]) -> None:
    for row in results:
        parts: list[str] = []
        # Center node
        center = row.get("center_concept")
        if center is not None:
            parts.append(_node_span(center, "📚", bold=True))
        # Walk positional relationship_N / neighbor_concept_N columns, skip nulls
        i = 1
        while f"relationship_{i}" in row or f"neighbor_concept_{i}" in row:
            rel = row.get(f"relationship_{i}")
            node = row.get(f"neighbor_concept_{i}")
            if rel is not None:
                parts.append(_rel_badge(rel, _SKOS_COLORS.get(rel, "#888")))
            if node is not None:
                parts.append(_node_span(node, "📚"))
            i += 1
        if len(parts) > 1:
            _path_card(parts)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render() -> None:
    st.subheader("Hardcoded Queries")
    st.caption(
        "Pre-configured queries to explore the structure, and get insights from the Knowledge Graph."
    )

    _, executor, neo4j_err = get_neo4j_resources()
    if executor is None:
        st.error(f"Neo4j unavailable: {neo4j_err}")
        return

    # ── Query selector ────────────────────────────────────────────────────────
    by_category: dict[str, list] = defaultdict(list)
    for q in HARDCODED_QUERIES:
        by_category[q["category"]].append(q)

    options = [q["id"] for q in HARDCODED_QUERIES]
    labels  = {q["id"]: f'{q["icon"]} {q["name"]}' for q in HARDCODED_QUERIES}

    col_sel, col_main = st.columns([1, 3])

    with col_sel:
        st.markdown('<div class="section-header">Query type</div>', unsafe_allow_html=True)
        selected_id = st.radio(
            "Select query",
            options,
            format_func=lambda oid: labels[oid],
            label_visibility="collapsed",
            key="hq_selected",
        )

    query_def = next(q for q in HARDCODED_QUERIES if q["id"] == selected_id)

    with col_main:
        st.markdown(
            f'<div style="border-left:3px solid #3498DB; padding-left:12px; margin-bottom:16px;">'
            f'<div style="font-size:18px; font-weight:700; color:#1a1e2a;">'
            f'{query_def["icon"]} {query_def["name"]}</div>'
            f'<div style="font-size:13px; color:#6b7280; margin-top:4px;">'
            f'{query_def["description"]}</div>'
            f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">'
            f'method: <code>{query_def["method"]}</code></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        has_picker = any(i["type"] == "node_picker" for i in query_def["inputs"])

        collected, all_filled = _collect_inputs(query_def)

        if has_picker:
            # No run button — query fires automatically whenever a concept is
            # selected. Changing hops/limit also re-runs immediately.
            st.session_state.pop(f"hq_{selected_id}_auto_run", None)
            run = all_filled
            if not run:
                st.info("Search for a node above — click a result to run the query.")
                return
        else:
            auto_run = st.session_state.pop(f"hq_{selected_id}_auto_run", False)
            run = st.button("▶ Run", type="primary", key=f"hq_run_{selected_id}") or auto_run
            if not run:
                if query_def["inputs"]:
                    st.info("Fill in the parameters above and press **▶ Run**.")
                return
            if not all_filled:
                st.warning("Please fill in all required fields.")
                return

        kwargs = {**collected, **query_def.get("fixed_params", {})}

        with st.spinner("Running query…"):
            try:
                results = getattr(executor, query_def["method"])(**kwargs)
            except Exception as exc:
                st.error(f"Query error: {exc}")
                return

        if not results:
            st.info("Query returned no results.")
            return

        st.success(f"**{len(results)}** row(s) returned")

        with st.expander("Cypher query", expanded=False):
            st.code(executor.last_query.strip(), language="cypher")
            if executor.last_params:
                st.caption("Parameters: " + ", ".join(f"`{k}` = `{v}`" for k, v in executor.last_params.items()))

        if _is_bridge_result(results):
            _render_bridge_results(results)
        elif _is_sdg_contributor_result(results):
            _render_sdg_contributor_results(results)
        elif _is_neighborhood_result(results):
            _render_neighborhood_results(results)
        else:
            flat = _flatten_results(results)
            df = pd.DataFrame(flat)
            st.dataframe(df, use_container_width=True, height=420)

        flat = _flatten_results(results)
        csv = pd.DataFrame(flat).to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv,
            file_name=f"{selected_id}.csv",
            mime="text/csv",
        )
