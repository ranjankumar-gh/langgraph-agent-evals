"""Layer 1: what actually changed in the system of record."""
from __future__ import annotations

import sqlite3

from evals.checks import CheckResult
from evals.schema import EndState


def observed_refunds(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT refund_id, order_id, refund_type, amount FROM refunds WHERE refund_id LIKE 'RF-%' ORDER BY refund_id"
    ).fetchall()
    return [dict(r) for r in rows]


def _matches(observed: list[dict], expected: EndState) -> bool:
    if len(observed) != expected.refund_count:
        return False
    if expected.refund_count == 0:
        return True
    refund = observed[0]
    if expected.refund_type is not None and refund["refund_type"] != expected.refund_type:
        return False
    if expected.amount is not None and abs(refund["amount"] - expected.amount) > 0.005:
        return False
    return True


def check_end_state(conn: sqlite3.Connection, acceptable: list[EndState]) -> CheckResult:
    observed = observed_refunds(conn)
    for expected in acceptable:
        if _matches(observed, expected):
            return CheckResult(True, f"matched {expected.model_dump()}")
    shown = [(r["refund_type"], r["amount"]) for r in observed]
    return CheckResult(False, f"observed refunds {shown}; acceptable {[e.model_dump() for e in acceptable]}")
