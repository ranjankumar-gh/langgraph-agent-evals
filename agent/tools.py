"""Deterministic refund tools over the per-run SQLite database.

Every call is appended to `Tools.log` *before* it executes, so a failed attempt
still appears in the trajectory.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

EXCLUDED_CATEGORIES = {"gift_card", "perishable"}
REFUND_WINDOW_DAYS = 30
MAX_PRIOR_REFUNDS = 2
HISTORY_WINDOW_DAYS = 90


class ToolError(RuntimeError):
    """A tool call failed (in this repo, always an injected fault)."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    ok: bool
    error: str | None = None


@dataclass
class Tools:
    conn: sqlite3.Connection
    today: date
    faults: dict[str, str] = field(default_factory=dict)
    log: list[ToolCall] = field(default_factory=list)
    _next_refund: int = 1
    reprice_on_reread: float | None = None
    _lookups: int = 0

    def _enter(self, name: str, args: dict[str, Any]) -> None:
        if self.faults.get(name) == "error":
            self.log.append(ToolCall(name, args, ok=False, error="injected fault"))
            raise ToolError(f"{name} failed: upstream service timed out")
        self.log.append(ToolCall(name, args, ok=True))

    def lookup_order(self, order_id: str, customer_id: str) -> dict | None:
        self._enter("lookup_order", {"order_id": order_id})
        self._lookups += 1
        if self._lookups > 1 and self.reprice_on_reread is not None:
            self.conn.execute("UPDATE orders SET price = ? WHERE order_id = ?", (self.reprice_on_reread, order_id))
            self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM orders WHERE order_id = ? AND customer_id = ?", (order_id, customer_id)
        ).fetchone()
        return dict(row) if row else None

    def get_refund_history(self, customer_id: str) -> int:
        self._enter("get_refund_history", {"customer_id": customer_id})
        since = (self.today - timedelta(days=HISTORY_WINDOW_DAYS)).isoformat()
        (count,) = self.conn.execute(
            "SELECT COUNT(*) FROM refunds WHERE customer_id = ? AND created_on >= ?", (customer_id, since)
        ).fetchone()
        return count

    def check_eligibility(self, order: dict, prior_refunds: int) -> dict:
        self._enter("check_eligibility", {"order_id": order["order_id"], "prior_refunds": prior_refunds})
        if order["delivered_on"] is None:
            return {"eligible": False, "reason": "the order has not been delivered yet"}
        if order["category"] in EXCLUDED_CATEGORIES:
            return {"eligible": False, "reason": f"{order['category']} items are not refundable"}
        age = (self.today - date.fromisoformat(order["delivered_on"])).days
        if age > REFUND_WINDOW_DAYS:
            return {"eligible": False, "reason": f"the {REFUND_WINDOW_DAYS}-day refund window has passed"}
        if prior_refunds >= MAX_PRIOR_REFUNDS:
            return {"eligible": False, "reason": "the refund limit for the last 90 days has been reached"}
        return {"eligible": True, "reason": "within policy"}

    def issue_refund(self, order_id: str, customer_id: str, refund_type: str, amount: float) -> str:
        self._enter(
            "issue_refund",
            {"order_id": order_id, "refund_type": refund_type, "amount": amount},
        )
        refund_id = f"RF-{self._next_refund:04d}"
        self._next_refund += 1
        self.conn.execute(
            "INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?)",
            (refund_id, order_id, customer_id, refund_type, amount, self.today.isoformat()),
        )
        self.conn.commit()
        return refund_id
