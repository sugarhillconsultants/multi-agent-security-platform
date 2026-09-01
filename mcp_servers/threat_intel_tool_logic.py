"""
mcp_servers/threat_intel_tool_logic.py

The Threat Intel Agent's tool logic — wraps Project 5 (Enterprise RAG
Platform)'s `/query` endpoint. Unlike log events, retrieved threat
intel documents plausibly DO carry varying classification in a real
deployment (an open-source threat report is "U"; an internally-authored
assessment referencing a specific compromised asset might not be) — so
each retrieved document here carries its own visibility label, and
each one is authorized INDIVIDUALLY, matching the Fusion Agent's
per-field pattern rather than an all-or-nothing check on the whole
query.
"""

from dataclasses import dataclass, field
from typing import Callable

from agents.authorization import SessionContext, ToolCallRequest, authorize_tool_call

# In production, each retrieved document's visibility would be real
# metadata already attached to it (e.g. stored alongside the document
# in the RAG index, similar in spirit to Project 6's per-cell labels).
# The data_source here returns raw (text, visibility) pairs so the
# authorization check can be applied per-document, not just once for
# the whole query.
DataSourceFn = Callable[[str], list]  # returns list of (text, visibility) tuples


@dataclass
class ThreatIntelResult:
    query: str
    authorized_documents: list = field(default_factory=list)  # list of text
    denied_documents: list = field(default_factory=list)      # [{"reason": ...}]
    audit_trail: list = field(default_factory=list)


def query_threat_intel(session: SessionContext, query: str, data_source: DataSourceFn) -> ThreatIntelResult:
    """Retrieves candidate documents from data_source, then authorizes
    EACH ONE individually before including it in the result — a
    document the session isn't cleared for is excluded, with its
    content never even examined further, matching the same
    per-item, deny-before-use pattern as the Fusion Agent."""
    result = ThreatIntelResult(query=query)

    candidates = data_source(query)  # (text, visibility) pairs

    for text, visibility in candidates:
        request = ToolCallRequest(
            agent_name="ThreatIntelAgent",
            tool_name="query_threat_intel",
            required_visibility=visibility,
            description=f"Retrieved document for query '{query}' with visibility '{visibility}'",
        )
        decision = authorize_tool_call(request, session)
        result.audit_trail.append(decision)

        if decision.allowed:
            result.authorized_documents.append(text)
        else:
            result.denied_documents.append({"reason": decision.reason})

    return result
