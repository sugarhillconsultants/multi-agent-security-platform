"""
mcp_servers/threat_intel_server.py

MCP server wrapper around threat_intel_tool_logic.py's query_threat_intel.
`real_rag_data_source` below is a REAL implementation, not a stub —
it authenticates against Project 5's actual deployed Hugging Face
Space via OAuth2 password grant, then queries its real /query
endpoint, using field names confirmed directly from Project 5's live
/openapi.json (QueryRequest: query/top_k/candidates_before_rerank;
RetrievedChunk: chunk_id/text/score/visibility).

Requires two environment variables to actually work:
  RAG_PLATFORM_USERNAME, RAG_PLATFORM_PASSWORD

CONFIRMED WORKING: Project 5 was updated to add real per-document
visibility classification (U/S/TS) — see that project's own commit
history and docs/incidents.md here for the full account of that
change. Three test documents (U/S/TS) were ingested and queried live,
confirming each comes back with its correct, real label.
"""

import os
import time

from mcp.server.mcpserver import MCPServer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agents.session_registry import get_session
from mcp_servers.threat_intel_tool_logic import query_threat_intel as _query_threat_intel_logic

mcp_server = MCPServer("threat-intel-agent")

RAG_PLATFORM_BASE_URL = "https://oromeop-enterprise-rag-platform.hf.space"

_cached_token = {"access_token": None, "obtained_at": 0}
_TOKEN_TTL_SECONDS = 25 * 60


def _get_access_token() -> str:
    import requests

    now = time.time()
    if _cached_token["access_token"] and (now - _cached_token["obtained_at"]) < _TOKEN_TTL_SECONDS:
        return _cached_token["access_token"]

    username = os.environ.get("RAG_PLATFORM_USERNAME")
    password = os.environ.get("RAG_PLATFORM_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "RAG_PLATFORM_USERNAME and RAG_PLATFORM_PASSWORD must be set to "
            "authenticate against Project 5's real deployment."
        )

    response = requests.post(
        f"{RAG_PLATFORM_BASE_URL}/token",
        data={"username": username, "password": password, "grant_type": "password"},
        timeout=60,  # generous — Hugging Face Spaces can sleep and need a cold start
    )
    response.raise_for_status()
    token_data = response.json()

    _cached_token["access_token"] = token_data["access_token"]
    _cached_token["obtained_at"] = now
    return token_data["access_token"]


def real_rag_data_source(query: str) -> list:
    """Real implementation: authenticates against Project 5's live
    Hugging Face Space and queries its real /query endpoint, returning
    (text, visibility) pairs — visibility is now a REAL, confirmed
    field on every retrieved chunk, not a placeholder."""
    import requests

    token = _get_access_token()

    response = requests.post(
        f"{RAG_PLATFORM_BASE_URL}/query",
        json={"query": query, "top_k": 5},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    return [(r["text"], r["visibility"]) for r in data["results"]]


@mcp_server.tool()
def query_threat_intel(query: str, session_id: str) -> dict:
    """Retrieve threat intelligence documents relevant to the query,
    with per-document authorization checked before each document is
    included in the result."""
    session = get_session(session_id)
    result = _query_threat_intel_logic(session, query, real_rag_data_source)

    return {
        "query": result.query,
        "authorized_documents": result.authorized_documents,
        "denied_documents": result.denied_documents,
    }


if __name__ == "__main__":
    mcp_server.run()
