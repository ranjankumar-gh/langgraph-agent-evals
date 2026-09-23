"""Graph state for the refund agent. Kept fixed across all three parts of the series."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class RefundState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    customer_id: str
    intent: str
    order_id: str | None
    order: dict[str, Any] | None
    prior_refunds: int
    eligibility: dict[str, Any]
    refund_type: str
    refund_amount: float
    approval: str
    refund_id: str
    error: str
