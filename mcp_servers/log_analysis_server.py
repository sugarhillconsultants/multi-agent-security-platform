"""
mcp_servers/log_analysis_server.py

MCP server wrapper around log_analysis_tool_logic.py's already-verified
logic (2/2 tests). Not executed in this project's dev environment —
see fusion_server.py's module docstring for the full explanation of
why (no `mcp` package, no network to install it).
"""

from mcp.server.fastmcp import FastMCP

from agents.session_registry import get_session
from mcp_servers.log_analysis_tool_logic import query_log_events as _query_log_events_logic

mcp_server = FastMCP("log-analysis-agent")


def real_log_platform_data_source(query: str) -> list | None:
    """Placeholder for Project 1's real /events endpoint. NOT
    implemented here — wiring this up means calling Project 1's
    actual deployed FastAPI service (see log-anomaly-platform's
    README for the live endpoint), deferred to real deployment."""
    raise NotImplementedError(
        "Wire this up to Project 1's real /events endpoint once deployed — "
        "see log-anomaly-platform's README"
    )


@mcp_server.tool()
def query_log_events(query: str, session_id: str) -> dict:
    """Query log events matching the given search. Routed through the
    same authorization framework as every other tool in this system,
    even though log events are currently always "U" — a uniform
    security model, not a selective one."""
    session = get_session(session_id)
    result = _query_log_events_logic(session, query, real_log_platform_data_source)

    return {
        "query": result.query,
        "authorized_events": result.authorized_events,
        "denied": result.denied,
        "denial_reason": result.denial_reason,
    }


if __name__ == "__main__":
    mcp_server.run()
