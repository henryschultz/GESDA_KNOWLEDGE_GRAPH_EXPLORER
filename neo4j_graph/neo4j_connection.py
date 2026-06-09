import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError

load_dotenv(Path(__file__).parent / ".env")


class Neo4jConnection:
    """Manages Neo4j Aura connection and provides basic operations."""

    def __init__(self, uri: str = None, username: str = None, password: str = None):
        """
        Initialize connection to Neo4j Aura.

        Args:
            uri: Neo4j connection URI (or NEO4J_URI env var)
            username: Username (or NEO4J_USERNAME env var)
            password: Password (or NEO4J_PASSWORD env var)
        """
        self.uri = uri or os.getenv("NEO4J_URI")
        self.username = username or os.getenv("NEO4J_USERNAME")
        self.password = password or os.getenv("NEO4J_PASSWORD")

        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Neo4j credentials required. Set NEO4J_URI, NEO4J_USERNAME, "
                "NEO4J_PASSWORD env vars or pass as arguments."
            )

        self.driver = None

    def connect(self) -> Driver:
        """
        Establish connection to Neo4j Aura.

        Returns:
            neo4j.Driver instance

        Raises:
            ServiceUnavailable: If cannot connect
            AuthError: If authentication fails
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✓ Connected to Neo4j Aura")
            return self.driver
        except AuthError as e:
            raise AuthError(f"Authentication failed: {e}")
        except ServiceUnavailable as e:
            raise ServiceUnavailable(f"Cannot connect to Neo4j: {e}")

    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()
            print("✓ Connection closed")

    def get_summary(self) -> dict:
        """
        Get summary statistics about the graph.

        Returns:
            Dictionary with node counts, relationship counts
        """
        if not self.driver:
            raise RuntimeError("Not connected. Call connect() first.")

        with self.driver.session() as session:
            # Node counts by type
            node_result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS type, count(n) AS count
                ORDER BY count DESC
            """)
            nodes = {record["type"]: record["count"] for record in node_result}

            # Relationship counts
            rel_result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS rel_type, count(r) AS count
                ORDER BY count DESC
            """)
            relationships = {record["rel_type"]: record["count"] for record in rel_result}

            # Total counts
            total_nodes = session.run("MATCH (n) RETURN count(n) AS total").single()["total"]
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS total").single()["total"]

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "node_types": nodes,
            "relationship_types": relationships,
        }

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
