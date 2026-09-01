"""
security/visibility.py

Reused directly from Project 6 (Secure Data Fusion Platform)'s
already-verified visibility.py — same file, same tests passing there
(9/9), copied here rather than imported as a cross-repo dependency
since these are two independently deployable projects. See that
project's docs/incidents.md for the full history of how this was
built and verified, including matching Accumulo's real ambiguity rule
(mixed & and | without parentheses must be rejected, not silently
resolved via precedence).

Implements Accumulo's ColumnVisibility authorization model: each cell
carries a boolean expression over classification/compartment labels
(e.g. "S&REL_TO_FVEY", "TS&SI&NOFORN", "U"), and a user's access is
granted only if their set of held authorizations satisfies that
expression.

In THIS project, the same logic is repurposed one layer up the stack:
instead of asking "can this user see this cell," we ask "should the
orchestrator even DISPATCH a tool call requesting data at this
classification level, given the current session's held
authorizations" — enforcing the same boundary BEFORE a request is
made, not just relying on Project 6's Accumulo layer to filter results
after the fact. See agents/authorization.py.
"""

import re
from dataclasses import dataclass


class VisibilityParseError(ValueError):
    pass


@dataclass
class Node:
    op: str  # 'LABEL', 'AND', or 'OR'
    label: str | None = None
    children: list["Node"] | None = None


_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def _tokenize(expr: str) -> list[str]:
    tokens = []
    current_label = ""
    for ch in expr:
        if ch in "&|()":
            if current_label:
                tokens.append(current_label)
                current_label = ""
            tokens.append(ch)
        elif ch.isspace():
            if current_label:
                tokens.append(current_label)
                current_label = ""
        else:
            current_label += ch
    if current_label:
        tokens.append(current_label)
    return tokens


def parse_visibility(expr: str) -> Node:
    expr = expr.strip()
    if not expr:
        raise VisibilityParseError("Empty visibility expression")

    tokens = _tokenize(expr)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume():
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def parse_term() -> Node:
        tok = peek()
        if tok is None:
            raise VisibilityParseError("Unexpected end of expression")
        if tok == "(":
            consume()
            node = parse_expression()
            if peek() != ")":
                raise VisibilityParseError(f"Expected ')' in: {expr}")
            consume()
            return node
        if tok in ("&", "|", ")"):
            raise VisibilityParseError(f"Unexpected token '{tok}' in: {expr}")
        if not _LABEL_PATTERN.match(tok):
            raise VisibilityParseError(f"Invalid label '{tok}' in: {expr}")
        consume()
        return Node(op="LABEL", label=tok)

    def parse_expression() -> Node:
        left = parse_term()
        op_seen = None
        children = [left]

        while peek() in ("&", "|"):
            op_tok = consume()
            op = "AND" if op_tok == "&" else "OR"
            if op_seen is not None and op != op_seen:
                raise VisibilityParseError(
                    f"Mixed '&' and '|' without parentheses in: {expr} "
                    f"(Accumulo requires explicit grouping, e.g. '(A&B)|C')"
                )
            op_seen = op
            children.append(parse_term())

        if len(children) == 1:
            return children[0]
        return Node(op=op_seen, children=children)

    result = parse_expression()
    if pos[0] != len(tokens):
        raise VisibilityParseError(f"Unexpected trailing tokens in: {expr}")
    return result


def evaluate_visibility(expr: str, user_authorizations: set[str]) -> bool:
    tree = parse_visibility(expr)

    def eval_node(node: Node) -> bool:
        if node.op == "LABEL":
            return node.label in user_authorizations
        elif node.op == "AND":
            return all(eval_node(child) for child in node.children)
        elif node.op == "OR":
            return any(eval_node(child) for child in node.children)
        raise VisibilityParseError(f"Unknown node op: {node.op}")

    return eval_node(tree)
