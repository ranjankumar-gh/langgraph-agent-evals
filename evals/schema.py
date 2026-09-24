"""The eval case: initial world, acceptable end states, trajectory constraints, answer spec."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from env.fixtures import EnvSpec

SLICES = (
    "happy", "ineligible", "ambiguous", "missing_data", "tool_failure", "approval_rejected", "injection",
)


class EndState(BaseModel):
    refund_count: int
    refund_type: str | None = None
    amount: float | None = None


class TrajectoryConstraints(BaseModel):
    required: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    ordering: list[tuple[str, str]] = Field(default_factory=list)
    max_calls: dict[str, int] = Field(default_factory=dict)


class AnswerSpec(BaseModel):
    reference: str
    mention_amount: float | None = None
    must_not_mention: list[str] = Field(default_factory=list)


class Oracle(BaseModel):
    """Expected model outputs. Used only by the offline self-test in tests/test_cases.py;
    never shown to the agent or to any grader."""

    intent: str
    order_id: str | None
    refund_type: str | None = None


class Case(BaseModel):
    id: str
    slice: Literal["happy", "ineligible", "ambiguous", "missing_data", "tool_failure", "approval_rejected", "injection", "changed_order"]  # type: ignore[valid-type]
    risk: Literal["low", "medium", "high"]
    difficulty: Literal["easy", "hard"]
    tags: list[str] = Field(default_factory=list)
    customer_id: str
    request: str
    env: EnvSpec
    approval: Literal["approve", "reject"] | None = None
    end_states: list[EndState]
    constraints: TrajectoryConstraints
    reference_trajectory: list[str]
    answer: AnswerSpec
    oracle: Oracle | None = None


def load_cases(directory: Path) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(directory.glob("*.yaml")):
        cases.extend(Case.model_validate(item) for item in yaml.safe_load(path.read_text(encoding="utf-8")))
    ids = [c.id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids: {sorted(duplicates)}")
    return cases
