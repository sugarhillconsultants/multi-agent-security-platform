"""
agents/orchestrator.py

The orchestrator's coordination logic — deliberately split into two
halves with very different verification status:

  1. THIS FILE: the deterministic mechanics of running an
     investigation plan — given a list of steps (which agent, what
     parameters), dispatch each one in order, collect results, and
     build a complete trace. Fully testable with mock agent tools,
     zero LLM dependency.

  2. NOT in this file: the actual reasoning about what to investigate
     given an initial alert — "given this log event, what threat
     intel should I look up, and does the fusion data support
     escalation" — which requires a real LLM call and is deferred to
     real deployment, the same way Project 5's embedding model and
     this project's own injection classifier are. See
     docs/architecture.md.

This split matters: a multi-agent system's RELIABILITY substantially
depends on this coordination layer behaving correctly and
predictably — retrying, handling a denied tool call gracefully,
producing a complete audit trace — independent of whatever the LLM
decides to investigate. Testing this layer thoroughly, without needing
a real model at all, is exactly the kind of verified foundation this
whole portfolio has been built around.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from agents.authorization import SessionContext


@dataclass
class InvestigationStep:
    """Names which tool to call and with what arguments — analogous
    to what an LLM-based planner would produce as its output, but here
    just plain data, so the dispatch mechanics can be tested without
    needing a model to generate the plan at all."""
    agent_name: str
    tool_fn: Callable  # one of the query_* functions from mcp_servers/*_tool_logic.py
    kwargs: dict = field(default_factory=dict)


@dataclass
class StepResult:
    step: InvestigationStep
    result: object
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class InvestigationTrace:
    session_id: str
    steps_completed: list = field(default_factory=list)  # list[StepResult]

    def summary(self) -> dict:
        """A structured summary suitable for the tracing/observability
        requirement — every step, whether it succeeded, and why, in
        one place."""
        return {
            "session_id": self.session_id,
            "total_steps": len(self.steps_completed),
            "steps": [
                {
                    "agent": sr.step.agent_name,
                    "succeeded": sr.error is None,
                    "error": sr.error,
                    "timestamp": sr.timestamp,
                }
                for sr in self.steps_completed
            ],
        }


def run_investigation(session: SessionContext, steps: list[InvestigationStep]) -> InvestigationTrace:
    """Runs each step in order, continuing even if one step fails —
    a single denied tool call or an unexpected exception should not
    silently abort the entire investigation, since a partial result
    (with a clear record of what failed and why) is far more useful to
    an analyst than nothing at all. This is a deliberate reliability
    property of the orchestrator, independent of any LLM reasoning."""
    trace = InvestigationTrace(session_id=session.session_id)

    for step in steps:
        try:
            result = step.tool_fn(session=session, **step.kwargs)
            trace.steps_completed.append(StepResult(step=step, result=result))
        except Exception as e:
            trace.steps_completed.append(StepResult(step=step, result=None, error=str(e)))

    return trace
