"""
tests/manual_check_real_log_platform.py

Manual, real-API test of mcp_servers/log_analysis_server.py's
real_log_platform_data_source — run this locally where
LOG_PLATFORM_USERNAME and LOG_PLATFORM_PASSWORD are actually set.

NOT auto-discovered by pytest — see docs/incidents.md #7 for why.
Run manually: python3 tests/manual_check_real_log_platform.py

CONFIRMED WORKING (docs/incidents.md #9): real OAuth2 authentication
against Project 1's live Container App (username `analyst`, password
the deployment's own fallback default `changeme123` — DEMO_PASSWORD
was never set on the live deployment, confirmed via `az containerapp
show`), a real ~15s cold start survived (the app is deliberately
scaled to zero), and a real classification returned from the actual
deployed model.
"""
import sys
sys.path.insert(0, ".")


def main():
    from agents.authorization import SessionContext
    from mcp_servers.log_analysis_tool_logic import classify_log_text
    from mcp_servers.log_analysis_server import real_log_platform_data_source

    session = SessionContext(session_id="manual-test", held_authorizations={"U"})

    suspicious_text = "Failed login attempt x47 for user root from 185.220.101.47 within 60 seconds"

    print(f"Submitting: {suspicious_text}")
    print("(First request may take 10-30+ seconds — Project 1's Container App is scaled to zero)\n")

    result = classify_log_text(session, suspicious_text, "auth-service", real_log_platform_data_source)

    print(f"Denied: {result.denied}")
    print(f"Classification: {result.classification}")


if __name__ == "__main__":
    main()
