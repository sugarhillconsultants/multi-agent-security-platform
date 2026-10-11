# Multi-Agent Security Operations Platform

The seventh project in this portfolio — a merged design covering the
two remaining reference categories (Multi-Agent orchestration and
Secure LLM Gateway), rather than treating them as separate projects,
since current job postings and 2026 hiring guides consistently bundle
"agent orchestration" together with "prompt injection defense" and
"tool misuse prevention" as one skill set, not two.

Extends the security-analyst narrative already running through
Projects 1, 4, 5, and 6: an Orchestrator delegates to specialist
agents — a **Log Analysis Agent** (Project 1's classifier), a
**Threat Intel Agent** (Project 5's RAG platform), and a **Fusion
Agent** (Project 6's Accumulo cell-level security) — each exposed as a
proper MCP server, with a pre-dispatch authorization layer and a
prompt-injection guardrail sitting in front of the agents' actual
reasoning.

## The actual thesis, provable in code

Most multi-agent systems let any agent call any tool and rely entirely
on the tool to enforce access control. This project adds a second,
earlier layer: the orchestrator reasons about whether a proposed tool
call should even be **dispatched**, given the current investigation
session's held clearance — reusing Project 6's own already-proven
visibility model, not a parallel, potentially-drifting reimplementation
of it.

This isn't asserted, it's proven: 30 tests, including the property
that actually matters —
`tests/test_agents.py::test_fusion_denied_field_never_reaches_data_source`
confirms a denied request produces **zero calls** to the underlying
data source, not just a discarded result.

## Status: fully verified end to end — all three tool integrations, the real LLM classifier, the real agent planner, and all three MCP servers confirmed against live infrastructure

Every module in `agents/`, `mcp_servers/*_tool_logic.py`, and
`guardrails/`'s integration logic runs with zero external dependencies
— no network, no LLM, no MCP SDK required for the 30-test core suite,
which includes a real bug caught and fixed before ever being presented
(see [`docs/incidents.md`](docs/incidents.md) #1) and a genuine edge
case (a session with zero authorizations, not even the lowest tier,
must be denied) found specifically by writing the test, not planned
for in advance (#2).

Beyond that core suite, every piece originally flagged as "correct but
unexecuted" has since been run for real: the LLM-based injection
classifier against Claude's actual API, correctly distinguishing
genuine injection attempts from content merely discussing them (#4);
the agent planner, producing a sensible, correctly-ordered
investigation plan for a real alert (#6); and all three MCP servers,
confirmed working through a real MCP Inspector client, including the
fail-closed security behavior firing correctly through a genuine
protocol round-trip (#5). All three tool integrations — Log Analysis
(Project 1), Threat Intel (Project 5), and Fusion (Project 6) — are
verified end to end against real, live, deployed infrastructure,
including a live security boundary proven across separate clearance
levels for each of Projects 5 and 6 (#9, #10, #11).

Full breakdown of what's verified and what remains open:
[`docs/architecture.md`](docs/architecture.md).

## Related: AI Red-Teaming / Adversarial AI Testing Platform

This project's own defenses — the injection classifier and the agent
planner — have been systematically attacked by a dedicated companion
project, [ai-redteam-platform](https://github.com/sugarhillconsultants/ai-redteam-platform),
using Microsoft's real PyRIT framework across three escalating tiers.
It found and reported a genuine planner-level vulnerability (indirect
injection via alert content manipulating tool selection toward
sensitive data), which this project's authorization layer fully
contained — real evidence that the defense-in-depth design holds under
active adversarial pressure, not just in isolated tests.

## What's actually in this repo

| Path | What it does | Verified? |
|---|---|---|
| `security/visibility.py` | Accumulo-style visibility parser, reused directly from Project 6 | **Yes** — same proven logic |
| `agents/authorization.py` | Pre-dispatch tool-call authorization, fail-closed | **Yes** — 5 tests |
| `agents/session_registry.py` | Session-to-authorization lookup | **Yes** — 2 tests |
| `mcp_servers/fusion_tool_logic.py` | Fusion Agent's per-field authorization logic, plus argument validation for the real reader | **Yes** — 7 tests |
| `mcp_servers/log_analysis_tool_logic.py` | Log Analysis Agent's logic | **Yes** — 2 tests |
| `mcp_servers/threat_intel_tool_logic.py` | Threat Intel Agent's per-document logic, plus optional injection screening | **Yes** — 5 tests |
| `mcp_servers/*_server.py` | MCP protocol wrappers around the above | **Yes** — run through the MCP Inspector over stdio, including a fail-closed refusal (#5); live data paths confirmed (#9–#11) |
| `agents/orchestrator.py` | Deterministic multi-step dispatch + tracing | **Yes** — 2 tests |
| `guardrails/injection_screening.py` | Prompt injection screening (integration logic + real classifier) | Integration: **yes**, 3 tests. Real LLM classifier: **run for real on 3 hand-written cases** (#4) — a first result, not a measured false-positive rate. Now called from `threat_intel_tool_logic.py` when a classifier is passed (and by default in the Threat Intel MCP server), failing closed |
| `tests/test_agents.py` | 30 tests, all passing | **Yes** |
| `docs/architecture.md` | Full honest verified/unverified breakdown | — |
| `docs/incidents.md` | 14 real findings from building this project (#12–#14 added after the first 11) | — |

## Running the verified parts yourself

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from agents.authorization import SessionContext
from mcp_servers.fusion_tool_logic import query_fusion_data

def mock_source(indicator, family):
    return {'value': family}

session = SessionContext(session_id='demo', held_authorizations={'U', 'S', 'REL_TO_FVEY'})
result = query_fusion_data(session, '10.0.0.1', ['sensor', 'attribution', 'humint'], mock_source)

print('Authorized:', list(result.authorized_data.keys()))
print('Denied:', result.denied_fields)
"
```

Expect `sensor` and `attribution` authorized, `humint` denied — and if
you instrument `mock_source` with a call counter, you'll see it's
never called for `humint` at all.

## What I'd add next

1. **Bind `session_id` to the caller's identity.** In the Fusion and
   Threat Intel servers the session ID is a plain tool argument, so
   anyone who can name a registered session can use its clearance.
2. **Build an evaluation harness for the planner.** It has been run
   once on one alert, before the `query_log_events` →
   `classify_log_text` rename. Run many alerts and record the plans.
3. **Measure the injection screen.** It passed three hand-written
   cases; that is not a false-positive rate. Run it on a labeled set.
4. **Close the loop in the planner.** The planner is plan-and-execute:
   the model never sees results, so it cannot notice a denied result
   or a skipped step. `plan_to_investigation_steps` now reports skipped
   tool names; a loop would need that accounting too.
5. **Re-run the live protocol path** for the Threat Intel and Fusion
   servers after the argument-validation and screening changes, and
   compile `AccumuloReader.java` against the cluster's classpath (the
   change that reads the password from the environment has not been
   compiled in this environment).
