"""
mcp_servers/fusion_server.py

MCP server wrapper around fusion_tool_logic.py's already-verified
logic. This file is the thin, protocol-specific layer — written
against the `mcp` Python SDK's documented FastMCP API, but NOT
executed in this project's development environment, since no `mcp`
package (and no network to install it) exists there. The actual
security-critical logic this server exposes is fully tested
independently in fusion_tool_logic.py (5/5 tests) — this file's job
is just to expose that already-correct logic over the MCP protocol,
not to reimplement any of the logic itself.

In production, `real_accumulo_data_source` would call Project 6
(Secure Data Fusion Platform)'s actual Accumulo scan — not
reimplemented here, since Project 6 already has that logic built,
tested, and verified against a real cluster.
"""

from mcp.server.fastmcp import FastMCP

from agents.session_registry import get_session
from mcp_servers.fusion_tool_logic import query_fusion_data as _query_fusion_data_logic

mcp_server = FastMCP("fusion-agent")


def real_accumulo_data_source(indicator: str, family: str) -> dict | None:
    """Placeholder for Project 6's real Accumulo scan. NOT implemented
    here — wiring this up for real means calling Project 6's actual
    deployed Accumulo instance (see that project's docs/architecture.md
    for connection details), which is a live-infrastructure integration
    step deferred to actual deployment, the same way Project 5's real
    embedding model was deferred until deployed."""
    raise NotImplementedError(
        "Wire this up to Project 6's real Accumulo scan once deployed — "
        "see secure-data-fusion-platform's docs/architecture.md"
    )


@mcp_server.tool()
def query_fusion_data(indicator: str, requested_families: list[str], session_id: str) -> dict:
    """Query fused threat intelligence data for an indicator, with
    per-field authorization checked BEFORE any Accumulo access is
    attempted — a denied field is never queried, not just filtered
    from the response."""
    session = get_session(session_id)
    result = _query_fusion_data_logic(session, indicator, requested_families, real_accumulo_data_source)

    return {
        "indicator": result.indicator,
        "authorized_data": result.authorized_data,
        "denied_fields": result.denied_fields,
        "audit_trail": [
            {"tool": d.request.tool_name, "allowed": d.allowed, "reason": d.reason, "timestamp": d.timestamp}
            for d in result.audit_trail
        ],
    }


if __name__ == "__main__":
    mcp_server.run()
