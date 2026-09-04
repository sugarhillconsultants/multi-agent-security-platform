"""
tests/manual_check_real_fusion.py

Manual, real-Accumulo test of mcp_servers/fusion_server.py's
real_accumulo_data_source. MUST be run from inside the `accumulo`
Docker container on the Secure Data Fusion Platform's Azure VM — not
from a laptop, unlike the other two manual integration tests. See
mcp_servers/fusion_server.py's module docstring for why.

NOT auto-discovered by pytest — see docs/incidents.md #7 for why.

Run from inside the accumulo container, e.g.:
  docker compose exec accumulo python3 tests/manual_check_real_fusion.py
(after copying this project's mcp_servers/, agents/, tests/ files and
the compiled AccumuloReader.class into that container first)
"""
import sys
sys.path.insert(0, ".")


def main():
    from agents.authorization import SessionContext
    from mcp_servers.fusion_tool_logic import query_fusion_data
    from mcp_servers.fusion_server import real_accumulo_data_source

    # Use whatever indicator is actually known to exist in the real,
    # already-populated cti_fusion table from Project 6's own session
    # — confirm the real value with `scan` in the Accumulo shell first
    # if this specific one doesn't return data.
    indicator = "10.29.188.213"

    print(f"Indicator: {indicator}\n")

    print("=== Session holding only U ===")
    session_u = SessionContext(session_id="test-u", held_authorizations={"U"})
    result_u = query_fusion_data(session_u, indicator, ["sensor", "enrichment", "attribution", "humint"], real_accumulo_data_source)
    print(f"Authorized: {list(result_u.authorized_data.keys())}")
    print(f"Denied: {[d['field'] for d in result_u.denied_fields]}")

    print()
    print("=== Fully cleared session ===")
    session_full = SessionContext(session_id="test-full", held_authorizations={"U", "S", "REL_TO_FVEY", "TS", "SI", "NOFORN"})
    result_full = query_fusion_data(session_full, indicator, ["sensor", "enrichment", "attribution", "humint"], real_accumulo_data_source)
    print(f"Authorized: {list(result_full.authorized_data.keys())}")
    print(f"Denied: {[d['field'] for d in result_full.denied_fields]}")
    print(f"Sample data: {result_full.authorized_data}")


if __name__ == "__main__":
    main()
