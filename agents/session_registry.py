"""
agents/session_registry.py

MCP tool calls are stateless function invocations — there's no
built-in notion of "the current session's clearance" the way a
traditional web request might carry a session cookie. This is a
minimal, in-memory registry mapping a session_id to its
SessionContext, so each MCP tool handler can look up the correct
authorizations for whichever investigation session is calling it.

In-memory only, deliberately — a real production deployment would use
a real session store (Redis, a database), but that's an infrastructure
concern orthogonal to this project's actual point (the authorization
logic itself), and adding it would just be unverified complexity for
its own sake.
"""

from agents.authorization import SessionContext

_sessions: dict[str, SessionContext] = {}


def register_session(session_id: str, held_authorizations: set[str]) -> SessionContext:
    session = SessionContext(session_id=session_id, held_authorizations=held_authorizations)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> SessionContext:
    if session_id not in _sessions:
        raise KeyError(
            f"No session registered for session_id '{session_id}' — "
            f"a request with an unknown session_id must fail closed, "
            f"not be treated as having any default authorizations"
        )
    return _sessions[session_id]


def clear_all_sessions():
    """Test helper — resets the registry between test cases so tests
    don't leak state into each other."""
    _sessions.clear()
