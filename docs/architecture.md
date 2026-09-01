# Architecture: Design, and the Honest Verified/Unverified Split

## The actual thesis

Most multi-agent demos let any agent call any tool and rely entirely
on the tool itself to enforce access control. This project adds a
second, earlier layer: the orchestrator reasons about whether a
proposed tool call should even be **dispatched**, given the current
investigation session's held authorizations — before the request
reaches the underlying system (Project 6's Accumulo, Project 1's log
API, Project 5's RAG index) at all.

This matters concretely: without this layer, an agent could
legitimately attempt a request for data beyond the session's clearance.
The underlying system would correctly deny the actual data — but the
attempt itself would still happen, still cost a round-trip, and
wouldn't produce a clean, explicit "this was denied and here's why"
audit record on its own. This project's `authorize_tool_call()` (see
`agents/authorization.py`) produces exactly that record, and — proven
by `tests/test_agents.py::test_fusion_denied_field_never_reaches_data_source`
— guarantees the underlying data source is never even called for a
denied request.

## Reusing Project 6's proven logic, not reinventing it

`security/visibility.py` is the same file, verified the same way, as
Project 6 (Secure Data Fusion Platform)'s. Copied here rather than
imported as a cross-repo dependency, since these are two independently
deployable projects — but deliberately the identical implementation,
not a reimplementation that could silently drift from the original's
already-proven correctness (including matching Accumulo's real
ambiguity rule for mixed `&`/`|` expressions without parentheses).

## Why MCP, and what that choice costs

The reference category this project targets explicitly asks for
"orchestrated agents with tool use" — MCP is the current, real
standard for exactly that, and wrapping Projects 1/5/6's existing APIs
as proper MCP servers is more differentiated than hand-rolling a
custom tool-calling scheme. The Fusion Agent's MCP server specifically
calls `authorize_tool_call()` from inside its own tool handler, before
any Accumulo access — meaning the pre-dispatch authorization is
enforced at the actual MCP tool boundary, not just in application code
sitting in front of it.

**The honest cost**: no `mcp` SDK exists in this project's development
environment, and no network to install it. Every `mcp_servers/*_server.py`
file is correct code against the SDK's documented `FastMCP` API, but
has never actually been run. This is a materially bigger unverified
surface than this portfolio's other projects had at the equivalent
stage — see `docs/incidents.md` for the full, itemized account of
what's verified versus deferred.

## The verified/unverified split, in one table

| Component | Verified? |
|---|---|
| `security/visibility.py` | **Yes** — same logic already proven in Project 6 |
| `agents/authorization.py` (pre-dispatch authorization) | **Yes** — 5 tests, including fail-closed behavior on malformed expressions |
| `agents/session_registry.py` | **Yes** — 2 tests, including fail-closed on unknown sessions |
| `mcp_servers/fusion_tool_logic.py` | **Yes** — 3 tests, including the critical "denied field never reaches the data source" property |
| `mcp_servers/log_analysis_tool_logic.py` | **Yes** — 2 tests, including the zero-authorizations edge case |
| `mcp_servers/threat_intel_tool_logic.py` | **Yes** — 1 test, per-document authorization |
| `agents/orchestrator.py` (dispatch mechanics) | **Yes** — 2 tests, including "one failed step doesn't abort the investigation" |
| `guardrails/injection_screening.py` (integration logic) | **Yes** — 3 tests, including discussing-vs-being-an-attack |
| `mcp_servers/*_server.py` (MCP protocol wrapper) | Correct code against documented API — **not executed**, no `mcp` package/network here |
| `guardrails/injection_screening.py`'s `llm_injection_classifier` | Correct code against documented Anthropic API — **not executed**, no `anthropic` package/API key/network here |
| Real integration with Projects 1/5/6's live endpoints | **Not implemented** — explicit `NotImplementedError` stubs naming exactly what to wire up |
| Actual agent reasoning (deciding what to investigate) | **Not built at all** — the orchestrator currently runs a pre-defined plan, doesn't generate one |

## What it would take to close the remaining gaps

1. Install `mcp` and `anthropic` somewhere with real network access,
   and actually run each MCP server, connecting a real MCP client to
   confirm the tool-call round-trip works as documented.
2. Wire the three `NotImplementedError` stubs to Projects 1, 5, and 6's
   real deployed endpoints. Note: Project 5's current RAG schema
   doesn't yet attach per-document visibility labels to retrieved
   chunks — that's a real, honest prerequisite to add there first,
   not just a wiring exercise on this project's side.
3. Confirm `llm_injection_classifier` actually makes the
   discussing-vs-attacking distinction correctly against real
   adversarial test documents, not just the mock used in this
   project's own test suite.
4. Build the actual agent reasoning layer — an LLM call that, given an
   initial alert, decides which tools to invoke and in what order,
   replacing the currently-hardcoded `InvestigationStep` lists used in
   testing with a real, dynamically-generated plan.
5. Add real tracing/observability export (e.g. OpenTelemetry) on top
   of `InvestigationTrace`'s existing structured summary, so this
   project's audit trail integrates with real monitoring
   infrastructure rather than just being returned as a Python object.
