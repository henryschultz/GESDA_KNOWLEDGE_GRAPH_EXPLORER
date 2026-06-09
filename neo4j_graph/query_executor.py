from typing import List, Dict, Any
from neo4j import Driver


_UC_SKOS_REL = "IS_BROADER_CONCEPT|IS_NARROWER_CONCEPT|IS_RELATED_CONCEPT"

_LINK_QUERY_HOPS_1 = """
MATCH (b1:Breakthrough {name: $breakthrough_1})-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {name: $breakthrough_2})
RETURN b1.name AS breakthrough_1,
       b2.name AS breakthrough_2,
       1 AS hops,
       [uc.pref_label_en] AS concept_chain,
       count(*) AS path_count
ORDER BY path_count DESC
"""

_LINK_QUERY_HOPS_2 = f"""
MATCH (b1:Breakthrough {{name: $breakthrough_1}})-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {{name: $breakthrough_2}})
RETURN b1.name AS breakthrough_1, b2.name AS breakthrough_2,
       1 AS hops, [uc.pref_label_en] AS concept_chain, count(*) AS path_count
UNION ALL
MATCH (b1:Breakthrough {{name: $breakthrough_1}})-[:REQUIRES|ADVANCES]->(uc1:UNESCOconcept)
      -[:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {{name: $breakthrough_2}})
WHERE uc1 <> uc2
RETURN b1.name AS breakthrough_1, b2.name AS breakthrough_2,
       2 AS hops, [uc1.pref_label_en, uc2.pref_label_en] AS concept_chain, count(*) AS path_count
ORDER BY hops ASC, path_count DESC
"""

_LINK_QUERY_HOPS_3 = f"""
MATCH (b1:Breakthrough {{name: $breakthrough_1}})-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {{name: $breakthrough_2}})
RETURN b1.name AS breakthrough_1, b2.name AS breakthrough_2,
       1 AS hops, [uc.pref_label_en] AS concept_chain, count(*) AS path_count
UNION ALL
MATCH (b1:Breakthrough {{name: $breakthrough_1}})-[:REQUIRES|ADVANCES]->(uc1:UNESCOconcept)
      -[:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {{name: $breakthrough_2}})
WHERE uc1 <> uc2
RETURN b1.name AS breakthrough_1, b2.name AS breakthrough_2,
       2 AS hops, [uc1.pref_label_en, uc2.pref_label_en] AS concept_chain, count(*) AS path_count
UNION ALL
MATCH (b1:Breakthrough {{name: $breakthrough_1}})-[:REQUIRES|ADVANCES]->(uc1:UNESCOconcept)
      -[:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      -[:{_UC_SKOS_REL}]-(uc3:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough {{name: $breakthrough_2}})
WHERE uc1 <> uc2 AND uc2 <> uc3 AND uc1 <> uc3
RETURN b1.name AS breakthrough_1, b2.name AS breakthrough_2,
       3 AS hops, [uc1.pref_label_en, uc2.pref_label_en, uc3.pref_label_en] AS concept_chain,
       count(*) AS path_count
ORDER BY hops ASC, path_count DESC
"""

# Concept importance queries - unified logic with optional platform weighting
# Only consider breakthroughs with is_latest flag to avoid counting duplicates

_CONCEPT_IMPORTANCE_REL_PATTERNS = {
    "all": "REQUIRES|ADVANCES",
    "requires_only": "REQUIRES",
    "advances_only": "ADVANCES",
}


def _build_concept_importance_query(rel_pattern: str, hops: int) -> str:
    rel = _CONCEPT_IMPORTANCE_REL_PATTERNS[rel_pattern]
    if hops == 0:
        return f"""
MATCH (p:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->
       (b:Breakthrough)-[:{rel}]->(uc:UNESCOconcept)
WHERE ($latest_only = false OR (b.is_latest = true))
WITH uc, count(DISTINCT p) AS platform_span, count(DISTINCT b) AS breakthrough_count
RETURN uc.pref_label_en AS concept_name,
       breakthrough_count,
       platform_span,
       breakthrough_count * platform_span AS importance_score
ORDER BY breakthrough_count DESC, importance_score DESC
LIMIT $limit
"""
    else:
        return f"""
MATCH (p:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->
       (b:Breakthrough)-[:{rel}]->(uc:UNESCOconcept)
       -[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
WHERE ($latest_only = false OR (b.is_latest = true))
WITH uc_final, count(DISTINCT p) AS platform_span, count(DISTINCT b) AS breakthrough_count
RETURN uc_final.pref_label_en AS concept_name,
       breakthrough_count,
       platform_span,
       breakthrough_count * platform_span AS importance_score
ORDER BY breakthrough_count DESC, importance_score DESC
LIMIT $limit
"""


# SDG-based concept importance: rank concepts by CONTRIBUTES_TO count, optionally weighted by SDGgoal span
def _build_concept_sdg_importance_query(hops: int) -> str:
    if hops == 0:
        return """
MATCH (uc:UNESCOconcept)-[:CONTRIBUTES_TO]->(t:SDGtarget)<-[:HAS_TARGET]-(g:SDGgoal)
WITH uc, count(DISTINCT t) AS n_sdgTargets_contributed, count(DISTINCT g) AS n_sdgGoals_contributed
RETURN uc.pref_label_en AS concept_name,
       n_sdgTargets_contributed,
       n_sdgGoals_contributed,
       n_sdgTargets_contributed * n_sdgGoals_contributed AS importance_score
ORDER BY n_sdgTargets_contributed DESC, importance_score DESC
LIMIT $limit
"""
    else:
        return f"""
MATCH (uc:UNESCOconcept)-[:CONTRIBUTES_TO]->(t:SDGtarget)<-[:HAS_TARGET]-(g:SDGgoal)
MATCH (uc)-[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
WITH uc_final, count(DISTINCT t) AS n_sdgTargets_contributed, count(DISTINCT g) AS n_sdgGoals_contributed
RETURN uc_final.pref_label_en AS concept_name,
       n_sdgTargets_contributed,
       n_sdgGoals_contributed,
       n_sdgTargets_contributed * n_sdgGoals_contributed AS importance_score
ORDER BY n_sdgTargets_contributed DESC, importance_score DESC
LIMIT $limit
"""

_BREAKTHROUGH_SPAN_PROFILE_RELS = {
    "all": ("REQUIRES|ADVANCES", "REQUIRES|ADVANCES"),
    "producer": ("ADVANCES", "REQUIRES"),
    "receiver": ("REQUIRES", "ADVANCES"),
}


def _build_breakthrough_platform_span_query(profile: str, hops: int) -> str:
    b_rel, other_rel = _BREAKTHROUGH_SPAN_PROFILE_RELS[profile]
    if hops == 0:
        return f"""
MATCH (b:Breakthrough)-[:{b_rel}]->(uc:UNESCOconcept)
      <-[:{other_rel}]-(b_other:Breakthrough)
      <-[:CONTAINS]-(:`Emerging topic`)<-[:CONTAINS]-(p_other:Platform)
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH b, count(DISTINCT b_other) AS reached_breakthroughs,
        count(DISTINCT p_other) AS platform_span
RETURN b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       reached_breakthroughs,
       platform_span,
       reached_breakthroughs * platform_span AS span_score
ORDER BY reached_breakthroughs DESC, span_score DESC, breakthrough_name ASC
LIMIT $limit
"""
    else:
        return f"""
MATCH (b:Breakthrough)-[:{b_rel}]->(uc:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
      <-[:{other_rel}]-(b_other:Breakthrough)
      <-[:CONTAINS]-(:`Emerging topic`)<-[:CONTAINS]-(p_other:Platform)
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH b, count(DISTINCT b_other) AS reached_breakthroughs,
        count(DISTINCT p_other) AS platform_span
RETURN b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       reached_breakthroughs,
       platform_span,
       reached_breakthroughs * platform_span AS span_score
ORDER BY reached_breakthroughs DESC, span_score DESC, breakthrough_name ASC
LIMIT $limit
"""


def _build_rank_breakthroughs_sdg_query(hops: int) -> str:
    if hops == 0:
        return """
MATCH (b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      -[:CONTRIBUTES_TO]->(t:SDGtarget)<-[:HAS_TARGET]-(g:SDGgoal)
WHERE b.is_latest = true
WITH b, count(DISTINCT t) AS n_sdg_targets, count(DISTINCT g) AS n_sdg_goals
RETURN b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       n_sdg_targets,
       n_sdg_goals,
       n_sdg_targets * n_sdg_goals AS importance_score
ORDER BY n_sdg_targets DESC, importance_score DESC
LIMIT $limit
"""
    else:
        return f"""
MATCH (b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{hops}]-(uc2:UNESCOconcept)
      -[:CONTRIBUTES_TO]->(t:SDGtarget)<-[:HAS_TARGET]-(g:SDGgoal)
WHERE b.is_latest = true
WITH b, count(DISTINCT t) AS n_sdg_targets, count(DISTINCT g) AS n_sdg_goals
RETURN b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       n_sdg_targets,
       n_sdg_goals,
       n_sdg_targets * n_sdg_goals AS importance_score
ORDER BY n_sdg_targets DESC, importance_score DESC
LIMIT $limit
"""


# --- Entity resolution queries (Phase 1) ---

_RESOLVE_BREAKTHROUGH = """
MATCH (n:Breakthrough)
WHERE toLower(n.name) CONTAINS toLower($keyword)
WITH n,
     CASE WHEN toLower(n.name) = toLower($keyword) THEN 1.0
          WHEN toLower(n.name) STARTS WITH toLower($keyword) THEN 0.9
          ELSE 0.7 END AS score
RETURN n.name AS name, score
ORDER BY score DESC, n.name ASC
LIMIT $limit
"""

_RESOLVE_CONCEPT = """
MATCH (n:UNESCOconcept)
WHERE toLower(n.pref_label_en) CONTAINS toLower($keyword)
WITH n,
     CASE WHEN toLower(n.pref_label_en) = toLower($keyword) THEN 1.0
          WHEN toLower(n.pref_label_en) STARTS WITH toLower($keyword) THEN 0.9
          ELSE 0.7 END AS score
RETURN n.pref_label_en AS name, score
ORDER BY score DESC, n.pref_label_en ASC
LIMIT $limit
"""

_RESOLVE_PLATFORM = """
MATCH (n:Platform {is_latest: true})
WHERE toLower(n.name) CONTAINS toLower($keyword)
WITH n,
     CASE WHEN toLower(n.name) = toLower($keyword) THEN 1.0
          WHEN toLower(n.name) STARTS WITH toLower($keyword) THEN 0.9
          ELSE 0.7 END AS score
RETURN n.name AS name, score
ORDER BY score DESC
LIMIT $limit
"""

_RESOLVE_OECD_FIELD = """
MATCH (n:OECDfield)
WHERE toLower(n.name) CONTAINS toLower($keyword)
WITH n,
     CASE WHEN toLower(n.name) = toLower($keyword) THEN 1.0
          WHEN toLower(n.name) STARTS WITH toLower($keyword) THEN 0.9
          ELSE 0.7 END AS score
RETURN n.name AS name, score
ORDER BY score DESC, n.name ASC
LIMIT $limit
"""

_RESOLVE_EMERGING_TOPIC = """
MATCH (n:`Emerging topic`)
WHERE toLower(n.name) CONTAINS toLower($keyword)
WITH n,
     CASE WHEN toLower(n.name) = toLower($keyword) THEN 1.0
          WHEN toLower(n.name) STARTS WITH toLower($keyword) THEN 0.9
          ELSE 0.7 END AS score
RETURN n.name AS name, score
ORDER BY score DESC, n.name ASC
LIMIT $limit
"""

# --- Cross-domain bridge queries (Phase 3) ---

class QueryExecutor:
    """Executes parameterized queries for breakthrough linking analysis."""

    def __init__(self, driver: Driver):
        """
        Initialize executor with Neo4j driver.

        Args:
            driver: neo4j.Driver instance
        """
        self.driver = driver
        self.last_query: str = ""
        self.last_params: Dict[str, Any] = {}

    def _execute_query(self, query: str, params: Dict[str, Any]) -> List[Dict]:
        """
        Execute parameterized query and return results as list of dicts.

        Args:
            query: Cypher query with $parameter placeholders
            params: Dictionary of parameters

        Returns:
            List of dictionaries with query results
        """
        self.last_query = query
        self.last_params = params
        with self.driver.session() as session:
            result = session.run(query, params)
            return [dict(record) for record in result]

    # -------------------------------------------------------------------------
    # Phase 1 — Entity resolution
    # -------------------------------------------------------------------------

    def resolve_entities(
        self,
        keyword: str,
        node_label: str = "Breakthrough",
        limit: int = 10,
    ) -> List[Dict]:
        """
        Translate a keyword fragment into candidate graph node names.

        Scores matches: exact=1.0, prefix=0.9, substring=0.7.
        This is the entity resolution layer that underpins all keyword-based
        queries — call it first to map natural-language terms to exact names.

        Args:
            keyword: Search term (case-insensitive substring match)
            node_label: One of "Breakthrough", "UNESCOconcept", "Platform",
                "OECDfield", "Emerging topic"
            limit: Maximum candidates to return

        Returns:
            List of dicts with keys: name, score
        """
        queries = {
            "Breakthrough": _RESOLVE_BREAKTHROUGH,
            "UNESCOconcept": _RESOLVE_CONCEPT,
            "Platform": _RESOLVE_PLATFORM,
            "OECDfield": _RESOLVE_OECD_FIELD,
            "Emerging topic": _RESOLVE_EMERGING_TOPIC,
        }
        if node_label not in queries:
            raise ValueError(
                f"node_label must be one of {list(queries)}; got {node_label!r}"
            )
        return self._execute_query(queries[node_label], {"keyword": keyword, "limit": limit})

    def list_platforms(self, latest_only: bool = True) -> List[Dict]:
        """
        List all platform names.

        Args:
            latest_only: Restrict to 2026 radar platforms if True

        Returns:
            List of dicts with keys: name, radar_index
        """
        query = """
MATCH (p:Platform)
WHERE ($latest_only = false OR p.is_latest = true)
RETURN DISTINCT p.name AS name, p.radar_index AS radar_index
ORDER BY p.radar_index
"""
        return self._execute_query(query, {"latest_only": latest_only})

    def list_oecd_fields(self, limit: int = None) -> List[Dict]:
        """
        List all OECD research fields.

        Returns:
            List of dicts with key: name
        """
        query = "MATCH (of:OECDfield) RETURN DISTINCT of.name AS name ORDER BY of.name"
        if limit:
            query += f" LIMIT {limit}"
        return self._execute_query(query, {})

    # -------------------------------------------------------------------------
    # Phase 2 — Domain keyword discovery
    # -------------------------------------------------------------------------

    def get_entity_by_keyword(
        self,
        keyword: str,
        node_label: str = "Breakthrough",
        latest_only: bool = True,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Find graph entities matching a keyword, enriched with context.

        Uses resolve_entities internally for fuzzy matching, then fetches
        context appropriate to the node type. The score from the fuzzy
        match is included in every result.

        Args:
            keyword: Case-insensitive substring
            node_label: One of "Breakthrough", "UNESCOconcept", "Platform",
                "OECDfield", "Emerging topic"
            latest_only: Restrict to 2026 radar where applicable
            limit: Maximum results

        Returns:
            Breakthrough   → name, platform_name, emerging_topic, score
            Platform       → name, radar_index, breakthrough_count, score
            UNESCOconcept  → name, breakthrough_count, platform_span, score
            OECDfield      → name, breakthrough_count, concept_count, score
            Emerging topic → name, platform_name, breakthrough_count, score
        """
        candidates = self.resolve_entities(keyword, node_label, limit=limit)
        if not candidates:
            return []

        names = [r["name"] for r in candidates]
        score_map = {r["name"]: r["score"] for r in candidates}

        if node_label == "Breakthrough":
            query = """
MATCH (p:Platform)-[:CONTAINS]->
      (et:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
WHERE ($latest_only = false OR (b.is_latest = true))
  AND b.name IN $names
RETURN DISTINCT b.name AS name,
       p.name AS platform_name,
       et.name AS emerging_topic
ORDER BY p.name, b.name
"""
        elif node_label == "Platform":
            query = """
MATCH (p:Platform)
WHERE ($latest_only = false OR p.is_latest = true)
  AND p.name IN $names
OPTIONAL MATCH (p)-[:CONTAINS]->(:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
WITH p, count(DISTINCT b) AS breakthrough_count
RETURN p.name AS name, p.radar_index AS radar_index, breakthrough_count
ORDER BY p.radar_index
"""
        elif node_label == "UNESCOconcept":
            query = """
MATCH (uc:UNESCOconcept)
WHERE uc.pref_label_en IN $names
OPTIONAL MATCH (p:Platform)-[:CONTAINS]->
      (:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc)
WHERE ($latest_only = false OR (b.is_latest = true))
WITH uc, count(DISTINCT b) AS breakthrough_count, count(DISTINCT p) AS platform_span
RETURN uc.pref_label_en AS name, breakthrough_count, platform_span
ORDER BY breakthrough_count DESC
"""
        elif node_label == "OECDfield":
            query = """
MATCH (of:OECDfield)
WHERE of.name IN $names
OPTIONAL MATCH (of)-[:IS_BROAD_MATCH|IS_EXACT_MATCH|IS_RELATED_CONCEPT]-(uc:UNESCOconcept)
              <-[:REQUIRES|ADVANCES]-(b:Breakthrough)
              <-[:CONTAINS]-(:`Emerging topic`)<-[:CONTAINS]-(:Platform)
WHERE ($latest_only = false OR (b.is_latest = true))
WITH of, count(DISTINCT b) AS breakthrough_count, count(DISTINCT uc) AS concept_count
RETURN of.name AS name, breakthrough_count, concept_count
ORDER BY breakthrough_count DESC
"""
        elif node_label == "Emerging topic":
            query = """
MATCH (p:Platform)-[:CONTAINS]->(et:`Emerging topic`)
WHERE et.name IN $names
OPTIONAL MATCH (et)-[:CONTAINS]->(b:Breakthrough)
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH et, p, count(DISTINCT b) AS breakthrough_count
RETURN DISTINCT et.name AS name, p.name AS platform_name, breakthrough_count
ORDER BY et.name
"""

        results = self._execute_query(
            query, {"names": names, "latest_only": latest_only}
        )
        for r in results:
            r["score"] = score_map.get(r["name"], 0.7)
        return results

    def get_breakthroughs_by_platform(
        self,
        platform_name: str,
        latest_only: bool = True,
        limit: int = 50,
    ) -> List[Dict]:
        """
        List all breakthroughs belonging to a named platform.

        Platform name is matched as a case-insensitive substring, so "AI"
        matches "AI & Machine Learning", etc.

        Args:
            platform_name: Platform name keyword
            latest_only: Restrict to is_latest breakthroughs if True
            limit: Maximum results

        Returns:
            List of dicts with keys: breakthrough_name, emerging_topic, platform_name
        """
        query = """
MATCH (p:Platform)-[:CONTAINS]->
      (et:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
WHERE ($latest_only = false OR (b.is_latest = true))
  AND toLower(p.name) CONTAINS toLower($platform_name)
RETURN DISTINCT b.name AS breakthrough_name,
       et.name AS emerging_topic,
       p.name AS platform_name
ORDER BY et.name, b.name
LIMIT $limit
"""
        return self._execute_query(
            query,
            {"platform_name": platform_name, "latest_only": latest_only, "limit": limit},
        )

    def get_new_topics_in_edition(self) -> List[Dict]:
        """
        Return breakthroughs present in the latest edition but absent in previous editions.
        
        Answers "which topics are new in the current edition vs previous editions?"
        using is_latest property.
        
        Returns:
            List of dicts with keys: breakthrough_name, emerging_topic, platform_name
        """
        query = """
    MATCH (p:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->(b_current:Breakthrough)
    WHERE b_current.is_latest = true
    AND NOT EXISTS {
        MATCH (b_previous:Breakthrough)
        WHERE b_previous.name = b_current.name 
        AND b_previous.is_latest = false
    }
    RETURN b_current.name AS breakthrough_name,
        et.name AS emerging_topic,
        p.name AS platform_name
    ORDER BY p.name, b_current.name
    """
        return self._execute_query(query, {})

    # -------------------------------------------------------------------------
    # Phase 3 — Cross-domain concept bridges
    # -------------------------------------------------------------------------

    def get_cross_domain_bridges(
        self,
        keyword_1: str,
        keyword_2: str,
        latest_only: bool = False,
        limit: int = 20,
        path_length: int = None,
        hops: int = 2,
    ) -> List[Dict]:
        """
        Find paths between two breakthroughs via UNESCOconcepts only.

        If path_length is specified, returns all paths of exactly that length (in relationships).
        Otherwise, returns all paths of the same shortest length.

        Args:
            keyword_1: Keyword matched against breakthrough names for side 1
            keyword_2: Keyword matched against breakthrough names for side 2
            latest_only: Restrict to is_latest breakthroughs if True (kept for compatibility)
            limit: Maximum number of paths to return
            path_length: If set, return paths of exactly this length (number of relationships).
                        If None, return all shortest paths.

        Returns:
            List of dicts with path structure: b1_name, rel_type_1, concept_1, skos_rel_1, ..., rel_type_2, b2_name, distance
        """
        path_length = hops+2
        if path_length is not None:
            query = f"""
MATCH p=((b1:Breakthrough {{name: $keyword_1}})-[*{path_length}..{path_length}]-(b2:Breakthrough {{name: $keyword_2}}))
WHERE all(n IN nodes(p)
WHERE (n = b1 OR n = b2) OR labels(n)[0] = 'UNESCOconcept')
RETURN p
LIMIT $limit
"""
        else:
            query = """
MATCH p=allShortestPaths((b1:Breakthrough {name: $keyword_1})-[*]-(b2:Breakthrough {name: $keyword_2}))
WHERE all(n IN nodes(p)
WHERE (n = b1 OR n = b2) OR labels(n)[0] = 'UNESCOconcept')
RETURN p
LIMIT $limit
"""
        params = {"keyword_1": keyword_1, "keyword_2": keyword_2, "limit": limit}
        self.last_query = query
        self.last_params = params

        formatted_results = []
        with self.driver.session() as session:
            result = session.run(query, params)
            for record in result:
                path = record["p"]
                nodes = path.nodes
                rels = path.relationships

                row = {}
                row["b1_name"] = nodes[0]["name"]
                row["b1_radar_version"] = nodes[0].get("radar_version")
                row["rel_type_1"] = rels[0].type

                # Add intermediate concepts and relationships
                for i in range(1, len(nodes) - 1):
                    row[f"concept_{i}"] = nodes[i].get("pref_label_en", nodes[i].get("name"))
                    if i < len(nodes) - 2:
                        row[f"skos_rel_{i}"] = rels[i].type

                row["rel_type_2"] = rels[-1].type
                row["b2_name"] = nodes[-1]["name"]
                row["b2_radar_version"] = nodes[-1].get("radar_version")
                row["distance"] = len(rels)

                formatted_results.append(row)

        return formatted_results

    def get_platform_overlap(
        self,
        platform_1: str,
        platform_2: str,
        latest_only: bool = True,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Find UNESCOconcepts shared between two named platforms.

        Returns concepts that appear in breakthroughs from both platforms,
        with the breakthrough lists from each side.

        Args:
            platform_1: First platform name keyword
            platform_2: Second platform name keyword
            latest_only: Restrict to is_latest breakthroughs if True
            limit: Maximum results

        Returns:
            List of dicts with keys: concept_name, p1_breakthroughs,
            p2_breakthroughs, overlap_score
        """
        query = """
MATCH (p1:Platform)-[:CONTAINS]->
      (:`Emerging topic`)-[:CONTAINS]->(b1:Breakthrough)
      -[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough)
      <-[:CONTAINS]-(:`Emerging topic`)<-[:CONTAINS]-(p2:Platform)
WHERE ($latest_only = false OR (b1.is_latest = true AND b2.is_latest = true))
  AND toLower(p1.name) CONTAINS toLower($platform_1)
  AND toLower(p2.name) CONTAINS toLower($platform_2)
  AND p1 <> p2
WITH uc,
     collect(DISTINCT b1.name) AS p1_breakthroughs,
     collect(DISTINCT b2.name) AS p2_breakthroughs,
     count(DISTINCT b1) * count(DISTINCT b2) AS overlap_score
RETURN uc.pref_label_en AS concept_name,
       p1_breakthroughs,
       p2_breakthroughs,
       overlap_score
ORDER BY overlap_score DESC
LIMIT $limit
"""
        return self._execute_query(
            query,
            {
                "platform_1": platform_1,
                "platform_2": platform_2,
                "latest_only": latest_only,
                "limit": limit,
            },
        )

    # -------------------------------------------------------------------------
    # Phase 4 — Impact scoring
    # -------------------------------------------------------------------------

    def get_breakthrough_sdg_impact(
        self,
        breakthrough_keyword: str,
        latest_only: bool = True,
        limit: int = 20,
        hops: int = 1,
    ) -> List[Dict]:
        """
        Score breakthroughs by how many distinct SDG targets they address.

        Answers "which renewable energy breakthroughs impact multiple SDG targets?".

        Args:
            breakthrough_keyword: Case-insensitive keyword matched against breakthrough names
            latest_only: Restrict to is_latest breakthroughs if True
            limit: Maximum results
            hops: Max concept hops via SKOS graph (1–3). Default 1.

        Returns:
            List of dicts with keys: breakthrough_name, platform_name,
            sdg_count, sdg_targets
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        if hops == 0:
            query = """
MATCH (p:Platform)-[:CONTAINS]->
      (:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
      -[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      -[:CONTRIBUTES_TO]->(t:SDGtarget)
WHERE ($latest_only = false OR (b.is_latest = true))
  AND toLower(b.name) CONTAINS toLower($keyword)
WITH b, p, count(DISTINCT t) AS sdg_count,
     collect(DISTINCT t.target_id) AS sdg_targets
RETURN b.name AS breakthrough_name,
       p.name AS platform_name,
       sdg_count,
       sdg_targets
ORDER BY sdg_count DESC, b.name ASC
LIMIT $limit
"""
        else:
            query = f"""
MATCH (p:Platform)-[:CONTAINS]->
      (:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
      -[:REQUIRES|ADVANCES]->(uc1:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{hops}]-(uc2:UNESCOconcept)
      -[:CONTRIBUTES_TO]->(t:SDGtarget)
WHERE ($latest_only = false OR (b.is_latest = true))
  AND toLower(b.name) CONTAINS toLower($keyword)
WITH b, p, count(DISTINCT t) AS sdg_count,
     collect(DISTINCT t.target_id) AS sdg_targets
RETURN b.name AS breakthrough_name,
       p.name AS platform_name,
       sdg_count,
       sdg_targets
ORDER BY sdg_count DESC, b.name ASC
LIMIT $limit
"""

        return self._execute_query(
            query,
            {
                "keyword": breakthrough_keyword,
                "latest_only": latest_only,
                "limit": limit,
            },
        )

    def rank_breakthroughs_by_sdg_impact(
        self,
        limit: int = 30,
        hops: int = 1,
        weight_by_ngoals: bool = True,
    ) -> List[Dict]:
        """
        Rank all latest-radar breakthroughs by how many SDG targets they address.

        weight_by_ngoals controls the scoring:
          True  (default): importance_score = n_sdg_targets * n_sdg_goals
          False:            rank by n_sdg_targets only

        Args:
            limit: Maximum results
            hops: Max SKOS concept hops (1–3)
            weight_by_ngoals: Weight by distinct SDG goals reached (default True)

        Returns:
            Ranked list with keys: breakthrough_name, n_sdg_targets,
            n_sdg_goals, importance_score
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        results = self._execute_query(
            _build_rank_breakthroughs_sdg_query(hops), {"limit": limit}
        )

        if not weight_by_ngoals:
            results.sort(key=lambda x: x.get("n_sdg_targets", 0), reverse=True)
        else:
            results.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

        return results[:limit]

    def get_breakthrough_platform_span(
        self,
        latest_only: bool = True,
        limit: int = 20,
        hops: int = 1,
        breakthrough_profile: str = "producer",
        weight_by_nplatforms: bool = True,
    ) -> List[Dict]:
        """
        Rank breakthroughs by how many distinct platforms their concepts connect to.

        breakthrough_profile controls the relationship direction:
          'all':      b -[:REQUIRES|ADVANCES]-> uc <-[:REQUIRES|ADVANCES]- b_other
          'producer': b -[:ADVANCES]-> uc <-[:REQUIRES]- b_other
          'receiver': b -[:REQUIRES]-> uc <-[:ADVANCES]- b_other

        hops expands concept matching via SKOS (IS_BROADER|IS_NARROWER) before
        checking for b_other connections.

        Args:
            latest_only: Restrict to is_latest breakthroughs if True
            limit: Maximum results
            hops: Max SKOS concept hops (1–3)
            breakthrough_profile: 'all', 'producer', or 'receiver'
            weight_by_platform_span: If True (default), rank by reached_breakthroughs * platform_span.
                                      If False, rank by reached_breakthroughs only.

        Returns:
            List of dicts with keys: breakthrough_name, reached_breakthroughs,
            platform_span, span_score
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")
        if breakthrough_profile not in _BREAKTHROUGH_SPAN_PROFILE_RELS:
            raise ValueError(f"breakthrough_profile must be 'all', 'producer', or 'receiver'; got {breakthrough_profile!r}")

        results = self._execute_query(
            _build_breakthrough_platform_span_query(breakthrough_profile, hops),
            {"latest_only": latest_only, "limit": limit},
        )

        if not weight_by_nplatforms:
            results.sort(key=lambda x: x.get("reached_breakthroughs", 0), reverse=True)
        else:
            results.sort(key=lambda x: x.get("span_score", 0), reverse=True)

        return results[:limit]

    def get_oecd_field_representation(
        self,
        latest_only: bool = True,
        limit: int = 30,
    ) -> List[Dict]:
        """
        Rank OECD research fields by how many radar breakthroughs map to them.

        Connection path: Breakthrough -[:REQUIRES|ADVANCES]-> UNESCOconcept
        <-[:IS_BROAD_MATCH|IS_EXACT_MATCH|IS_RELATED_CONCEPT]- OECDfield

        Args:
            latest_only: Restrict to is_latest breakthroughs if True
            limit: Maximum results

        Returns:
            List of dicts with keys: oecd_field, breakthrough_count, concept_count
        """
        query = """
MATCH (p:Platform)-[:CONTAINS]->
      (:`Emerging topic`)-[:CONTAINS]->(b:Breakthrough)
      -[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:IS_BROAD_MATCH|IS_EXACT_MATCH|IS_RELATED_CONCEPT]-(of:OECDfield)
WHERE ($latest_only = false OR (b.is_latest = true))
WITH of, count(DISTINCT b) AS breakthrough_count,
         count(DISTINCT uc) AS concept_count
RETURN of.name AS oecd_field,
       breakthrough_count,
       concept_count
ORDER BY breakthrough_count DESC
LIMIT $limit
"""
        return self._execute_query(
            query, {"latest_only": latest_only, "limit": limit}
        )

    # -------------------------------------------------------------------------
    # Phase 5 — Semantic enrichment
    # -------------------------------------------------------------------------

    def get_concept_neighborhood(
        self,
        concept_keyword: str,
        hops: int = 1,
        limit: int = 30,
    ) -> List[Dict]:
        """
        Return the local SKOS semantic neighborhood of a concept.

        Finds the concept matching the keyword (first result) then returns
        its broader, narrower, and cross-vocabulary neighbors.

        Args:
            concept_keyword: Case-insensitive keyword matched against concept pref_label_en
            hops: Neighborhood radius via IS_BROADER/IS_NARROWER (1–3)
            limit: Maximum neighbor results

        Returns:
            List of dicts with positional columns per hop depth, e.g. for hops=2:
            center_concept, relationship_1, neighbor_concept_1,
            relationship_2, neighbor_concept_2, distance
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        _center = """
MATCH (uc_center:UNESCOconcept)
WHERE toLower(uc_center.pref_label_en) CONTAINS toLower($concept_keyword)
WITH uc_center ORDER BY uc_center.pref_label_en ASC LIMIT 1
"""
        _rel = f":{_UC_SKOS_REL}"

        if hops == 1:
            query = _center + f"""
MATCH (uc_center)-[r1{_rel}]->(n1:UNESCOconcept)
RETURN uc_center.pref_label_en AS center_concept,
       type(r1) AS relationship_1,
       n1.pref_label_en AS neighbor_concept_1,
       1 AS distance
ORDER BY neighbor_concept_1 ASC
LIMIT $limit
"""
        elif hops == 2:
            query = _center + f"""
MATCH (uc_center)-[r1{_rel}]->(n1:UNESCOconcept)
      -[r2{_rel}]->(n2:UNESCOconcept)
WHERE n2 <> uc_center
RETURN uc_center.pref_label_en AS center_concept,
       type(r1) AS relationship_1,
       n1.pref_label_en AS neighbor_concept_1,
       type(r2) AS relationship_2,
       n2.pref_label_en AS neighbor_concept_2,
       2 AS distance
ORDER BY neighbor_concept_1 ASC, neighbor_concept_2 ASC
LIMIT $limit
"""
        else:  # hops == 3
            query = _center + f"""
MATCH (uc_center)-[r1{_rel}]->(n1:UNESCOconcept)
      -[r2{_rel}]->(n2:UNESCOconcept)
      -[r3{_rel}]->(n3:UNESCOconcept)
WHERE n3 <> uc_center AND n3 <> n1
RETURN uc_center.pref_label_en AS center_concept,
       type(r1) AS relationship_1,
       n1.pref_label_en AS neighbor_concept_1,
       type(r2) AS relationship_2,
       n2.pref_label_en AS neighbor_concept_2,
       type(r3) AS relationship_3,
       n3.pref_label_en AS neighbor_concept_3,
       3 AS distance
ORDER BY neighbor_concept_1 ASC, neighbor_concept_2 ASC, neighbor_concept_3 ASC
LIMIT $limit
"""
        return self._execute_query(query, {"concept_keyword": concept_keyword, "limit": limit})

    # -------------------------------------------------------------------------
    # Existing methods (preserved + enhanced)
    # -------------------------------------------------------------------------

    def get_breakthrough_links(
        self,
        breakthrough_1: str,
        breakthrough_2: str,
        hops: int = 1,
    ) -> List[Dict]:
        """
        Find concept paths between two breakthroughs via UNESCOconcept graph.

        hops is a maximum: hops=2 includes direct (1-hop) results too,
        with shorter paths returned first.

        Args:
            breakthrough_1: Name of first breakthrough
            breakthrough_2: Name of second breakthrough
            hops: Max concept hops (1–3). Default 1 for backward compatibility.

        Returns:
            List of dicts with keys: breakthrough_1, breakthrough_2, hops,
            concept_chain (list of concept labels), path_count
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        queries = {1: _LINK_QUERY_HOPS_1, 2: _LINK_QUERY_HOPS_2, 3: _LINK_QUERY_HOPS_3}
        return self._execute_query(
            queries[hops],
            {"breakthrough_1": breakthrough_1, "breakthrough_2": breakthrough_2},
        )

    def get_all_linked_breakthroughs(self, breakthrough_name: str) -> List[Dict]:
        """
        Find all breakthroughs linked to a given one via shared concepts.

        Args:
            breakthrough_name: Name of the reference breakthrough

        Returns:
            List of related breakthroughs with shared concept counts,
            platform context, and concept list
        """
        query = """
MATCH (b1:Breakthrough {name: $breakthrough_name})-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
      <-[:REQUIRES|ADVANCES]-(b2:Breakthrough)
      <-[:CONTAINS]-(:`Emerging topic`)<-[:CONTAINS]-(p:Platform)
WHERE b1 <> b2
RETURN DISTINCT b2.name AS related_breakthrough,
       p.name AS platform_name,
       count(uc) AS shared_concepts,
       collect(DISTINCT uc.pref_label_en) AS concepts
ORDER BY shared_concepts DESC
"""
        return self._execute_query(query, {"breakthrough_name": breakthrough_name})

    def get_concept_importance(
        self, limit: int = 30, latest_only: bool = True, hops: int = 1,
        weight_by_nplatforms: bool = True, relationships: str = "all",
    ) -> List[Dict]:
        """
        Get concepts ranked by importance metric.

        hops: maximum concept hops (1–3). Concepts reachable via up to n SKOS hops.
        weight_by_nplatforms: If True, rank by breakthrough_count * platform_span (importance).
                            If False, rank by breakthrough_count (centrality) only.
        relationships: Which relationship types to count — 'all' (REQUIRES + ADVANCES),
                       'requires_only', or 'advances_only'.

        Args:
            limit: Number of concepts to return
            latest_only: Filter to 2026 radar (is_latest=true) if True
            hops: Max concept hops (1–3). Default 1.
            weight_by_nplatforms: Weight by platform span (default True).
            relationships: Relationship filter — 'all', 'requires_only', or 'advances_only'.

        Returns:
            Ranked list of concepts with breakthrough_count and platform_span
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")
        if relationships not in _CONCEPT_IMPORTANCE_REL_PATTERNS:
            raise ValueError(f"relationships must be 'all', 'requires_only', or 'advances_only'; got {relationships!r}")

        query = _build_concept_importance_query(relationships, hops)
        results = self._execute_query(query, {"limit": limit, "latest_only": latest_only})

        # Sort by appropriate metric if weight_by_nplatforms is False
        if not weight_by_nplatforms:
            results.sort(key=lambda x: x.get("breakthrough_count", 0), reverse=True)
        else:
            results.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

        return results[:limit]

    def get_top_concepts(
        self, limit: int = 30, latest_only: bool = True, hops: int = 1
    ) -> List[Dict]:
        """Legacy alias for get_concept_importance with weight_by_nplatforms=True."""
        return self.get_concept_importance(
            limit=limit, latest_only=latest_only, hops=hops, weight_by_nplatforms=True
        )

    def get_concept_betweenness(self, limit: int = 30, hops: int = 1) -> List[Dict]:
        """Legacy alias for get_concept_importance with weight_by_nplatforms=False."""
        return self.get_concept_importance(
            limit=limit, latest_only=True, hops=hops, weight_by_nplatforms=False
        )

    def get_concept_importance_by_sdg(
        self, limit: int = 30, hops: int = 1, weight_by_nsdggoals: bool = True,
    ) -> List[Dict]:
        """
        Get concepts ranked by how many SDG targets they directly contribute to.

        Counts CONTRIBUTES_TO relationships per concept (n_sdgTargets_contributed).
        Optional weighting multiplies by the number of distinct SDGgoals reached
        via those targets (n_sdgGoals_contributed). SKOS hops expand which concepts aggregate
        contributions from their neighbourhood, mirroring the hops logic in
        get_concept_importance.

        Args:
            limit: Number of concepts to return
            hops: Max SKOS hops (1–3)
            weight_by_nsdggoals: If True (default), rank by n_sdgTargets_contributed * n_sdgGoals_contributed.
                                  If False, rank by n_sdgTargets_contributed only.

        Returns:
            Ranked list of concepts with n_sdgTargets_contributed, n_sdgGoals_contributed, and importance_score
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        results = self._execute_query(_build_concept_sdg_importance_query(hops), {"limit": limit})

        if not weight_by_nsdggoals:
            results.sort(key=lambda x: x.get("n_sdgTargets_contributed", 0), reverse=True)
        else:
            results.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

        return results[:limit]

    def get_concept_combined_importance(
        self, limit: int = 30, latest_only: bool = True, hops: int = 1,
        relationships: str = "all",
    ) -> List[Dict]:
        """
        Rank concepts by both their breakthrough connectivity and SDG target coverage.

        Combines get_concept_importance and get_concept_importance_by_sdg into a
        single query: for each concept, counts distinct breakthroughs connected via
        REQUIRES/ADVANCES and distinct SDG targets connected via CONTRIBUTES_TO.
        SKOS hops expand the concept neighbourhood for both signals.
        Both counts are normalized to [0, 1] by the max value in the result set,
        then summed into normalized_total which is the ranking metric.

        Args:
            limit: Number of concepts to return
            latest_only: Filter breakthroughs to is_latest=true if True
            hops: Max SKOS hops (0–3)
            relationships: Breakthrough relationship filter —
                           'all' (REQUIRES + ADVANCES), 'requires_only', or 'advances_only'.

        Returns:
            Ranked list with keys: concept_name, breakthrough_count, n_sdg_targets,
            combined_total, norm_breakthrough, norm_sdg_targets, normalized_total
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")
        if relationships not in _CONCEPT_IMPORTANCE_REL_PATTERNS:
            raise ValueError(f"relationships must be 'all', 'requires_only', or 'advances_only'; got {relationships!r}")

        rel = _CONCEPT_IMPORTANCE_REL_PATTERNS[relationships]

        if hops == 0:
            query = f"""
MATCH (uc:UNESCOconcept)
OPTIONAL MATCH (p:Platform)-[:CONTAINS]->(:`Emerging topic`)-[:CONTAINS]->
               (b:Breakthrough)-[:{rel}]->(uc)
WHERE ($latest_only = false OR b.is_latest = true)
WITH uc, count(DISTINCT b) AS breakthrough_count
OPTIONAL MATCH (uc)-[:CONTRIBUTES_TO]->(t:SDGtarget)
WITH uc, breakthrough_count, count(DISTINCT t) AS n_sdg_targets
RETURN uc.pref_label_en AS concept_name,
       breakthrough_count,
       n_sdg_targets
"""
            total_query_b = f"""
MATCH (uc:UNESCOconcept)
MATCH (b:Breakthrough)-[:{rel}]->(uc)
WHERE ($latest_only = false OR b.is_latest = true)
RETURN count(DISTINCT b) AS total
"""
            total_query_s = """
MATCH (uc:UNESCOconcept)-[:CONTRIBUTES_TO]->(t:SDGtarget)
RETURN count(DISTINCT t) AS total
"""
        else:
            query = f"""
MATCH (uc:UNESCOconcept)-[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
WITH uc_final
OPTIONAL MATCH (p:Platform)-[:CONTAINS]->(:`Emerging topic`)-[:CONTAINS]->
               (b:Breakthrough)-[:{rel}]->(uc_final)
WHERE ($latest_only = false OR b.is_latest = true)
WITH uc_final, count(DISTINCT b) AS breakthrough_count
OPTIONAL MATCH (uc_final)-[:CONTRIBUTES_TO]->(t:SDGtarget)
WITH uc_final, breakthrough_count, count(DISTINCT t) AS n_sdg_targets
RETURN uc_final.pref_label_en AS concept_name,
       breakthrough_count,
       n_sdg_targets
"""
            total_query_b = f"""
MATCH (uc:UNESCOconcept)-[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
MATCH (b:Breakthrough)-[:{rel}]->(uc_final)
WHERE ($latest_only = false OR b.is_latest = true)
RETURN count(DISTINCT b) AS total
"""
            total_query_s = f"""
MATCH (uc:UNESCOconcept)-[:{_UC_SKOS_REL}*0..{hops}]-(uc_final:UNESCOconcept)
MATCH (uc_final)-[:CONTRIBUTES_TO]->(t:SDGtarget)
RETURN count(DISTINCT t) AS total
"""

        all_results = self._execute_query(query, {"latest_only": latest_only})
        if not all_results:
            return all_results

        total_b = (self._execute_query(total_query_b, {"latest_only": latest_only}) or [{}])[0].get("total", 1) or 1
        total_s = (self._execute_query(total_query_s, {}) or [{}])[0].get("total", 1) or 1

        for r in all_results:
            r["norm_breakthrough"] = round(r["breakthrough_count"] / total_b, 4)
            r["norm_sdg_targets"]  = round(r["n_sdg_targets"] / total_s, 4)
            r["combined_total"]    = r["breakthrough_count"] + r["n_sdg_targets"]
            r["normalized_total"]  = round(r["norm_breakthrough"] + r["norm_sdg_targets"], 4)

        all_results.sort(key=lambda x: x["normalized_total"], reverse=True)
        return all_results[:limit]

    def get_concept_importance_for_sdgtarget(
        self, target_id: str, limit: int = 20, latest_only: bool = True, hops: int = 1
    ) -> List[Dict]:
        """
        Get top concepts for a specific SDG target.

        Args:
            target_id: SDGtarget identifier (e.g., "3.1" for SDG 3 target 1)
            limit: Number of concepts to return
            latest_only: Filter to 2026 radar (is_latest=true) if True
            hops: Max concept hops via SKOS graph (1–3)

        Returns:
            Ranked list of concepts contributing to that target, with breakthrough_count
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        queries = {
            1: f"""
MATCH (:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->
       (b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
       -[:CONTRIBUTES_TO]->(t:SDGtarget {{target_id: $target_id}})
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH uc, count(DISTINCT b) AS breakthrough_count
RETURN uc.pref_label_en AS concept_name,
       breakthrough_count
ORDER BY breakthrough_count DESC
LIMIT $limit
""",
            2: f"""
MATCH (:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->
       (b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
       -[:{_UC_SKOS_REL}*0..1]-(uc_final:UNESCOconcept)
       -[:CONTRIBUTES_TO]->(t:SDGtarget {{target_id: $target_id}})
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH uc_final, count(DISTINCT b) AS breakthrough_count
RETURN uc_final.pref_label_en AS concept_name,
       breakthrough_count
ORDER BY breakthrough_count DESC
LIMIT $limit
""",
            3: f"""
MATCH (:Platform)-[:CONTAINS]->(et:`Emerging topic`)-[:CONTAINS]->
       (b:Breakthrough)-[:REQUIRES|ADVANCES]->(uc:UNESCOconcept)
       -[:{_UC_SKOS_REL}*0..2]-(uc_final:UNESCOconcept)
       -[:CONTRIBUTES_TO]->(t:SDGtarget {{target_id: $target_id}})
WHERE ($latest_only = false OR (b.is_latest = true AND b_other.is_latest = true))
WITH uc_final, count(DISTINCT b) AS breakthrough_count
RETURN uc_final.pref_label_en AS concept_name,
       breakthrough_count
ORDER BY breakthrough_count DESC
LIMIT $limit
""",
        }

        return self._execute_query(
            queries[hops],
            {"target_id": target_id, "limit": limit, "latest_only": latest_only},
        )

    def get_concept_evolution(self, hops: int = 2) -> List[Dict]:
        """
        Compare concept importance across 2021, 2023, and 2026 radar editions.

        hops expands concept matching via SKOS (IS_BROADER|IS_NARROWER) before
        grouping, mirroring the hops logic in get_concept_importance.

        Args:
            hops: Max SKOS concept hops (1–3). Default 2.

        Returns:
            List of concepts appearing in all three editions with per-edition
            breakthrough counts (2026 first), pairwise deltas, and trend
            directions for 2023→2026, 2021→2023, and overall 2021→2026
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")

        depth = hops
        query = f"""
MATCH (b21:Breakthrough {{radar_version: 2021}})-[:REQUIRES|ADVANCES]->(uc21:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{depth}]-(uc21f:UNESCOconcept)
WITH uc21f.pref_label_en AS concept_name, count(DISTINCT b21) AS count_2021
MATCH (b23:Breakthrough {{radar_version: 2023}})-[:REQUIRES|ADVANCES]->(uc23:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{depth}]-(uc23f:UNESCOconcept)
WHERE uc23f.pref_label_en = concept_name
WITH concept_name, count_2021, count(DISTINCT b23) AS count_2023
MATCH (b26:Breakthrough {{radar_version: 2026}})-[:REQUIRES|ADVANCES]->(uc26:UNESCOconcept)
      -[:{_UC_SKOS_REL}*0..{depth}]-(uc26f:UNESCOconcept)
WHERE uc26f.pref_label_en = concept_name
WITH concept_name, count_2021, count_2023, count(DISTINCT b26) AS count_2026
RETURN concept_name,
       count_2026,
       count_2023,
       count_2021,
       count_2026 - count_2023 AS delta_2023_2026,
       count_2023 - count_2021 AS delta_2021_2023,
       count_2026 - count_2021 AS delta_overall,
       CASE WHEN count_2026 > count_2023 THEN 'RISING'
            WHEN count_2026 < count_2023 THEN 'FALLING'
            ELSE 'STABLE' END AS trend_2023_2026,
       CASE WHEN count_2023 > count_2021 THEN 'RISING'
            WHEN count_2023 < count_2021 THEN 'FALLING'
            ELSE 'STABLE' END AS trend_2021_2023,
       CASE WHEN count_2026 > count_2021 THEN 'RISING'
            WHEN count_2026 < count_2021 THEN 'FALLING'
            ELSE 'STABLE' END AS trend_overall
ORDER BY delta_overall DESC
"""
        return self._execute_query(query, {})

    def query_custom(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        """
        Execute custom Cypher query.

        Args:
            query: Raw Cypher query
            params: Query parameters (optional)

        Returns:
            Query results as list of dicts
        """
        return self._execute_query(query, params or {})

    def list_breakthroughs(self, limit: int = None) -> List[Dict]:
        """
        List all breakthroughs (optionally filtered to latest edition).
    
        Args:
            limit: Maximum number to return
    
        Returns:
            List of breakthrough nodes with all properties
        """
        query = "MATCH (b:Breakthrough) RETURN b"
        if limit:
            query += f" LIMIT {limit}"
        return self._execute_query(query, {})

    def list_concepts(self, limit: int = None) -> List[Dict]:
        """
        List all UNESCO concepts.
    
        Args:
            limit: Maximum number to return
    
        Returns:
            List of UNESCO concept nodes with all properties
        """
        query = "MATCH (uc:UNESCOconcept) RETURN uc"
        if limit:
            query += f" LIMIT {limit}"
        return self._execute_query(query, {})

    def list_sdg_goals(self) -> List[Dict]:
        """
        List all SDG goals.
    
        Returns:
            List of SDG goal nodes with all properties
        """
        query = "MATCH (g:SDGgoal) RETURN g ORDER BY g.goal_id"
        return self._execute_query(query, {})

    def list_sdg_indicators(self) -> List[Dict]:
        """
        List all SDG indicators.
    
        Returns:
            List of SDG indicator nodes with all properties
        """
        query = "MATCH (i:SDGindicator) RETURN i ORDER BY i.indicator_id"
        return self._execute_query(query, {})

    def list_sdg_targets(self, goal_id: str = None) -> List[Dict]:
        """
        List SDG targets, optionally filtered by goal.
    
        Args:
            goal_id: Optional SDGgoal ID to filter targets (e.g., "3" for SDG 3)
    
        Returns:
            List of SDG target nodes with all properties
        """
        if goal_id:
            query = """
    MATCH (g:SDGgoal {goal_id: $goal_id})-[:HAS_TARGET]->(t:SDGtarget)
    RETURN t
    ORDER BY t.target_id
    """
            return self._execute_query(query, {"goal_id": goal_id})
        else:
            query = "MATCH (t:SDGtarget) RETURN t ORDER BY t.target_id"
            return self._execute_query(query, {})

    def list_emerging_topics(self, limit: int = None) -> List[Dict]:
        """
        List all emerging topics.
    
        Args:
            limit: Maximum number to return
    
        Returns:
            List of emerging topic nodes with all properties
        """
        query = "MATCH (et:`Emerging topic`) RETURN et ORDER BY et.name"
        if limit:
            query += f" LIMIT {limit}"
        return self._execute_query(query, {})
    
    def list_platforms(self, limit: int = None) -> List[Dict]:
        """
        List all emerging topics.
    
        Args:
            limit: Maximum number to return
    
        Returns:
            List of emerging topic nodes with all properties
        """
        query = "MATCH (p:Platform) RETURN p ORDER BY p.name"
        if limit:
            query += f" LIMIT {limit}"
        return self._execute_query(query, {})
    

    def get_breakthrough_contributors_for_sdgtarget(
        self,
        target_id: str,
        limit: int = 10,
        latest_only: bool = True,
    ) -> List[Dict]:
        """
        Find breakthroughs that most directly contribute to a given SDG target.

        Path traversed (undirected shortestPath, no hop cap):
          (t:SDGtarget) <-[CONTRIBUTES_TO]- (uc) -[SKOS*]- (uc2) <-[REQUIRES|ADVANCES]- (b)

        Returns one row per shortest path, ranked by ascending distance (number of
        relationships). The result columns match the sdg_contributor shape detected
        by the UI: sdg_target_id, concept_1, [skos_rel_1, concept_2, ...], b_rel,
        breakthrough_name, radar_version, distance.

        Args:
            target_id: The SDGtarget target_id property (e.g. "3.1")
            limit: Number of paths to return (default 10)
            latest_only: Restrict to is_latest breakthroughs if True
        """
        # Build UNION of explicit hop patterns (0 SKOS hops = 2 rels total, up to 3 SKOS hops = 5 rels).
        # Each branch returns a consistent column set; unused concept/skos_rel columns are NULL.
        query = f"""
MATCH (t:SDGtarget {{target_id: $target_id}})
MATCH (t)<-[:CONTRIBUTES_TO]-(uc1:UNESCOconcept)<-[r1:ADVANCES]-(b:Breakthrough)
WHERE ($latest_only = false OR b.is_latest = true)
RETURN t.target_id AS sdg_target_id,
       uc1.pref_label_en AS concept_1,
       null AS skos_rel_1, null AS concept_2,
       null AS skos_rel_2, null AS concept_3,
       null AS skos_rel_3, null AS concept_4,
       type(r1) AS b_rel,
       b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       2 AS distance

UNION ALL

MATCH (t:SDGtarget {{target_id: $target_id}})
MATCH (t)<-[:CONTRIBUTES_TO]-(uc1:UNESCOconcept)
      -[sr1:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      <-[r1:ADVANCES]-(b:Breakthrough)
WHERE ($latest_only = false OR b.is_latest = true) AND uc1 <> uc2
RETURN t.target_id AS sdg_target_id,
       uc1.pref_label_en AS concept_1,
       type(sr1) AS skos_rel_1, uc2.pref_label_en AS concept_2,
       null AS skos_rel_2, null AS concept_3,
       null AS skos_rel_3, null AS concept_4,
       type(r1) AS b_rel,
       b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       3 AS distance

UNION ALL

MATCH (t:SDGtarget {{target_id: $target_id}})
MATCH (t)<-[:CONTRIBUTES_TO]-(uc1:UNESCOconcept)
      -[sr1:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      -[sr2:{_UC_SKOS_REL}]-(uc3:UNESCOconcept)
      <-[r1:ADVANCES]-(b:Breakthrough)
WHERE ($latest_only = false OR b.is_latest = true) AND uc1 <> uc2 AND uc2 <> uc3
RETURN t.target_id AS sdg_target_id,
       uc1.pref_label_en AS concept_1,
       type(sr1) AS skos_rel_1, uc2.pref_label_en AS concept_2,
       type(sr2) AS skos_rel_2, uc3.pref_label_en AS concept_3,
       null AS skos_rel_3, null AS concept_4,
       type(r1) AS b_rel,
       b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       4 AS distance

UNION ALL

MATCH (t:SDGtarget {{target_id: $target_id}})
MATCH (t)<-[:CONTRIBUTES_TO]-(uc1:UNESCOconcept)
      -[sr1:{_UC_SKOS_REL}]-(uc2:UNESCOconcept)
      -[sr2:{_UC_SKOS_REL}]-(uc3:UNESCOconcept)
      -[sr3:{_UC_SKOS_REL}]-(uc4:UNESCOconcept)
      <-[r1:ADVANCES]-(b:Breakthrough)
WHERE ($latest_only = false OR b.is_latest = true) AND uc1 <> uc2 AND uc2 <> uc3 AND uc3 <> uc4
RETURN t.target_id AS sdg_target_id,
       uc1.pref_label_en AS concept_1,
       type(sr1) AS skos_rel_1, uc2.pref_label_en AS concept_2,
       type(sr2) AS skos_rel_2, uc3.pref_label_en AS concept_3,
       type(sr3) AS skos_rel_3, uc4.pref_label_en AS concept_4,
       type(r1) AS b_rel,
       b.name AS breakthrough_name,
       b.radar_version AS radar_version,
       5 AS distance
"""
        params = {"target_id": target_id, "latest_only": latest_only, "limit": limit}
        self.last_query = query
        self.last_params = params

        # Deduplicate: keep only the shortest path per breakthrough
        seen: dict[str, dict] = {}
        with self.driver.session() as session:
            result = session.run(query, params)
            for record in result:
                row = dict(record)
                name = row["breakthrough_name"]
                if name not in seen or row["distance"] < seen[name]["distance"]:
                    seen[name] = row

        formatted = sorted(seen.values(), key=lambda r: (r["distance"], r["breakthrough_name"]))
        formatted = formatted[:limit]

        return formatted

    def get_breakthroughs_from_sdgtargets(
        self,
        target_ids: List[str],
        hops: int = 3,
        cost_function: str = "mean",
        limit: int = 50,
    ) -> List[Dict]:
        """
        Find breakthroughs connected to multiple SDGtarget nodes via up to n hops.

        Traverses from SDGtargets to UNESCOconcepts (via CONTRIBUTES_TO), then through
        the concept graph (IS_BROADER|IS_NARROWER|IS_RELATED_CONCEPT) up to the specified
        hops, then returns all breakthroughs connected to reached concepts.
        Each breakthrough is ranked by cost, which aggregates distances from all input
        targets using either mean or sum.

        Args:
            target_ids: List of SDGtarget IDs (e.g., "3.1", "5.2")
            hops: Maximum hops in concept graph (1-3). Default 3.
            cost_function: "mean" (avg distance) or "sum" (total distance). Default "mean".
            limit: Maximum breakthroughs to return

        Returns:
            List of dicts with keys: breakthrough_name, concept_count, distance_list,
            cost, platform_name
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")
        if cost_function not in ("mean", "sum"):
            raise ValueError(f"cost_function must be 'mean' or 'sum'; got {cost_function}")

        depth = hops
        query = f"""
WITH $target_ids AS input_target_ids
MATCH (input_target:SDGtarget)
WHERE input_target.target_id IN input_target_ids
MATCH (input_target)<-[:CONTRIBUTES_TO]-(input_uc:UNESCOconcept)
MATCH path = (input_uc)-[:{_UC_SKOS_REL}*0..{depth}]-(nearby_uc:UNESCOconcept)
MATCH (b:Breakthrough)-[:REQUIRES|ADVANCES]-(nearby_uc)
MATCH (p:Platform)-[:CONTAINS]-(:`Emerging topic`)-[:CONTAINS]-(b)
WITH b.name AS breakthrough_name,
     p.name AS platform_name,
     input_target.target_id AS input_target_id,
     length(path) AS distance_to_input
RETURN DISTINCT breakthrough_name, platform_name, input_target_id, distance_to_input
"""
        raw_results = self._execute_query(query, {"target_ids": target_ids})

        # Aggregate distances by breakthrough, tracking which targets are reached
        breakthrough_map = {}
        max_unreachable_distance = hops + 1

        for row in raw_results:
            b_name = row["breakthrough_name"]
            platform = row["platform_name"]
            input_target = row["input_target_id"]
            distance = row["distance_to_input"]

            if b_name not in breakthrough_map:
                breakthrough_map[b_name] = {
                    "breakthrough_name": b_name,
                    "platform_name": platform,
                    "distances": {},
                }

            if input_target not in breakthrough_map[b_name]["distances"]:
                breakthrough_map[b_name]["distances"][input_target] = distance
            else:
                breakthrough_map[b_name]["distances"][input_target] = min(
                    breakthrough_map[b_name]["distances"][input_target], distance
                )

        # Ensure every breakthrough has a distance for every input target
        results = []
        for b_name, data in breakthrough_map.items():
            distance_list = []
            for target_id in target_ids:
                if target_id in data["distances"]:
                    distance_list.append(data["distances"][target_id])
                else:
                    distance_list.append(max_unreachable_distance)

            if cost_function == "mean":
                cost = sum(distance_list) / len(distance_list) if distance_list else 0
            else:  # sum
                cost = sum(distance_list)

            results.append(
                {
                    "breakthrough_name": data["breakthrough_name"],
                    "platform_name": data["platform_name"],
                    "concept_count": len(target_ids),
                    "distance_list": distance_list,
                    "cost": cost,
                }
            )

        results.sort(key=lambda x: x["cost"])
        return results[:limit]

    def get_breakthroughs_from_concepts(
        self,
        concept_names: List[str],
        hops: int = 3,
        cost_function: str = "mean",
        filter_by: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Find breakthroughs connected to multiple UNESCOconcept nodes via up to n hops.

        Traverses the concept graph (IS_BROADER|IS_NARROWER|IS_RELATED_CONCEPT) up to
        the specified hops, then returns all breakthroughs connected to reached concepts.
        Each breakthrough is ranked by cost, which aggregates distances from all input
        concepts using either mean or sum.

        Args:
            concept_names: List of UNESCO concept pref_label_ens to start from
            hops: Maximum hops in concept graph (1-3). Default 3.
            cost_function: "mean" (avg distance) or "sum" (total distance). Default "mean".
            filter_by: Filter by relationship type - None (both), "advances", or "requires". Default None.
            limit: Maximum breakthroughs to return

        Returns:
            List of dicts with keys: breakthrough_name, concept_count, distance_list,
            cost, platform_name
        """
        if not isinstance(hops, int) or hops < 0:
            raise ValueError(f"hops must be a non-negative integer; got {hops}")
        if cost_function not in ("mean", "sum"):
            raise ValueError(f"cost_function must be 'mean' or 'sum'; got {cost_function}")
        if filter_by not in (None, "advances", "requires"):
            raise ValueError(f"filter_by must be None, 'advances', or 'requires'; got {filter_by}")

        depth = hops

        # Build the relationship filter
        if filter_by == "advances":
            rel_filter = "ADVANCES"
        elif filter_by == "requires":
            rel_filter = "REQUIRES"
        else:
            rel_filter = "REQUIRES|ADVANCES"

        query = f"""
WITH $concept_names AS input_concept_names
MATCH (input_uc:UNESCOconcept)
WHERE input_uc.pref_label_en IN input_concept_names
MATCH path = (input_uc)-[:{_UC_SKOS_REL}*0..{depth}]-(nearby_uc:UNESCOconcept)
MATCH (b:Breakthrough)-[:{rel_filter}]-(nearby_uc)
MATCH (p:Platform)-[:CONTAINS]-(:`Emerging topic`)-[:CONTAINS]-(b)
WITH b.name AS breakthrough_name,
     p.name AS platform_name,
     input_uc.pref_label_en AS input_concept,
     length(path) AS distance_to_input
RETURN DISTINCT breakthrough_name, platform_name, input_concept, distance_to_input
"""
        raw_results = self._execute_query(query, {"concept_names": concept_names})

        # Aggregate distances by breakthrough, tracking which concepts are reached
        breakthrough_map = {}
        max_unreachable_distance = hops + 1

        for row in raw_results:
            b_name = row["breakthrough_name"]
            platform = row["platform_name"]
            input_concept = row["input_concept"]
            distance = row["distance_to_input"]

            if b_name not in breakthrough_map:
                breakthrough_map[b_name] = {
                    "breakthrough_name": b_name,
                    "platform_name": platform,
                    "distances": {},
                }

            if input_concept not in breakthrough_map[b_name]["distances"]:
                breakthrough_map[b_name]["distances"][input_concept] = distance
            else:
                breakthrough_map[b_name]["distances"][input_concept] = min(
                    breakthrough_map[b_name]["distances"][input_concept], distance
                )

        # Ensure every breakthrough has a distance for every input concept
        results = []
        for b_name, data in breakthrough_map.items():
            distance_list = []
            for concept_name in concept_names:
                if concept_name in data["distances"]:
                    distance_list.append(data["distances"][concept_name])
                else:
                    distance_list.append(max_unreachable_distance)

            if cost_function == "mean":
                cost = sum(distance_list) / len(distance_list) if distance_list else 0
            else:  # sum
                cost = sum(distance_list)

            results.append(
                {
                    "breakthrough_name": data["breakthrough_name"],
                    "platform_name": data["platform_name"],
                    "concept_count": len(concept_names),
                    "distance_list": distance_list,
                    "cost": cost,
                }
            )

        results.sort(key=lambda x: x["cost"])
        return results[:limit]
