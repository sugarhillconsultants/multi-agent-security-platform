"""
mcp_servers/fusion_tool_logic.py

The Fusion Agent's actual tool logic — separated from the MCP wire
protocol wrapper (fusion_server.py) so this can be tested fully
offline, with zero MCP SDK dependency. In production, `data_source`
would be Project 6's real Accumulo scan; here it's injected as a
parameter (dependency injection) so tests can verify behavior with a
controllable, call-counting mock — including the specific property
that makes this novel: a denied field must NEVER reach the data
source at all, not just have its result discarded afterward.

FIELD_VISIBILITY_MAP mirrors Project 6's actual schema exactly
(security-data-fusion-platform's ingestion/generator.py) — sensor and
enrichment cells are always "U", attribution is "S&REL_TO_FVEY",
HUMINT corroboration is "TS&SI&NOFORN". Keeping this mapping in sync
with the real system it fronts is a real, ongoing maintenance
responsibility — see docs/architecture.md.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.authorization import SessionContext, ToolCallRequest, AuthorizationDecision, authorize_tool_call

FIELD_VISIBILITY_MAP = {
    "sensor": "U",
    "enrichment": "U",
    "attribution": "S&REL_TO_FVEY",
    "humint": "TS&SI&NOFORN",
}

DataSourceFn = Callable[[str, str], Optional[dict]]


@dataclass
class FusionQueryResult:
    indicator: str
    authorized_data: dict = field(default_factory=dict)  # family -> data
    denied_fields: list = field(default_factory=list)     # [{"field": ..., "reason": ...}]
    audit_trail: list = field(default_factory=list)       # list[AuthorizationDecision]


def query_fusion_data(
    session: SessionContext,
    indicator: str,
    requested_families: list[str],
    data_source: DataSourceFn,
) -> FusionQueryResult:
    """For each requested data family, authorize BEFORE ever calling
    data_source — a denied field must produce zero calls to the
    underlying store, not just a discarded result. This is the actual
    security property this module exists to demonstrate."""
    result = FusionQueryResult(indicator=indicator)

    for family in requested_families:
        visibility = FIELD_VISIBILITY_MAP.get(family)

        if visibility is None:
            result.denied_fields.append({
                "field": family,
                "reason": f"Unknown data family '{family}' — no visibility mapping defined, denying by default",
            })
            continue

        request = ToolCallRequest(
            agent_name="FusionAgent",
            tool_name="query_fusion_data",
            required_visibility=visibility,
            description=f"Requesting '{family}' data for indicator {indicator}",
        )
        decision: AuthorizationDecision = authorize_tool_call(request, session)
        result.audit_trail.append(decision)

        if decision.allowed:
            value = data_source(indicator, family)
            if value is not None:
                result.authorized_data[family] = value
        else:
            result.denied_fields.append({"field": family, "reason": decision.reason})

    return result
