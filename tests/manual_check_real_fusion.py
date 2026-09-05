"""
tests/manual_check_real_fusion.py

Manual, real-Accumulo test proving the actual security boundary
against the real, live cti_fusion table.

IMPORTANT — why this file's structure differs from
manual_check_real_log_platform.py and manual_check_real_threat_intel.py:
those two import their real data-source functions directly from their
respective mcp_servers/*_server.py files, since the `mcp` package was
installed on the machine those tests ran on (a laptop). This test
genuinely could not do the same: it has to run INSIDE the `accumulo`
Docker container itself (the only place `accumulo classpath` and the
compiled AccumuloReader.class exist), and installing the `mcp` SDK
there just to satisfy an import was unnecessary overhead for a
one-shot verification. So `real_accumulo_data_source` is defined
directly in this file — genuinely identical logic to
mcp_servers/fusion_server.py's version, just not imported from it —
rather than pretending this ran a path it didn't. See
docs/incidents.md #11 for the full account, including a first version
of this file that DID import from fusion_server.py but was never
actually the one executed.

NOT auto-discovered by pytest — see docs/incidents.md #7 for why.

Run from inside the accumulo container on the Secure Data Fusion
Platform's Azure VM, e.g.:
  docker compose exec accumulo python3 tests/manual_check_real_fusion.py
(after copying this file, agents/authorization.py,
security/visibility.py, and mcp_servers/fusion_tool_logic.py into that
container — see docs/incidents.md #11 for exactly how this was done)

Requires ACCUMULO_ROOT_PASSWORD set (matches the docker-compose
deployment's own value).
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def real_accumulo_data_source(indicator: str, family: str):
    """Genuinely identical logic to mcp_servers/fusion_server.py's
    function of the same name — duplicated here rather than imported,
    specifically to avoid needing the `mcp` package installed inside
    the accumulo container just to run this one-shot manual check. By
    the time this is called, agents/authorization.py has ALREADY
    authorized this specific request; this function only fetches
    already-cleared data, it makes no access-control decision itself."""
    password = os.environ.get("ACCUMULO_ROOT_PASSWORD")
    if not password:
        raise RuntimeError("ACCUMULO_ROOT_PASSWORD must be set to query the real Accumulo cluster.")

    cmd = (
        f'java -cp "$(accumulo classpath):/tmp" AccumuloReader '
        f'"{indicator}" "{family}" "cti_fusion" "docker-instance" "zookeeper:2181" "{password}"'
    )
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        return None

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


def main():
    from agents.authorization import SessionContext
    from mcp_servers.fusion_tool_logic import query_fusion_data

    # Confirmed via earlier manual testing to have real sensor,
    # enrichment, and attribution data (but genuinely no HUMINT entry
    # in the underlying synthetic dataset — see docs/incidents.md #11
    # for how that was verified rather than assumed to be a bug).
    indicator = "130.54.152.216"

    print(f"Indicator: {indicator}\n")

    print("=== Session holding only U ===")
    session_u = SessionContext(session_id="test-u", held_authorizations={"U"})
    result_u = query_fusion_data(session_u, indicator, ["sensor", "enrichment", "attribution", "humint"], real_accumulo_data_source)
    print(f"Authorized: {list(result_u.authorized_data.keys())}")
    print(f"Denied: {[d['field'] for d in result_u.denied_fields]}")

    print()
    print("=== Session holding U, S, REL_TO_FVEY (not TS) ===")
    session_s = SessionContext(session_id="test-s", held_authorizations={"U", "S", "REL_TO_FVEY"})
    result_s = query_fusion_data(session_s, indicator, ["sensor", "enrichment", "attribution", "humint"], real_accumulo_data_source)
    print(f"Authorized: {list(result_s.authorized_data.keys())}")
    print(f"Data: {result_s.authorized_data}")
    print(f"Denied: {[d['field'] for d in result_s.denied_fields]}")

    print()
    print("=== Fully cleared session ===")
    session_full = SessionContext(session_id="test-full", held_authorizations={"U", "S", "REL_TO_FVEY", "TS", "SI", "NOFORN"})
    result_full = query_fusion_data(session_full, indicator, ["sensor", "enrichment", "attribution", "humint"], real_accumulo_data_source)
    print(f"Authorized: {list(result_full.authorized_data.keys())}")
    print(f"Denied: {[d['field'] for d in result_full.denied_fields]}")

    print()
    print("=== Confirming a known HUMINT-bearing indicator returns real data (see docs/incidents.md #11) ===")
    result_humint = query_fusion_data(session_full, "133.185.255.161", ["humint"], real_accumulo_data_source)
    print(f"Authorized: {result_humint.authorized_data}")
    print(f"Denied: {result_humint.denied_fields}")


if __name__ == "__main__":
    main()
