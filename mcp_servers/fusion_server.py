"""
mcp_servers/fusion_server.py

MCP server wrapper around fusion_tool_logic.py's already-verified
logic. `real_accumulo_data_source` below is a REAL implementation —
it invokes AccumuloReader.java (compiled the same way as Project 6's
AccumuloBulkWriter.java) via subprocess, since no reliable Python
client exists for Accumulo 2.x.

CRITICAL RUNTIME CONSTRAINT, unlike the log_analysis/threat_intel
integrations: this function invokes the `accumulo` CLI wrapper
internally (via `accumulo classpath`), which only exists inside the
`accumulo` Docker container on the Secure Data Fusion Platform's Azure
VM — not on a general-purpose machine. This MCP server must actually
run from inside that container, not from a laptop like the other two
integrations. See docs/incidents.md.

Requires:
  ACCUMULO_ROOT_PASSWORD (matches the docker-compose deployment)
  ACCUMULO_READER_DIR (directory containing the compiled
    AccumuloReader.class — defaults to /tmp, matching where
    AccumuloBulkWriter.class was compiled in Project 6's own session)
"""

import os
import subprocess

from mcp.server.mcpserver import MCPServer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agents.session_registry import get_session
from mcp_servers.fusion_tool_logic import query_fusion_data as _query_fusion_data_logic

mcp_server = MCPServer("fusion-agent")


def real_accumulo_data_source(indicator: str, family: str) -> dict:
    """Real implementation: invokes the compiled AccumuloReader.java
    program via subprocess. By the time this is called,
    agents/authorization.py has ALREADY authorized this specific
    request (per-field, before dispatch) — this function only fetches
    data, it doesn't make any access-control decision itself."""
    zookeepers = os.environ.get("ACCUMULO_ZOOKEEPERS", "zookeeper:2181")
    instance_name = os.environ.get("ACCUMULO_INSTANCE_NAME", "docker-instance")
    table_name = os.environ.get("ACCUMULO_TABLE_NAME", "cti_fusion")
    password = os.environ.get("ACCUMULO_ROOT_PASSWORD")
    reader_dir = os.environ.get("ACCUMULO_READER_DIR", "/tmp")

    if not password:
        raise RuntimeError("ACCUMULO_ROOT_PASSWORD must be set to query the real Accumulo cluster.")

    cmd = (
        f'java -cp "$(accumulo classpath):{reader_dir}" AccumuloReader '
        f'"{indicator}" "{family}" "{table_name}" "{instance_name}" "{zookeepers}" "{password}"'
    )

    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        raise RuntimeError(f"AccumuloReader failed (exit {result.returncode}): {result.stderr}")

    fields = {}
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        _row, _cf, cq, _visibility, value = parts
        fields[cq] = value

    return fields if fields else None


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
