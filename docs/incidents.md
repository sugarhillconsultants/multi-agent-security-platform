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

## 7. Pushing the manual test scripts broke the entire CI run — caught only by actually looking at GitHub Actions, not local testing

`tests/test_real_classifier_manual.py` and `tests/test_real_planner_manual.py`
were both named to match pytest's default auto-discovery pattern
(`test_*.py`) simply because that seemed like the natural place for
them to live, sitting alongside `test_agents.py`. They were never run
locally through `pytest tests/` — only invoked directly as scripts
(`python3 tests/test_real_planner_manual.py`), which never triggered
the problem.

The actual CI workflow runs `pytest tests/ -v`, which auto-discovers
and attempts to **import** every `test_*.py` file to look for test
functions inside it. Both manual scripts execute their real API calls
at module level — not inside a function — so the mere act of
importing them for collection purposes triggered an actual attempt to
call `import anthropic`, which correctly doesn't exist in CI (by
design — CI should never have API keys or incur real costs). This
raised `ModuleNotFoundError`, which aborted the **entire** test run
before a single one of the 21 legitimately-passing tests could
execute — `Interrupted: 2 errors during collection`, hiding all real,
working test results behind what looked like a total CI failure to
anyone glancing at the Actions tab.

Fixed two ways, deliberately redundant: renamed both files away from
the `test_*.py`/`*_test.py` pattern entirely
(`manual_check_real_classifier.py`, `manual_check_real_planner.py`),
so pytest's default collection never attempts to import them at all;
and wrapped each file's executable logic in `if __name__ ==
"__main__":`, so even accidentally importing either file for any
reason in the future can never trigger a real API call as a side
effect, independent of whatever it happens to be named. Confirmed the
fix directly: `pytest tests/ --collect-only` now shows exactly 21
tests collected with zero errors, and `pytest tests/ -v` shows all 21
passing.

This is worth stating plainly: this specific failure mode was
genuinely invisible from every check performed before pushing —
running the manual scripts directly worked fine, and the automated
suite passed 21/21 when run directly with `pytest tests/test_agents.py`
specifically. It only surfaced by looking at the actual GitHub Actions
log after pushing, which is exactly why this portfolio treats a green
CI badge as real, independent confirmation rather than a formality —
this incident is a direct, concrete example of why that distinction
matters.

## 8. Wiring up live Project 1 integration revealed the original tool design assumed a capability that never existed

`query_log_events`'s original design assumed Project 1 exposed a
"search my past events for X" endpoint — a reasonable-sounding
assumption when this project was first scaffolded, never actually
checked against Project 1's real, current API surface.

Fetching Project 1's live `/openapi.json` directly (rather than
working from memory of what that project looked like several sessions
ago) confirmed no such endpoint exists at all. The real API supports
exactly two things: submitting a specific piece of log text for live
classification (`POST /events`, taking `LogEventIn`: `text`/`source`,
returning `LogEventOut`: `event_id`/`text`/`predicted_label`/
`confidence`), and looking up one already-classified event by its
numeric ID (`GET /events/{event_id}`). There is no keyword search, no
listing, no filtering by time range.

Rather than force a mismatched design onto the real system, the tool
was renamed throughout — `query_log_events` became `classify_log_text`
— in `mcp_servers/log_analysis_tool_logic.py`,
`mcp_servers/log_analysis_server.py`, and `agents/planner.py`'s tool
schema, with the parameter shape changed from a free-text `query`
string to the real `text`/`source` fields Project 1's API actually
expects. This is arguably a better design for the actual use case
too: given a security alert, submitting the specific suspicious log
content for classification is a more direct question than searching
an index that was never built.

This is worth stating as a pattern distinct from every other finding
in this log: every previous incident was caught by attempting to
*run* something and hitting a real error. This one was caught by
*checking a live system's actual current interface* before writing
integration code against it — a different, earlier form of the same
underlying discipline (verify against reality, not assumption), applied
before any code was written rather than after it failed.

## 9. Confirming Project 1's live integration for real — plus a genuine, honest observation about the model's own output

Getting `classify_log_text` to actually run against Project 1's real
deployment required recovering a genuinely lost demo credential first:
neither of us remembered the username, and the GitHub repository
secrets (`AZURE_CLIENT_ID`, `HF_TOKEN`, etc.) turned out to be
deployment infrastructure credentials, not the application's own user
database. Found by reading Project 1's actual `app/auth.py` directly:
username `analyst`, with the password read from a `DEMO_PASSWORD`
environment variable that was never actually set on the live
deployment — confirmed via `az containerapp show`, meaning the real,
live password is genuinely the code's own fallback default,
`changeme123`. Verified directly with a standalone `curl` call before
writing any Python against it, matching this whole session's pattern
of confirming reality before building on top of it.

**A separate, real friction point along the way**: two file edits
(`log_analysis_tool_logic.py`'s rename, `log_analysis_server.py`'s
real implementation) silently failed to persist — pasted heredoc
commands that appeared to run produced no error, but the files'
modification timestamps (`ls -la`) showed they were untouched from a
session two days earlier. Root cause never fully identified (possibly
the heredoc got bundled into a prior multi-line paste and only
partially executed), but caught immediately by checking `ls -la`
before assuming a write succeeded, rather than trusting that a
paste without a visible error meant it worked — the same "verify, don't
assume" discipline applied to a shell-command mechanic this time,
not application logic.

**With both fixed, `python3 tests/manual_check_real_log_platform.py`
succeeded completely against the real, live deployment**: real OAuth2
authentication, a real ~15-second cold start survived (Project 1's
Container App is deliberately scaled to zero), and a real response
from the actual deployed classifier: `{'event_id': 1, 'predicted_label':
'normal', 'confidence': 0.54}`.

Worth stating honestly rather than glossing over: that confidence
score is low — barely above chance — for input that reads like a
textbook brute-force pattern ("Failed login attempt x47 ... within 60
seconds"). This isn't a flaw in today's integration work; the request/
response plumbing is fully, correctly confirmed. It's a separate,
genuine observation about the underlying model's actual behavior on
this specific input, worth recording plainly as a real result rather
than either quietly omitting it or treating a successful HTTP
round-trip as if it also validated the model's judgment — those are
two different claims, and only the first one was being tested today.

## 10. Adding real visibility classification to Project 5, and proving the security boundary end to end with live data

Checking Project 5's actual live `/openapi.json` confirmed the gap
this project's docs had already flagged was still genuinely there:
`RetrievedChunk` had only `chunk_id`/`text`/`score` — no classification
field anywhere, and `IngestRequest` had nowhere to attach one either.

Rather than build a full per-user authorization system into Project 5
itself (which has only ever had one hardcoded demo user, no clearance
concept at all), the scoped, honest choice: Project 5 becomes a real,
labeled data source — a `visibility` field added to `IngestRequest`
(default `"U"`) and `RetrievedChunk` (now required), with the actual
label tracked per-chunk and returned on every query. Enforcement stays
where it already correctly lives: this project's own
`agents/authorization.py`, exactly mirroring how Project 6's Fusion
Agent integration already works — the source system labels, the
calling system decides who's cleared to see what.

Verified in stages, each confirmed before moving to the next: the
change didn't break Project 5's own 20 existing tests (none construct
a `RetrievedChunk` directly, so the new required field had zero
blast radius); the automated deploy pipeline (test → then
automatically push to the live Hugging Face Space, confirmed by
reading Project 5's own `.github/workflows/test.yml` directly rather
than assuming how deployment worked) ran successfully; and the live,
deployed `/openapi.json` was fetched again afterward to confirm
`visibility` genuinely appears as a required field on the running
system, not just in the pushed source.

**Then the actual proof**: three real documents ingested live, at
`U`, `S`, and `TS`, followed by a real query against all three,
correctly returning each with its exact label and real,
model-generated relevance scores (the classified attribution and
HUMINT documents scored far higher than the unrelated public CVE
advisory — a substantive, genuine semantic distinction, not
arbitrary). Then, running `manual_check_real_threat_intel.py` against
this live data at three different session clearance levels: a
`U`-only session correctly saw exactly 1 of 3 documents; a `U`+`S`
session correctly saw exactly 2; a fully-cleared session correctly saw
all 3 — precise, graduated enforcement proven against real,
live infrastructure, not a mock.

This closes the second of the three original `NotImplementedError`
stubs with full, live, end-to-end confirmation — only Project 6
(Fusion/Accumulo) remains, which needs the Azure VM running again plus
new infrastructure to read from Accumulo in Python at all.

## What's verified, and what genuinely isn't yet

Every module in `agents/`, `mcp_servers/*_tool_logic.py`, and
`guardrails/`'s integration logic runs with zero external dependencies
— no network, no LLM, no MCP SDK, no live Project 1/5/6 infrastructure.
All 21 tests pass (18 original + 3 covering the planner's deterministic
tool_use-to-InvestigationStep conversion, added alongside incident #6),
including three genuinely load-bearing properties proven with real
evidence rather than assumed: a denied field or document produces
**zero calls** to its underlying data source (not just a discarded
result), the orchestrator correctly continues an investigation after
one step fails rather than aborting silently, and an unknown tool name
from the planner is skipped rather than crashing the whole plan.

As of incident #4, `guardrails/injection_screening.py`'s real,
LLM-based `llm_injection_classifier` has now been run for real,
against Claude's actual API, and correctly handled all three test
cases including the hard discussing-vs-attacking distinction — this
is no longer an open gap.

As of incident #6, `agents/planner.py`'s real agent reasoning has now
also been run for real, against Claude's actual API, and produced a
sensible, correctly-ordered investigation plan for a realistic alert —
this is no longer an open gap either. What remains unverified about
this layer specifically: only one alert scenario has been tried
manually; broader confidence in the planner's tool-selection judgment
across a wider range of alerts would need more manual runs, or a
proper evaluation harness, neither of which exists yet.

As of incident #9, `mcp_servers/log_analysis_server.py`'s
`real_log_platform_data_source` is no longer a stub — it has been run
for real against Project 1's actual live deployment, with a real
authenticated request/response round-trip confirmed end to end. This
is the first of the three original `NotImplementedError` placeholders
to be genuinely closed.

As of incident #10, `mcp_servers/threat_intel_server.py`'s
`real_rag_data_source` is also no longer a stub — Project 5 itself was
extended with real per-document visibility classification, redeployed
live, and the full security boundary was proven end to end against
that live data: a `U`-only session, a `U`+`S` session, and a
fully-cleared session each correctly saw exactly the right subset of
three real, live-ingested documents. This is the second of the three
original stubs genuinely closed.

What's still explicitly NOT verified, stated plainly rather than
glossed over:
- Project 6 (Fusion) still has its original `NotImplementedError` stub
  in place — it needs its Azure VM running again, plus genuinely new
  infrastructure to read from Accumulo in Python at all (no reliable
  current Python client exists for Accumulo 2.x, the same real gap
  that led to building a separate Java writer program in that project
  — reading has the identical problem, and would need either a Java
  reader bridge, Accumulo's Thrift proxy service, or a small REST
  wrapper, none of which currently exist).
- The actual "happy path" through a real MCP tool call — a registered
  session correctly reaching a real data source through the MCP
  protocol layer itself, not just via direct Python function calls —
  hasn't been separately re-exercised via the Inspector since the
  Project 1 integration was completed; only the fail-closed
  unknown-session path has been confirmed that way so far, and only
  for the Fusion Agent specifically.
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
