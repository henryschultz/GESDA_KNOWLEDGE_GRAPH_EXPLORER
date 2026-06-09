"""
Graph schema constants: node types, properties, relationships, and UI colours.

Edit this file to reflect any schema changes in the Neo4j graph.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Node types and their properties / display label
# ---------------------------------------------------------------------------

# Keys: the exact Neo4j label (backtick-wrapped if spaces exist, handled in Cypher)
NODE_SCHEMA: dict[str, dict] = {
    "Breakthrough": {
        "display_prop": "name",
        "properties": ["name", "is_latest", "radar_version"],
        "label_cypher": "Breakthrough",
    },
    "UNESCOconcept": {
        "display_prop": "pref_label_en",
        "properties": ["pref_label_en", "pref_label_fr", "pref_label_es", "pref_label_ru", "pref_label_ar", "uri"],
        "label_cypher": "UNESCOconcept",
    },
    "Platform": {
        "display_prop": "name",
        "properties": ["name", "is_latest", "radar_version"],
        "label_cypher": "Platform",
    },
    "Emerging topic": {
        "display_prop": "name",
        "properties": ["name", "is_latest", "radar_version"],
        "label_cypher": "`Emerging topic`",
    },
    "SDGtarget": {
        "display_prop": "target_id",
        "properties": ["target_id", "target_text"],
        "label_cypher": "SDGtarget",
    },
    "SDGgoal": {
        "display_prop": "goal_id",
        "properties": ["goal_id", "goal_text"],
        "label_cypher": "SDGgoal",
    },
    "SDGindicator": {
        "display_prop": "indicator_id",
        "properties": ["indicator_id", "indicator_text"],
        "label_cypher": "SDGindicator",
    },
    "OECDfield": {
        "display_prop": "name",
        "properties": ["name"],
        "label_cypher": "OECDfield",
    },
}

# ---------------------------------------------------------------------------
# Relationship types: from → to (for query builder suggestions)
# ---------------------------------------------------------------------------

RELATIONSHIPS: list[dict] = [
    {"type": "REQUIRES",            "from": "Breakthrough",    "to": "UNESCOconcept"},
    {"type": "ADVANCES",            "from": "Breakthrough",    "to": "UNESCOconcept"},
    {"type": "CONTAINS",            "from": "Platform",        "to": "Emerging topic"},
    {"type": "CONTAINS",            "from": "Emerging topic",  "to": "Breakthrough"},
    {"type": "CONTRIBUTES_TO",      "from": "UNESCOconcept",   "to": "SDGtarget"},
    {"type": "HAS_TARGET",          "from": "SDGgoal",         "to": "SDGtarget"},
    {"type": "IS_BROADER_CONCEPT",  "from": "UNESCOconcept",   "to": "UNESCOconcept"},
    {"type": "IS_NARROWER_CONCEPT", "from": "UNESCOconcept",   "to": "UNESCOconcept"},
    {"type": "IS_RELATED_CONCEPT",  "from": "UNESCOconcept",   "to": "UNESCOconcept"},
    {"type": "IS_BROAD_MATCH",      "from": "OECDfield",       "to": "UNESCOconcept"},
    {"type": "IS_EXACT_MATCH",      "from": "OECDfield",       "to": "UNESCOconcept"},
    {"type": "IS_RELATED_CONCEPT",  "from": "OECDfield",       "to": "UNESCOconcept"},
]

# ---------------------------------------------------------------------------
# UI colours per node type
# ---------------------------------------------------------------------------

NODE_COLORS: dict[str, str] = {
    "Breakthrough":    "#E74C3C",
    "UNESCOconcept":   "#3498DB",
    "Platform":        "#2ECC71",
    "Emerging topic":  "#F39C12",
    "SDGtarget":       "#9B59B6",
    "SDGgoal":         "#1ABC9C",
    "SDGindicator":    "#E67E22",
    "OECDfield":       "#7F8C8D",
}

# ---------------------------------------------------------------------------
# Filter operators for query builder
# ---------------------------------------------------------------------------

FILTER_OPS = ["CONTAINS", "=", "STARTS WITH", "ENDS WITH", "<>", ">", "<", ">=", "<="]

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def cypher_label(node_type: str) -> str:
    """Return the Cypher-safe label string (backtick-wrapped if needed)."""
    return NODE_SCHEMA.get(node_type, {}).get("label_cypher", node_type)


def available_rels_from(node_type: str) -> list[dict]:
    """Return all relationship definitions that start from node_type."""
    return [r for r in RELATIONSHIPS if r["from"] == node_type]
