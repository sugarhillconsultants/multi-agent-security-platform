# Real Findings From Building This Project

Same rationale as every other project in this portfolio: an honest
account of what was actually discovered while writing and testing this
code, not a cleaned-up version of events.

## 1. A real bug caught before it was ever presented — a naming collision that would have broken every MCP server

The first draft of `fusion_server.py` did this:

```python
from mcp_servers.fusion_tool_logic import query_fusion_data

@mcp_server.tool()
def query_fusion_data(indicator, requested_families, session_id):
    ...
```

Importing a function and then declaring a new function with the exact
same name silently shadows the import — the MCP tool wrapper would
have either called itself recursively or simply never reached the
real, already-verified logic in `fusion_tool_logic.py` at all,
depending on Python's exact name resolution at that point. Caught by
re-reading the file before presenting it, the same discipline this
whole portfolio has used since Project 1's `id`/`event_id` bug. Fixed
by aliasing the import (`as _query_fusion_data_logic`) in all three
MCP server files, so the tool-facing name and the underlying logic
function's name never collide.

## 2. A genuine edge case found only by writing the test, not planned for in advance

While testing `log_analysis_tool_logic.py`, the natural first test was
"a session holding `U` can query U-level log events." Writing a second
test — "what about a session holding *no* authorizations at all,
not even `U`?" — wasn't originally planned; it came from wanting the
suite to cover the boundary, not just the expected case.

The result mattered: a session with `held_authorizations=set()` is
correctly **denied**, exactly like Project 6's own visibility model
requires — `evaluate_visibility("U", set())` correctly returns `False`,
since holding zero authorizations doesn't satisfy even the least
restrictive label. This confirms "no clearance" genuinely means "no
access" system-wide, not an implicit default-permit for the
lowest-classification tier. A system that got this wrong would look
correct in every "obvious" test case and only fail in the one
scenario nobody thought to check — exactly the kind of gap a real
security review exists to catch.

## 3. Designing the injection screening tests surfaced a real, substantive distinction the actual classifier needs to get right

Writing `test_injection_screening_distinguishes_discussing_vs_being_an_attack`
forced a concrete design question: a threat-intel document that
*describes* prompt injection techniques (legitimate, valuable content
for a security analyst) is not the same thing as a document that
*is* an injection attempt. A naive keyword-matching classifier (or an
insufficiently-prompted LLM classifier) could easily conflate these —
flagging every mention of the word "ignore" regardless of context,
which would make the guardrail actively harmful (suppressing
legitimate threat intelligence) rather than merely imperfect.

This distinction is now explicit in `llm_injection_classifier`'s
actual prompt (see `guardrails/injection_screening.py`), not left
implicit — but it's worth stating plainly that **this specific
behavior has not been verified against the real classifier**, only
against a mock built to encode the same distinction. Confirming the
real LLM-based classifier actually makes this distinction correctly
is real, necessary work for whoever deploys this, not something to
assume works just because the prompt asks for it clearly.

## 4. Running the real classifier for the first time: a genuine API requirement neither of us anticipated, then a clean, confirmed pass

The very first real call to `llm_injection_classifier` — genuinely
the first execution of this function anywhere, against Claude's actual
API rather than a mock — failed immediately with:

```
anthropic.BadRequestError: Error code: 400 - {'type': 'error',
'error': {'type': 'invalid_request_error', 'message':
'anthropic-workspace-id is required when authenticating with an
identity-linked API key; send the id of the workspace this request
acts in.'}}
```

Identity-linked API keys (the current default when creating a key via
the Claude Console) require an explicit `anthropic-workspace-id`
header naming which workspace the request acts in — not documented
anywhere in this project's original code, since neither of us had
occasion to hit this specific requirement until actually attempting
the real call. Fixed by reading the workspace ID from a new
`ANTHROPIC_WORKSPACE_ID` environment variable and passing it via
`extra_headers` on the `messages.create()` call.

**With that fixed, the real classifier passed all three test cases
correctly on the very first genuine attempt** — including the hard
one (#3 above): a threat report describing prompt injection technique,
*without itself containing an injection attempt*, was correctly
classified as safe, while an actual injection attempt was correctly
flagged with a specific, accurate reason. The distinction this
project's test suite could only assert against a mock is now
confirmed against the real model.

## What's verified, and what genuinely isn't yet

Every module in `agents/`, `mcp_servers/*_tool_logic.py`, and
`guardrails/`'s integration logic runs with zero external dependencies
— no network, no LLM, no MCP SDK, no live Project 1/5/6 infrastructure.
All 18 tests pass, including two genuinely load-bearing properties
proven with real evidence rather than assumed: a denied field or
document produces **zero calls** to its underlying data source (not
just a discarded result), and the orchestrator correctly continues an
investigation after one step fails rather than aborting silently.

As of incident #4, `guardrails/injection_screening.py`'s real,
LLM-based `llm_injection_classifier` has now been run for real,
against Claude's actual API, and correctly handled all three test
cases including the hard discussing-vs-attacking distinction — this
is no longer an open gap.

What's still explicitly NOT verified, stated plainly rather than
glossed over:
- The three `mcp_servers/*_server.py` MCP wrapper files — correct code
  against the documented `mcp` SDK API, never executed (no `mcp`
  package/network access confirmed against a real MCP client yet).
- The actual agent *reasoning* (deciding what to investigate given an
  initial alert) — not built at all yet; `agents/orchestrator.py`
  only handles the deterministic mechanics of running a pre-defined
  plan, not generating one.
- Live integration with Projects 1, 5, and 6's real deployed
  endpoints — every `real_*_data_source` function in `mcp_servers/`
  is an explicit `NotImplementedError` stub pointing at exactly what
  needs wiring up.

This is still a meaningfully larger unverified surface than this
portfolio's earlier projects at the equivalent stage — but the single
most novel, highest-risk piece (does the real LLM classifier actually
make the distinction its prompt claims to enforce) is now confirmed,
not assumed. See docs/architecture.md for the full, itemized breakdown
and what it would take to close the remaining gaps.
