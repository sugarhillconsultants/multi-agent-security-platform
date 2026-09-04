"""
tests/manual_check_real_threat_intel.py

Manual, real-API test proving the actual security boundary: Project 5
returns ALL matching documents regardless of classification (by
design — it has no per-user authorization concept); THIS project's
own authorization layer is what actually enforces clearance. This
script demonstrates that boundary against real, live data.

NOT auto-discovered by pytest — see docs/incidents.md #7 for why.
Run manually: python3 tests/manual_check_real_threat_intel.py

Requires RAG_PLATFORM_USERNAME and RAG_PLATFORM_PASSWORD set.
"""
import sys
sys.path.insert(0, ".")


def main():
    from agents.authorization import SessionContext
    from mcp_servers.threat_intel_tool_logic import query_threat_intel
    from mcp_servers.threat_intel_server import real_rag_data_source

    query_text = "ransomware-group-X APT-style-cluster-A attribution"

    print(f"Query: {query_text}")
    print("(First request may be slow — Hugging Face Spaces can sleep)\n")

    print("=== Session holding only U ===")
    session_u = SessionContext(session_id="test-u", held_authorizations={"U"})
    result_u = query_threat_intel(session_u, query_text, real_rag_data_source)
    print(f"Authorized documents: {len(result_u.authorized_documents)}")
    for doc in result_u.authorized_documents:
        print(f"  - {doc[:80]}")
    print(f"Denied: {len(result_u.denied_documents)}")

    print()
    print("=== Session holding U, S (not TS) ===")
    session_s = SessionContext(session_id="test-s", held_authorizations={"U", "S"})
    result_s = query_threat_intel(session_s, query_text, real_rag_data_source)
    print(f"Authorized documents: {len(result_s.authorized_documents)}")
    for doc in result_s.authorized_documents:
        print(f"  - {doc[:80]}")
    print(f"Denied: {len(result_s.denied_documents)}")

    print()
    print("=== Fully cleared session (U, S, TS) ===")
    session_full = SessionContext(session_id="test-full", held_authorizations={"U", "S", "TS"})
    result_full = query_threat_intel(session_full, query_text, real_rag_data_source)
    print(f"Authorized documents: {len(result_full.authorized_documents)}")
    for doc in result_full.authorized_documents:
        print(f"  - {doc[:80]}")
    print(f"Denied: {len(result_full.denied_documents)}")


if __name__ == "__main__":
    main()
