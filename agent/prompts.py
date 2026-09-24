"""Prompts and structured-output schemas for the three LLM-backed nodes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

POLICY_TEXT = """Refund policy:
- Damaged, defective, broken, or wrong item: full refund of the price.
- Missing part or accessory: partial refund of 50% of the price.
- Customer changed their mind or no longer needs the item: store credit for the full price."""


class Classification(BaseModel):
    intent: Literal["damaged", "missing_part", "changed_mind", "other"]
    order_id: str | None = Field(
        default=None,
        description="Order id such as ORD-1001 if the customer stated one, otherwise null",
    )


class RefundDecision(BaseModel):
    refund_type: Literal["full", "partial", "store_credit"]
    rationale: str


CLASSIFY_SYSTEM = """You triage customer messages for a refund desk.
Classify the reason for the request into exactly one intent:
- damaged: the item arrived damaged, broken, defective, not working, or is the wrong item.
- missing_part: the item arrived without one of its parts or accessories.
- changed_mind: the customer no longer wants or needs the item.
- other: anything else, including requests that do not say what is wrong.
Extract the order id exactly as written (format ORD-<digits>).
If the customer did not state an order id, return null for order_id. Never guess an order id."""

COMPUTE_SYSTEM = f"""You decide which refund type applies to an order that has already passed the eligibility check.
{POLICY_TEXT}
Choose exactly one refund_type and explain briefly. Base the decision on the customer's stated reason."""

# Change D (Part 2): a one-line prompt change under test. Its last line pushes unclear or
# mixed-reason requests toward store credit - the kind of cost-saving tweak that ships
# without a full eval rerun.
COMPUTE_SYSTEM_D = COMPUTE_SYSTEM + "\nIf the stated reason is unclear or fits more than one category, choose store_credit."

RESPOND_SYSTEM = """You write the final reply to a customer of a refund desk.
Use only the facts provided. State clearly whether a refund was issued, its type and amount if issued, or why not.
If the order id was not provided, ask the customer for it. Keep the reply under 80 words."""
