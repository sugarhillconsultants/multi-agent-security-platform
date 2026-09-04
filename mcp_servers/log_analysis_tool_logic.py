"""
mcp_servers/log_analysis_tool_logic.py

Renamed from `query_log_events` to `classify_log_text` — a real,
confirmed correction, not a stylistic choice. The original design
assumed Project 1 exposed a "search my past events for X" endpoint,
mirroring how a search index typically works. Checking Project 1's
actual live OpenAPI spec directly revealed no such endpoint exists at
all: the real API only supports submitting a specific piece of log
text and getting back a live classification (`POST /events`), plus
looking up one already-classified event by its numeric ID
(`GET /events/{event_id}`). There is no free-text search capability.
Renaming the tool to match what the system actually does, rather than
keeping a name that implies a capability that was never real. See
docs/incidents.md.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.authorization import SessionContext, ToolCallRequest, authorize_tool_call

DataSourceFn = Callable[[str, str], Optional[dict]]


@dataclass
class LogClassificationResult:
    text: str
    source: str
    classification: dict = field(default_factory=dict)
    denied: bool = False
    denial_reason: str = ""
    audit_trail: list = field(default_factory=list)


def classify_log_text(session: SessionContext, text: str, source: str, data_source: DataSourceFn) -> LogClassificationResult:
    """Submits a specific piece of log text to Project 1's real
    classifier and returns its actual prediction. Log events are
    always "U" in Project 1's current design — but the request still
    goes through the real authorization check rather than skipping
    it, so the audit trail is complete and uniform across every tool
    in this system, not just the ones that happen to ever actually
    deny something."""
    request = ToolCallRequest(
        agent_name="LogAnalysisAgent",
        tool_name="classify_log_text",
        required_visibility="U",
        description=f"Classifying log text from source '{source}': {text[:80]}",
    )
    decision = authorize_tool_call(request, session)

    result = LogClassificationResult(text=text, source=source, audit_trail=[decision])

    if decision.allowed:
        classification = data_source(text, source)
        if classification is not None:
            result.classification = classification
    else:
        result.denied = True
        result.denial_reason = decision.reason

    return result
