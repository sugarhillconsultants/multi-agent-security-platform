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

This isn't asserted, it's proven: 18 tests, including the property
that actually matters —
`tests/test_agents.py::test_fusion_denied_field_never_reaches_data_source`
confirms a denied request produces **zero calls** to the underlying
data source, not just a discarded result.

## Status: core authorization/orchestration logic fully verified — MCP and LLM layers correct but unexecuted

Every module in `agents/`, `mcp_servers/*_tool_logic.py`, and
`guardrails/`'s integration logic runs with zero external dependencies
— no network, no LLM, no MCP SDK. All 18 tests pass, including a
real bug caught and fixed before ever being presented (see
[`docs/incidents.md`](docs/incidents.md) #1) and a genuine edge case
(a session with zero authorizations, not even the lowest tier, must be
denied) found specifically by writing the test, not planned for in
advance (#2).

The three MCP server wrappers and the real LLM-based injection
classifier are correct code against each system's documented API, but
have **not been executed** — no `mcp` or `anthropic` package, no
network, no API key exist in this project's development environment.
This is a meaningfully larger unverified surface than this portfolio's
other projects had at the equivalent stage, an honest, direct
consequence of choosing the more current, more differentiated
MCP-based design. Full breakdown: [`docs/architecture.md`](docs/architecture.md).

## What's actually in this repo

| Path | What it does | Verified? |
|---|---|---|
| `security/visibility.py` | Accumulo-style visibility parser, reused directly from Project 6 | **Yes** — same proven logic |
| `agents/authorization.py` | Pre-dispatch tool-call authorization, fail-closed | **Yes** — 5 tests |
| `agents/session_registry.py` | Session-to-authorization lookup | **Yes** — 2 tests |
| `mcp_servers/fusion_tool_logic.py` | Fusion Agent's per-field authorization logic | **Yes** — 3 tests |
| `mcp_servers/log_analysis_tool_logic.py` | Log Analysis Agent's logic | **Yes** — 2 tests |
| `mcp_servers/threat_intel_tool_logic.py` | Threat Intel Agent's per-document logic | **Yes** — 1 test |
| `mcp_servers/*_server.py` | MCP protocol wrappers around the above | Correct code, unexecuted |
| `agents/orchestrator.py` | Deterministic multi-step dispatch + tracing | **Yes** — 2 tests |
| `guardrails/injection_screening.py` | Prompt injection screening (integration logic + real classifier) | Integration: **yes**, 3 tests. Real LLM classifier: unexecuted |
| `tests/test_agents.py` | 18 tests, all passing | **Yes** |
| `docs/architecture.md` | Full honest verified/unverified breakdown | — |
| `docs/incidents.md` | 3 real findings from building this project | — |

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

1. **Install `mcp` and `anthropic` somewhere with real network access**
   and actually run each MCP server against a real client — the single
   biggest remaining gap.
2. Wire the three `NotImplementedError` stubs to Projects 1, 5, and 6's
   real deployed endpoints (Project 5 needs per-document visibility
   metadata added to its schema first — a real prerequisite, not just
   wiring).
3. Build the actual agent reasoning layer — an LLM call deciding what
   to investigate, replacing the currently-hardcoded test plans.
4. Confirm the real injection classifier actually makes the
   discussing-vs-attacking distinction its prompt asks for, against
   real adversarial documents, not just the mock used in testing.
