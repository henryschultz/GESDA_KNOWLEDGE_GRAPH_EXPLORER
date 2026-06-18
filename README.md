---
title: GESDA Knowledge Graph Explorer
emoji: 🔬
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: "1.41.0"
app_file: graph_UI/app.py
pinned: false
---
# GESDA Knowledge Graph Explorer

A deterministic, no-LLM Streamlit UI for exploring the GESDA knowledge graph — UNESCO Thesaurus concepts, UN SDG targets/goals/indicators, and the `Breakthrough`/`Platform`/`Emerging topic` nodes extracted from the GESDA Science & Diplomacy Radar (2021 / 2023 / 2026 editions).

It runs entirely on hand-built or generated Cypher against Neo4j, plus a local embedding model for semantic search — there is no LLM call anywhere in this app (the LLM-driven agent that *does* answer free-text questions lives in `graphrag/` in the main repo, not here).

This is a **standalone git repository**, independent of the main `GESDA_RAG_RADAR` repo, deployed as its own [Hugging Face Space](https://huggingface.co/spaces/schultzhenry/gesda_knowledge_graph_demo).

## Tabs

### 🔎 Hardcoded Queries

A fixed menu of pre-built, parameterized Cypher queries (defined in `graph_UI/queries/hardcoded.py`, executed via `neo4j_graph/query_executor.py`). Each one renders the Cypher it ran, the result table, and a CSV download. Current queries:

| Query                                                     | What it does                                                                                                     |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Concept Neighborhood**                            | Semantic neighbors of a UNESCO concept via `IS_BROADER`/`IS_NARROWER`/`IS_RELATED_CONCEPT`, up to N hops   |
| **Cross-Breakthroughs relationships (2026)**        | Top "producer" (advances many fields others need) or "receiver" (needs many fields others advance) breakthroughs |
| **Cross-Domain Concept Bridges**                    | Semantic path connecting two breakthroughs through shared/related UNESCO concepts                                |
| **Concept importance to the Radar**                 | Ranks UNESCO concepts by centrality to breakthroughs (`REQUIRES`/`ADVANCES`)                                 |
| **Concept importance to UN SDGs**                   | Ranks UNESCO concepts by centrality to SDG targets (`CONTRIBUTES_TO`)                                          |
| **Concept combined importance (Radar + SDGs)**      | Joint ranking across both — a "meta-trend" view across science and diplomacy                                    |
| **Breakthroughs SDG Impact (2026)**                 | Scores 2026 breakthroughs by number of distinct SDG targets they reach                                           |
| **SDG Target → Biggest Breakthrough Contributors** | For one SDG target, finds the breakthroughs reaching it by the shortest concept path                             |
| **Concept Evolution (2021 → 2023 → 2026)**        | Compares a concept's importance across all three Radar editions                                                  |

Queries that take a concept/breakthrough/SDG-target name use a **node picker**: type a free-text term, it runs a vector search scoped to that node type, and clicking a result fills the field and auto-runs the query.

### 🔭 Vector Search

Free-text semantic search across all node types in one box — useful for finding the right graph terminology from non-expert language (works in most languages, since BGE-M3 is multilingual). Select a specific node type or search "All" at once; results are grouped and deduplicated (UNESCO concepts collapse multiple matched attributes — e.g. translated labels — under one card).

### 🛠️ Query Builder

An interactive, iterative Cypher builder: pick a starting node type, add up to 5 relationship hops (only schema-valid relationships are offered at each step), optionally pin any node in the chain to a specific value via the same vector-search picker, and run. The generated Cypher is shown live before you run it.

## Architecture

```
                          ┌─────────────────────┐
                          │   Streamlit UI       │
                          │   (this app)         │
                          └──────────┬───────────┘
                 ┌────────────────────┼────────────────────┐
                 ▼                                          ▼
      neo4j_graph/ (Cypher)                        src/ (vector search)
      Neo4jConnection + QueryExecutor              BAAI/bge-m3 (local, in-process)
                 │                                          │
                 ▼                                          ▼
          Neo4j Aura (graph)                    Qdrant Cloud — collection
          breakthroughs, concepts,               `kg_nodes_bge_m3` (1024-dim)
          SDG targets, platforms, edges           one point per node attribute
```

The embedding model (`BAAI/bge-m3` via `FlagEmbedding`) runs **inside the Space itself**, loaded once at startup and cached with `@st.cache_resource` — no external embedding API and no VPN dependency, so query-time search works for free on a public Space. Neo4j Aura and Qdrant Cloud are both reachable directly over the public internet.

## Repository layout

```
hf_space/
├── README.md              this file (+ HF Space metadata frontmatter)
├── requirements.txt       Python dependencies
├── config/
│   └── config.yaml        embedding model + Qdrant connection settings
├── src/                   vector-search building blocks
│   ├── config.py          loads config.yaml, overlays QDRANT_URL/QDRANT_API_KEY env vars
│   ├── embeddings.py       EmbeddingModel (local BGE-M3) / APIEmbeddingModel (unused here)
│   └── qdrant_store.py     QdrantStore — thin wrapper over qdrant-client (local or cloud)
├── graph_UI/              the Streamlit app
│   ├── app.py              entry point — page config, sidebar, tab wiring
│   ├── config.py           path bootstrap, app constants, .env loading
│   ├── db/
│   │   ├── neo4j_client.py    cached Neo4jConnection/QueryExecutor
│   │   └── vector_client.py   cached embedder/QdrantStore + vector_search()
│   ├── queries/
│   │   ├── hardcoded.py       the Hardcoded Queries tab's query definitions
│   │   ├── mappings.py        jargon → graph-term query rewriting
│   │   └── schema.py          node types, relationships, colors (Query Builder + badges)
│   └── ui/
│       ├── tab_hardcoded.py
│       ├── tab_vector_search.py
│       ├── tab_query_builder.py
│       └── styles.py
└── neo4j_graph/           self-contained Neo4j client (no dependency on the main repo)
    ├── config.py            reads NEO4J_URI/USERNAME/PASSWORD from env
    ├── neo4j_connection.py
    └── query_executor.py    all Cypher query methods used by the Hardcoded Queries tab
```

## Running locally

**Requirements:** Python 3.11+, a Neo4j instance with the GESDA graph loaded, and a Qdrant collection named `kg_nodes_bge_m3` populated by `scripts/embed_kg_nodes_bge_m3.py` (in the main repo) — either Qdrant Cloud or a local embedded store.

```bash
cd hf_space
pip install -r requirements.txt
```

Create `neo4j_graph/.env`:

```
NEO4J_URI=neo4j+s://<your-aura-id>.databases.neo4j.io
NEO4J_USERNAME=...
NEO4J_PASSWORD=...
```

Set Qdrant connection info either in `config/config.yaml` directly, or via environment variables (these override the YAML):

```bash
export QDRANT_URL="https://<your-cluster>.cloud.qdrant.io"
export QDRANT_API_KEY="..."
```

To point at a local embedded Qdrant store instead of the cloud, edit `config/config.yaml`:

```yaml
qdrant:
  mode: "local"
  local_path: "/path/to/qdrant_storage"
```

Then run:

```bash
streamlit run graph_UI/app.py
```

First launch downloads the `BAAI/bge-m3` model weights (~2 GB) — subsequent launches use the local HF cache.

## Deploying to Hugging Face Spaces

This repo's `hf` remote already points at the live Space:

```bash
git remote -v   # hf  git@hf.co:spaces/schultzhenry/gesda_knowledge_graph_demo
```

**1. Set Space secrets** — on the Space page, go to *Settings → Variables and secrets* and add:

| Secret             | Value                                   |
| ------------------ | --------------------------------------- |
| `NEO4J_URI`      | your Neo4j Aura URI (`neo4j+s://...`) |
| `NEO4J_USERNAME` | Aura username                           |
| `NEO4J_PASSWORD` | Aura password                           |
| `QDRANT_URL`     | Qdrant Cloud cluster URL                |
| `QDRANT_API_KEY` | Qdrant Cloud API key                    |

These land as process environment variables at container startup — `neo4j_graph/config.py` and `src/config.py` read them directly (no `.env` file is shipped or needed in the Space).

**2. Push:**

```bash
git add .
git commit -m "update"
git push hf main
```

HF rebuilds automatically. First build installs `torch` + `FlagEmbedding` and downloads the BGE-M3 weights, so it takes a few minutes; subsequent builds are faster via layer/package caching. Watch progress under the Space's *Logs* tab.

**3. Verify:**

- Logs show no import errors and both the Neo4j and vector-search connection indicators in the sidebar go green.
- **Vector Search** tab: a query like "quantum computing" returns scored results.
- **Hardcoded Queries** tab: e.g. "Concept Neighborhood" returns a populated table.
- **Query Builder** tab: build a 1-hop path and run it.

### Qdrant Cloud note

Qdrant Cloud's server mode enforces payload indexes for filtered search (unlike local/embedded mode). If you re-create or re-migrate the `kg_nodes_bge_m3` collection, make sure keyword indexes exist on `node_type` and `attribute_name` — see `scripts/migrate_qdrant_to_cloud.py --index-only` in the main repo.
