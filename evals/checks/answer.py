"""Layer 3: what the agent said. A string check plus a single-pass LLM judge."""
from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from agent.llm import LLM
from evals.checks import CheckResult
from evals.schema import AnswerSpec, Case

JUDGE_PASS = 4

JUDGE_SYSTEM = """You grade the final reply of a customer-service refund agent.
You are given the customer's request, a reference description of the correct outcome, and the agent's reply.
Score 1-5 for whether the reply communicates the correct outcome:
5 = fully consistent with the reference; 4 = consistent with minor omissions; 3 = partly consistent;
2 = mostly inconsistent; 1 = contradicts the reference or is missing.
Return JSON with an integer score and a one-sentence rationale."""


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5)
    rationale: str


@dataclass(frozen=True)
class AnswerResult:
    string_pass: bool
    judge_score: int
    judge_rationale: str
    passed: bool


def mentions_amount(text: str, amount: float) -> bool:
    normalized = text.replace(",", "")
    candidates = {f"{amount:.2f}"}
    if amount == int(amount):
        candidates.add(str(int(amount)))
    return any(re.search(rf"(?<![\d.]){re.escape(c)}(?!\d)", normalized) for c in candidates)


def string_check(text: str, spec: AnswerSpec) -> CheckResult:
    problems: list[str] = []
    if spec.mention_amount is not None and not mentions_amount(text, spec.mention_amount):
        problems.append(f"amount {spec.mention_amount:.2f} not mentioned")
    for phrase in spec.must_not_mention:
        if phrase in text:
            problems.append(f"mentions forbidden {phrase!r}")
    return CheckResult(not problems, "; ".join(problems) or "ok")


def answer_check(judge: LLM, case: Case, final: str, *, seed: int) -> AnswerResult:
    strings = string_check(final, case.answer)
    if not final.strip():
        return AnswerResult(strings.passed, 1, "no final message", False)
    user = (
        f"Customer request:\n{case.request}\n\n"
        f"Reference outcome:\n{case.answer.reference}\n\n"
        f"Agent reply:\n{final}"
    )
    verdict = judge.structured(JUDGE_SYSTEM, user, JudgeVerdict, seed=seed)
    return AnswerResult(strings.passed, verdict.score, verdict.rationale, strings.passed and verdict.score >= JUDGE_PASS)
