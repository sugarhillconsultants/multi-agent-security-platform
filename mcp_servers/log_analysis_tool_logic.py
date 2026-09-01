"""
mcp_servers/log_analysis_tool_logic.py

The Log Analysis Agent's tool logic — wraps Project 1 (Log Anomaly
Detection Platform)'s `/events` endpoint. Log events there carry no
per-cell classification today (Project 1's schema is text/predicted_label/
confidence only), so every request here is genuinely always "U" —
but it's still routed through the SAME authorize_tool_call() framework
as the Fusion Agent, not given a bypass. This is a deliberate design
choice: a uniform security model that every tool goes through
consistently is a real, meaningfully different property than a model
where only the "obviously classified" tool gets checked and everything
else is implicitly trusted — the latter is exactly the kind of gap a
real security review would flag.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.authorization import SessionContext, ToolCallRequest, authorize_tool_call

DataSourceFn = Callable[[str], Optional[list]]


@dataclass
class LogAnalysisResult:
    query: str
    authorized_events: list = field(default_factory=list)
    denied: bool = False
    denial_reason: str = ""
    audit_trail: list = field(default_factory=list)


def query_log_events(session: SessionContext, query: str, data_source: DataSourceFn) -> LogAnalysisResult:
    """Log events are always "U" in Project 1's current design — but
    the request still goes through the real authorization check rather
    than skipping it, so the audit trail is complete and uniform across
    every tool in this system, not just the ones that happen to ever
    actually deny something."""
    request = ToolCallRequest(
        agent_name="LogAnalysisAgent",
        tool_name="query_log_events",
        required_visibility="U",
        description=f"Querying log events matching: {query}",
    )
    decision = authorize_tool_call(request, session)

    result = LogAnalysisResult(query=query, audit_trail=[decision])

    if decision.allowed:
        result.authorized_events = data_source(query) or []
    else:
        result.denied = True
        result.denial_reason = decision.reason

    return result
