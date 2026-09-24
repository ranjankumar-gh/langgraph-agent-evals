"""Per-case environment specification: the world an eval case starts in."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OrderSpec(BaseModel):
    order_id: str
    customer_id: str
    item: str
    category: str
    price: float
    delivered_on: str | None
    notes: str = ""


class PriorRefundSpec(BaseModel):
    order_id: str
    customer_id: str
    amount: float
    created_on: str


class EnvSpec(BaseModel):
    today: str = "2026-06-15"
    orders: list[OrderSpec] = Field(default_factory=list)
    prior_refunds: list[PriorRefundSpec] = Field(default_factory=list)
    faults: dict[str, Literal["error"]] = Field(default_factory=dict)
    # When set, every lookup_order after the first sees the order at this price: a change
    # (e.g. a partial cancellation) that lands between the first read and the refund.
    reprice_on_reread: float | None = None
