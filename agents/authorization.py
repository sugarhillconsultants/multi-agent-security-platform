"""
agents/authorization.py

The genuinely novel piece of this project: most multi-agent systems
let any agent call any tool and rely entirely on the tool itself to
enforce access control (exactly what Project 6's Accumulo layer does
correctly, on its own). This module adds a second, earlier layer:
the ORCHESTRATOR reasons about whether a proposed tool call should
even be DISPATCHED, given the current investigation session's held
authorizations — before any request reaches Project 6's Fusion Agent
or Accumulo at all.

Why this matters, concretely: without this layer, an agent could
legitimately attempt a request for TS-level data on behalf of a
session that only holds S-level clearance. Accumulo would correctly
deny the actual data — but the attempt itself would still happen,
still cost a round-trip, and (more importantly for a real system)
would need to be logged and explained as a DENIED action rather than
silently never having been attempted. This layer prevents the
attempt in the first place and produces an explicit, auditable
authorization decision — feeding directly into this project's tracing/
observability requirement, not a bolt-on afterthought.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from security.visibility import evaluate_visibility, VisibilityParseError


@dataclass
class SessionContext:
    """The current investigation session's held authorizations —
    analogous to what a real analyst's clearance would be, checked
    once per session rather than re-derived per request."""
    session_id: str
    held_authorizations: set[str]


@dataclass
class ToolCallRequest:
    """A proposed tool call an agent wants to make. `required_visibility`
    is the classification expression the REQUESTED DATA would carry —
    e.g. an agent asking the Fusion Agent for HUMINT-derived
    attribution would set this to "TS&SI&NOFORN", matching exactly the
    label Project 6's real Accumulo table uses for that data. This is
    intentionally the SAME expression syntax as Project 6's cell
    visibility labels — the whole point is reusing one real,
    already-verified evaluation model across both layers, not
    inventing a second, parallel authorization scheme that could
    silently drift from the first."""
    agent_name: str
    tool_name: str
    required_visibility: str
    description: str = ""


@dataclass
class AuthorizationDecision:
    """An explicit, auditable record of why a tool call was allowed or
    denied — not just a bare boolean. Every field here is meant to be
    logged, not just returned and discarded, since a real security
    review needs to see WHY, not just what happened."""
    request: ToolCallRequest
    session_id: str
    allowed: bool
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def authorize_tool_call(request: ToolCallRequest, session: SessionContext) -> AuthorizationDecision:
    """The actual pre-dispatch authorization check. Returns a decision
    that should be logged regardless of outcome — a DENIED decision is
    just as important an audit record as an ALLOWED one, arguably more
    so."""
    try:
        allowed = evaluate_visibility(request.required_visibility, session.held_authorizations)
    except VisibilityParseError as e:
        # A malformed visibility expression is NOT the same as "denied"
        # — it's a real error in how the request itself was constructed,
        # and should fail closed (deny) rather than silently succeed,
        # matching this whole portfolio's consistent stance that
        # ambiguous/malformed security expressions must never be
        # resolved permissively.
        return AuthorizationDecision(
            request=request,
            session_id=session.session_id,
            allowed=False,
            reason=f"Malformed visibility expression, denying by default: {e}",
        )

    if allowed:
        reason = (
            f"Session {session.session_id} holds authorizations "
            f"{sorted(session.held_authorizations)}, satisfying "
            f"required visibility '{request.required_visibility}'"
        )
    else:
        reason = (
            f"Session {session.session_id} holds authorizations "
            f"{sorted(session.held_authorizations)}, which do NOT satisfy "
            f"required visibility '{request.required_visibility}' — "
            f"tool call blocked before dispatch, not attempted"
        )

    return AuthorizationDecision(
        request=request,
        session_id=session.session_id,
        allowed=allowed,
        reason=reason,
    )
