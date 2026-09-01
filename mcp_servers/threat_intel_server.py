"""
mcp_servers/threat_intel_server.py

MCP server wrapper around threat_intel_tool_logic.py's already-verified
logic (2/2 tests). Not executed in this project's dev environment —
see fusion_server.py's module docstring for the full explanation.
"""

from mcp.server.fastmcp import FastMCP

from agents.session_registry import get_session
from mcp_servers.threat_intel_tool_logic import query_threat_intel as _query_threat_intel_logic

mcp_server = FastMCP("threat-intel-agent")


def real_rag_data_source(query: str) -> list:
    """Placeholder for Project 5's real RAG /query endpoint. NOT
    implemented here — wiring this up means calling Project 5's
    actual deployed Hugging Face Space (see enterprise-rag-platform's
    README for the live endpoint), deferred to real deployment. Note:
    Project 5's current schema doesn't yet attach a per-document
    visibility label to retrieved chunks — adding that is a real,
    honest prerequisite for this integration to be more than a
    placeholder, not just a wiring exercise."""
    raise NotImplementedError(
        "Wire this up to Project 5's real /query endpoint once deployed, "
        "and add per-document visibility metadata to its retrieval schema "
        "first — see enterprise-rag-platform's docs/architecture.md"
    )


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
