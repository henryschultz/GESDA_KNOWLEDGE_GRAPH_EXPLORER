"""Central configuration and path bootstrap for the KG Explorer UI."""
from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------

UI_ROOT = Path(__file__).parent.resolve()
PROJECT_ROOT = UI_ROOT.parent.resolve()
NEO4J_DIR = PROJECT_ROOT / "neo4j_graph"

# Make existing project modules importable
for _p in [str(PROJECT_ROOT), str(NEO4J_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    load_dotenv(NEO4J_DIR / ".env", override=False)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Application constants
# ---------------------------------------------------------------------------

APP_TITLE = "GESDA Knowledge Graph Explorer"
APP_ICON = "🔬"

# Vector search defaults
DEFAULT_TOP_K = 20
DEFAULT_THRESHOLD = 0.50
KG_NODES_COLLECTION = "kg_nodes_bge_m3"

# Query builder defaults
DEFAULT_LIMIT = 25
