"""
tests/test_real_planner_manual.py

Manual, real-API test of agents/planner.py's plan_investigation() —
run this locally where ANTHROPIC_API_KEY and ANTHROPIC_WORKSPACE_ID
are actually set. This is genuinely the first execution of this
function anywhere; written but never run until now.

NOT run in CI — requires real credentials. Run manually:
python3 tests/test_real_planner_manual.py
"""
import sys
sys.path.insert(0, ".")

from agents.planner import plan_investigation, plan_to_investigation_steps
from mcp_servers.log_analysis_tool_logic import query_log_events
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
    "query_log_events": query_log_events,
    "query_threat_intel": query_threat_intel,
    "query_fusion_data": query_fusion_data,
}

steps = plan_to_investigation_steps(tool_use_blocks, tool_map)
print(f"\nConverted to {len(steps)} InvestigationStep(s) — ready to hand to run_investigation().")
