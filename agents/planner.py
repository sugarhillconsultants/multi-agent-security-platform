"""
agents/planner.py

The actual agent reasoning layer this project's design has deferred
until now: given an initial alert, ask Claude to decide which tools to
call and with what arguments, using Claude's native tool-use
mechanism (the correct, current way to do this — not asking the model
to write JSON in free text).

This produces a PLAN — a list of tool calls Claude decided to make —
which is then converted into `agents.orchestrator.InvestigationStep`
objects and handed to `run_investigation()`, the same
already-verified, 18-test-covered orchestrator that has nothing to do
with whether the plan came from a hardcoded test list or a real LLM
decision. This separation is deliberate: the planner's correctness
(did Claude choose sensible tools) is a different question from the
orchestrator's correctness (does dispatch happen reliably, does a
failure get handled gracefully) — this file only concerns the former.

NOT covered by this project's automated test suite — genuinely cannot
be, since Claude's exact tool-selection decisions for a given prompt
aren't guaranteed identical run to run. Verified manually instead, the
same way guardrails/injection_screening.py's real classifier was.
"""

import os

# The same three tools already exposed as MCP servers in mcp_servers/ —
# described here as Claude tool-use schemas rather than MCP tool
# definitions, since the planner calls the LLM directly rather than
# going through the MCP protocol layer itself.
INVESTIGATION_TOOLS = [
    {
        "name": "classify_log_text",
        "description": (
            "Submit a SPECIFIC piece of suspicious log text to Project 1's "
            "real classifier and get back its actual prediction "
            "(predicted_label, confidence). Project 1 does not support "
            "searching historical events by keyword — only classifying a "
            "specific piece of text you provide. Use this for any alert "
            "that includes or references specific log content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The specific log text to classify"},
                "source": {"type": "string", "description": "The originating system this log text came from"},
            },
            "required": ["text", "source"],
        },
    },
    {
        "name": "query_threat_intel",
        "description": (
            "Search Project 5's threat intelligence RAG platform for "
            "relevant reports, known actor attribution, or technique "
            "descriptions. Use this to check if an indicator or pattern "
            "matches known threat activity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What threat intelligence to search for"}},
            "required": ["query"],
        },
    },
    {
        "name": "query_fusion_data",
        "description": (
            "Query Project 6's fused, classification-aware threat data for "
            "a SPECIFIC indicator (e.g. an IP address). Returns whatever "
            "data families the current session is cleared to see — some "
            "may be denied depending on classification. Use this only "
            "once you have a specific indicator to investigate, not for "
            "open-ended searches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "description": "The specific indicator to look up, e.g. an IP address"},
                "requested_families": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Which data families to request: sensor, enrichment, attribution, humint",
                },
            },
            "required": ["indicator", "requested_families"],
        },
    },
]


def plan_investigation(alert_description: str):
    """Calls Claude with the alert and the available tools, returns the
    raw tool_use blocks Claude decided to invoke — the PLAN, not yet
    executed. NOT run in this project's automated test suite — requires
    a real ANTHROPIC_API_KEY and ANTHROPIC_WORKSPACE_ID, the same as
    guardrails/injection_screening.py's real classifier."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        tools=INVESTIGATION_TOOLS,
        messages=[{
            "role": "user",
            "content": (
                f"A security alert was raised: {alert_description}\n\n"
                f"Decide which tools to call to investigate this alert. "
                f"You may call multiple tools. Start broad (logs, threat "
                f"intel) before querying fusion data for a specific "
                f"indicator, once you have one."
            ),
        }],
        extra_headers={"anthropic-workspace-id": workspace_id} if workspace_id else {},
    )

    return [block for block in response.content if block.type == "tool_use"]


def plan_to_investigation_steps(tool_use_blocks, tool_name_to_function: dict, extra_kwargs_by_tool: dict = None):
    """Converts Claude's raw tool_use blocks into
    agents.orchestrator.InvestigationStep objects. Pure, deterministic
    conversion logic — fully testable without any LLM call, given a
    fixed set of tool_use blocks (e.g. captured from a real run, or
    constructed by hand to simulate one).

    SECURITY NOTE: `extra_kwargs_by_tool` exists specifically so the
    calling code — never Claude — injects `session`/`data_source`
    parameters. Claude decides WHAT to investigate; it must never be
    in a position to specify WHICH session's authorizations a tool
    call runs under. Merging extra_kwargs AFTER Claude's own `input`
    dict means a caller could also use this to override any field
    Claude provided, which is intentional: the calling code's values
    always take precedence over whatever the model produced."""
    from agents.orchestrator import InvestigationStep

    extra_kwargs_by_tool = extra_kwargs_by_tool or {}
    steps = []

    for block in tool_use_blocks:
        tool_fn = tool_name_to_function.get(block.name)
        if tool_fn is None:
            continue  # Claude named a tool that doesn't exist in our mapping — skip, don't crash the whole plan
        kwargs = dict(block.input)
        kwargs.update(extra_kwargs_by_tool.get(block.name, {}))
        steps.append(InvestigationStep(agent_name=block.name, tool_fn=tool_fn, kwargs=kwargs))

    return steps
