"""
tests/manual_check_real_planner.py

Manual, real-API test of agents/planner.py's plan_investigation() —
run this locally where ANTHROPIC_API_KEY and ANTHROPIC_WORKSPACE_ID
are actually set.

NOT auto-discovered by pytest — see manual_check_real_classifier.py's
module docstring and docs/incidents.md #7 for why this file is named
to avoid pytest's test_*.py collection pattern, and why the
executable logic is wrapped in if __name__ == "__main__":.

Run manually: python3 tests/manual_check_real_planner.py
"""
import sys
sys.path.insert(0, ".")


def main():
    from agents.planner import plan_investigation, plan_to_investigation_steps
    from mcp_servers.log_analysis_tool_logic import classify_log_text
    from mcp_servers.threat_intel_tool_logic import query_threat_intel
    from mcp_servers.fusion_tool_logic import query_fusion_data

    alert = (
        "Unusual outbound connection volume detected from internal host "
        "10.0.0.42 to external IP 185.220.101.47 over the past hour, "
        "flagged by the log anomaly classifier with high confidence."
    )

    print(f"Alert: {alert}\n")
    print("Calling Claude to decide how to investigate...\n")

    tool_use_blocks = plan_investigation(alert)

    print(f"Claude decided to call {len(tool_use_blocks)} tool(s):\n")
    for block in tool_use_blocks:
        print(f"  - {block.name}({block.input})")

    tool_map = {
        "classify_log_text": classify_log_text,
        "query_threat_intel": query_threat_intel,
        "query_fusion_data": query_fusion_data,
    }

    skipped = []
    steps = plan_to_investigation_steps(tool_use_blocks, tool_map, skipped_tools=skipped)
    print(f"\n{len(tool_use_blocks)} tool call(s) planned, {len(steps)} step(s) built, {len(skipped)} skipped.")
    if skipped:
        print(f"  SKIPPED (not in the tool map): {skipped}")
    print("Ready to hand to run_investigation().")


if __name__ == "__main__":
    main()
