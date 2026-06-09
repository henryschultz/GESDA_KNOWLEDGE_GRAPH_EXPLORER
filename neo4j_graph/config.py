"""Configuration settings for GESDA breakthrough prototype."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Neo4j Connection
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Query defaults
DEFAULT_CONCEPT_LIMIT = 30
DEFAULT_BREAKTHROUGH_LIMIT = 50
DEFAULT_RESULT_LIMIT = 20

# Radar editions
LATEST_EDITION = 2026
PREVIOUS_EDITION = 2023

# Graph constraints
MAX_HOPS = 3

# Performance settings
QUERY_TIMEOUT = 30  # seconds
CONNECTION_TIMEOUT = 10  # seconds
