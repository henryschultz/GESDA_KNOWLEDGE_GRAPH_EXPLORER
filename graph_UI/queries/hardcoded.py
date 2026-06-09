"""
Hardcoded query definitions — backed by QueryExecutor methods.

Each entry maps to one method on QueryExecutor (neo4j_graph/query_executor.py).
The UI reads `inputs` to render the right controls, collects values, then calls:

    getattr(executor, entry["method"])(**user_inputs, **entry.get("fixed_params", {}))

Input spec fields
-----------------
key         : kwarg name passed to the method
label       : label shown in the UI
type        : "text" | "select" | "checkbox" | "number"
placeholder : (text only) hint text
options     : (select only) list of values
default     : initial value
min / max   : (number only) bounds

Add a new query by appending a dict here — no other file needs to change.
"""
from __future__ import annotations

from typing import Final

HARDCODED_QUERIES: Final[list[dict]] = [

    # ── Exploration ───────────────────────────────────────────────────────────
    {
        "id":          "concept_neighborhood",
        "name":        "Concept Neighborhood",
        "icon":        "🕸️",
        "category":    "Explore mappings",
        "description": "Explore the semantic neighbors of a concept",
        "method":      "get_concept_neighborhood",
        "inputs": [
            {"key": "concept_keyword", "label": "Search for a concept", "type": "node_picker",
             "node_type": "UNESCOconcept", "placeholder": "e.g. artificial intelligence", "top_k": 7},
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [1, 2, 3, 4], "default": 2, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",           "label": "Limit",               "type": "number", "default": 30, "min": 5, "max": 200},
        ],
    },
    {
        "id":          "platform_span",
        "name":        "Cross-Breakthroughs relationships (2026)",
        "icon":        "🌐",
        "category":    "Insights from the Knowledge Graph",
        "description": "Find the top 'producer' or 'receiver' Breakthroughs in the 2026 Radar",
        "method":      "get_breakthrough_platform_span",
        "inputs": [
            {"key": "breakthrough_profile", "label": "Breakthroughs that...", "type": "select",
             "options": ["all", "producer", "receiver"],
             "option_labels": {"all": "Both", "producer": "Produce most for other Breakthroughs", "receiver": "Need most from other Breakthroughs"},
             "default": "producer", "help": "Producer Breakthroughs advance fields that other breakthroughs require; Receiver breakthroughs require fields that other Breakthroughs advance."},
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2, 3], "default": 3, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",       "label": "Limit",               "type": "number",   "default": 20, "min": 5, "max": 200},
            {"key": "weight_by_nplatforms", "label": "Rank by importance score", "type": "checkbox", "default": False,
            "help": "Importance score = Breakthrough count × Platform span."},
        ],
    },
    {
        "id":          "cross_domain_bridges",
        "name":        "Cross-Domain Concept Bridges",
        "icon":        "🔗",
        "category":    "Cross-domain",
        "description": "Explore the semantic path between two Breakthroughs",
        "method":      "get_cross_domain_bridges",
        "inputs": [
            {"key": "keyword_1", "label": "Search for a breakthrough", "type": "node_picker",
             "node_type": "Breakthrough", "placeholder": "e.g. artificial intelligence", "top_k": 7},
            {"key": "keyword_2", "label": "Search for a breakthrough", "type": "node_picker",
             "node_type": "Breakthrough", "placeholder": "e.g. environment", "top_k": 7},
            {"key": "limit", "label": "Limit",     "type": "number", "default": 20, "min": 5, "max": 200},
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2, 3,4], "default": 0, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
        ],
    },

    # ── Concept Analysis ──────────────────────────────────────────────────────
    {
        "id":          "concept_importance",
        "name":        "Concept importance to the Radar",
        "icon":        "📊",
        "category":    "Explore mappings",
        "description": "Rank UNESCO concepts by their centrality to the Radar Breakthroughs",
        "method":      "get_concept_importance",
        "inputs": [
            {"key": "relationships", "label": "Count...", "type": "select",
             "options": ["all", "requires_only", "advances_only"],
             "option_labels": {"all": "Both", "requires_only": "Requirements for the field", "advances_only": "Advances to the field"},
             "default": "advances_only", "help": "Count the number of Breakthroughs that advance, require the field, or both."},
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2, 3], "default": 3, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",       "label": "Limit",               "type": "number",   "default": 30, "min": 5, "max": 200},
            {"key": "latest_only", "label": "Latest edition only", "type": "checkbox", "default": True,
             "help": "Only consider breakthroughs from the latest radar edition (2026)."},
            {"key": "weight_by_nplatforms", "label": "Rank by importance score", "type": "checkbox", "default": False,
             "help": "Importance score = #Breakthroughs reached × #Platforms reached."},
        ],
    },
    {
        "id":          "concept_importance_sdg",
        "name":        "Concept importance to UN SDGs",
        "icon":        "🎯",
        "category":    "Explore mappings",
        "description": "Rank UNESCO concepts by their centrality to the SDG targets",
        "method":      "get_concept_importance_by_sdg",
        "inputs": [
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2, 3], "default": 3, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",       "label": "Limit",               "type": "number",   "default": 30, "min": 5, "max": 200},
            {"key": "weight_by_nsdggoals", "label": "Rank by importance score", "type": "checkbox", "default": False,
             "help": "Importance score = #SDG targets reached × #SDG goals reached."},
        ],
    },
    {
        "id":          "concept_combined_importance",
        "name":        "Concept combined importance (Radar + SDGs)",
        "icon":        "⚡",
        "category":    "Explore mappings",
        "description": "Rank UNESCO concepts by both their connectivity to Radar Breakthroughs and SDG targets ('meta-trend' across diplomacy and science)",
        "method":      "get_concept_combined_importance",
        "inputs": [
            {"key": "relationships", "label": "Count...", "type": "select",
             "options": ["all", "requires_only", "advances_only"],
             "option_labels": {"all": "Both", "requires_only": "Requirements for the field", "advances_only": "Advances to the field"},
             "default": "advances_only", "help": "Count the number of Breakthroughs that advance, require the field, or both."},
            {"key": "hops",        "label": "Semantic jumps allowed", "type": "select", "options": [0, 1, 2, 3], "default": 3,
             "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",       "label": "Limit",               "type": "number",   "default": 30, "min": 5, "max": 200},
            {"key": "latest_only", "label": "Latest edition only", "type": "checkbox", "default": True,
             "help": "Only consider breakthroughs from the latest radar edition (2026)."},
        ],
    },
    {
        "id":          "sdg_impact",
        "name":        "Breakthroughs SDG Impact (2026)",
        "icon":        "🌱",
        "category":    "Insights from the Knowledge Graph",
        "description": "Score 2026 Breakthroughs by how many distinct SDG targets they address",
        "method":      "rank_breakthroughs_by_sdg_impact",
        "inputs": [
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2, 3], "default": 3, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
            {"key": "limit",                "label": "Limit",                "type": "number",   "default": 20, "min": 5, "max": 200},
            {"key": "weight_by_ngoals", "label": "Rank by importance score", "type": "checkbox", "default": False,
             "help": "Importance score = #SDG targets reached × #SDG goals reached."},
        ],
    },

    {
        "id":          "sdg_breakthrough_contributors",
        "name":        "SDG Target → Biggest Breakthrough Contributors",
        "icon":        "🎯",
        "category":    "Insights from the Knowledge Graph",
        "description": "Find the most direct Breakthrough contributors to a given SDG target, ranked by shortest concept path",
        "method":      "get_breakthrough_contributors_for_sdgtarget",
        "inputs": [
            {"key": "target_id", "label": "Search for an SDG target", "type": "node_picker",
             "node_type": "SDGtarget", "placeholder": "e.g. poverty", "top_k": 7,
             "value_prop": "node_id", "display_node_id": True},
            {"key": "limit",       "label": "Limit", "type": "number", "default": 10, "min": 1, "max": 100},
            {"key": "latest_only", "label": "Latest edition only", "type": "checkbox", "default": True,
             "help": "Only consider breakthroughs from the latest radar edition (2026)."},
        ],
    },
    {
        "id":          "concept_evolution",
        "name":        "Concept Evolution (2021 → 2023 → 2026)",
        "icon":        "📈",
        "category":    "Insights from the Knowledge Graph",
        "description": "Compare concept importance between the 2021, 2023 and 2026 Radar editions. HEAVY QUERY (semantic jump = 1 → ~ 1min; semantic jump = 2 → ~3min)",
        "method":      "get_concept_evolution",
        "inputs":      [
            {"key": "hops",        "label": "Semantic jumps allowed",           "type": "select",   "options": [0, 1, 2], "default": 2, "help": "Jump between UNESCO Concepts via RELATED, BROADER, NARROWER relationships."},
        ],
    }
]
