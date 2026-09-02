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

## 5. Attempting to run the MCP servers for the first time: the SDK had undergone a major, undocumented-to-us breaking change

Running `mcp dev mcp_servers/fusion_server.py` for the first time
failed immediately with `ModuleNotFoundError: No module named
'mcp.server.fastmcp'`, along with an unusually specific and helpful
message pointing directly at the SDK's own migration guide. The `mcp`
package had undergone a major version bump (v1 to v2) at some point
between when this code was originally written and when it was first
actually run — `FastMCP` was renamed to `MCPServer`, among many other
changes covered in the SDK's migration documentation.

Rather than pin back to the deprecated v1 line (`mcp<2`) to make the
original code work as-is, the three server files were updated to the
real, current v2 API — consistent with this project's whole reason for
choosing MCP in the first place (a current, differentiated design, not
a demonstration of a now-legacy API). Reading the migration guide
directly rather than guessing revealed the actual fix needed for these
specific files was narrow: the guide's own "What is unchanged on
`MCPServer`" section confirms `@mcp.tool()` decorators and `.run()`
keep their v1 behavior for a simple server like these — none of the
three files here use resources, prompts, elicitation, or custom
transport configuration, which is where most of v2's other breaking
changes actually apply. The fix was exactly two lines per file: the
import path (`mcp.server.fastmcp` → `mcp.server.mcpserver`) and the
class name (`FastMCP` → `MCPServer`).

This is worth stating plainly as a category of risk distinct from
everything else in this incident log: every other unverified-until-run
piece in this portfolio was unverified because of environment
limitations (no network, no compiler, no GPU). This one was unverified
because the *target it was written against had changed out from under
it* while sitting unexecuted — a real reminder that "correct code
against a documented API" has a shelf life, and needs to be confirmed
against current reality, not just assumed to remain valid indefinitely.

**Two more real, narrow issues surfaced getting the Fusion Agent's
server to actually run, both fixed and then confirmed working:**

- `mcp dev` loads the server file via `importlib.util.module_from_spec()`/
  `exec_module()` directly on the file path — this does NOT
  automatically add the project root to `sys.path` the way a normal
  `python3 script.py` invocation would, so `from agents.session_registry
  import ...` failed with `ModuleNotFoundError: No module named
  'agents'`. Fixed by having each server file explicitly insert its own
  parent directory onto `sys.path` before those imports.
- `mcp dev` looks for a server object named `mcp`, `server`, or `app`
  by default; this project's servers all use `mcp_server`. Fixed by
  invoking with the explicit `file:object` syntax the tool itself
  suggested (`mcp dev mcp_servers/fusion_server.py:mcp_server`).

**With all of the above fixed, all three MCP servers were successfully
run for real, end to end, for the first time**: the MCP Inspector
connected over stdio to each one in turn (`fusion-agent`,
`log-analysis-agent`, `threat-intel-agent`), correctly reporting each
server's identity and capabilities. For the Fusion Agent specifically,
a tool call to `query_fusion_data` was confirmed routed all the way
through the real MCP protocol layer into the actual, already-tested
application code — where `agents/session_registry.py`'s fail-closed
behavior for an unrecognized session correctly fired, raising exactly
the `KeyError` already proven in
`tests/test_agents.py::test_session_registry_unknown_session_fails_closed`,
this time via a genuine MCP client round-trip rather than a direct
Python function call. This is real, complete confirmation that the
MCP protocol layer, the import/path setup, and the underlying security
logic all genuinely work together, across all three servers — not
verified separately and assumed to compose correctly.

## 6. The actual agent reasoning layer, run for real for the first time — and it behaved exactly as intended

`agents/planner.py` implements the one piece explicitly deferred at
the end of every prior session: given a raw alert, ask Claude to
decide which tools to call, using Claude's native tool-use mechanism
rather than free-text JSON parsing. This can't be covered by the
automated test suite — Claude's exact tool-selection decisions for a
given prompt aren't guaranteed identical run to run — so it was
verified manually instead, the same way the injection classifier was.

Given the alert *"Unusual outbound connection volume detected from
internal host 10.0.0.42 to external IP 185.220.101.47 over the past
hour, flagged by the log anomaly classifier with high confidence,"*
Claude correctly chose to call `query_log_events` (pulling log context
first, with a well-constructed search query extracting the specific
host, IP, and timeframe from the alert text) and `query_threat_intel`
(checking the external IP against known threat activity) — and,
notably, did **not** jump straight to `query_fusion_data`, the one
tool gated by classification-level authorization. This matches the
prompt's explicit instruction to start broad before querying fusion
data for a specific indicator — real evidence the prompt's guidance
actually shaped the model's behavior, not a lucky coincidence.

A deliberate security boundary in this design, worth stating
explicitly: `plan_to_investigation_steps()`'s `extra_kwargs_by_tool`
parameter exists specifically so the calling code — never Claude —
injects which session's authorizations a tool call runs under. Claude
decides WHAT to investigate; it is never in a position to specify
WHICH clearance level the investigation runs under.

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
- The actual "happy path" through a real MCP tool call — a registered
  session correctly reaching one of the `real_*_data_source` functions'
  intentional `NotImplementedError` stubs — hasn't been separately
  exercised via the Inspector; only the fail-closed unknown-session
  path has been confirmed end to end, and only for the Fusion Agent
  specifically (though there's no structural reason to expect the
  other two would behave differently, given they share the identical
  authorization-check pattern).
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
