"""
mcp_servers/log_analysis_server.py

MCP server wrapper around log_analysis_tool_logic.py's classify_log_text.
`real_log_platform_data_source` below is a REAL implementation, not a
stub — it authenticates against Project 1's actual deployed
Container App via OAuth2 password grant, then submits text to its
real /events endpoint, using field names and response shapes
confirmed directly from Project 1's live /openapi.json (LogEventIn:
text/source; LogEventOut: event_id/text/predicted_label/confidence).

Requires two environment variables to actually work:
  LOG_PLATFORM_USERNAME, LOG_PLATFORM_PASSWORD
NOT executed against the real live endpoint as part of this project's
own development/CI — genuinely first-run territory, same as every
other real-API integration in this portfolio. Project 1's Container
App is scaled to zero replicas (a deliberate cost-saving choice made
earlier), so the first real call here will incur a real cold-start
delay of some seconds — expected, not a bug.
"""

import os
import time

from mcp.server.mcpserver import MCPServer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agents.session_registry import get_session
from mcp_servers.log_analysis_tool_logic import classify_log_text as _classify_log_text_logic

mcp_server = MCPServer("log-analysis-agent")

LOG_PLATFORM_BASE_URL = "https://ca-log-anomaly.jollymushroom-46a3b9a7.eastus.azurecontainerapps.io"

# Simple in-process token cache — avoids re-authenticating on every
# single call. Not persisted across process restarts; fine for this
# project's scope, same "don't over-engineer past the actual need"
# judgment used throughout this portfolio.
_cached_token = {"access_token": None, "obtained_at": 0}
_TOKEN_TTL_SECONDS = 25 * 60  # refresh a bit before a typical 30-min JWT expiry, if that's what Project 1 uses


def _get_access_token() -> str:
    import requests

    now = time.time()
    if _cached_token["access_token"] and (now - _cached_token["obtained_at"]) < _TOKEN_TTL_SECONDS:
        return _cached_token["access_token"]

    username = os.environ.get("LOG_PLATFORM_USERNAME")
    password = os.environ.get("LOG_PLATFORM_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "LOG_PLATFORM_USERNAME and LOG_PLATFORM_PASSWORD must be set to "
            "authenticate against Project 1's real deployment."
        )

    response = requests.post(
        f"{LOG_PLATFORM_BASE_URL}/token",
        data={"username": username, "password": password, "grant_type": "password"},
        timeout=60,  # generous — first request may hit a cold start
    )
    response.raise_for_status()
    token_data = response.json()

    _cached_token["access_token"] = token_data["access_token"]
    _cached_token["obtained_at"] = now
    return token_data["access_token"]


def real_log_platform_data_source(text: str, source: str) -> dict:
    """Real implementation: authenticates against Project 1's live
    Container App and submits text to its real /events endpoint,
    returning the actual model's classification."""
    import requests

    token = _get_access_token()

    response = requests.post(
        f"{LOG_PLATFORM_BASE_URL}/events",
        json={"text": text, "source": source},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()  # real LogEventOut: event_id, text, predicted_label, confidence


@mcp_server.tool()
def classify_log_text(text: str, source: str, session_id: str) -> dict:
    """Submit a specific piece of log text to Project 1's real
    classifier for analysis. Routed through the same authorization
    framework as every other tool in this system."""
    session = get_session(session_id)
    result = _classify_log_text_logic(session, text, source, real_log_platform_data_source)

    return {
        "text": result.text,
        "source": result.source,
        "classification": result.classification,
        "denied": result.denied,
        "denial_reason": result.denial_reason,
    }


if __name__ == "__main__":
    mcp_server.run()
