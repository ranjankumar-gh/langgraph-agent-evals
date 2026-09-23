from collections import Counter
from pathlib import Path

import pytest

from agent.prompts import Classification, RefundDecision
from evals.cases.build_cases import build
from evals.checks.answer import JudgeVerdict
from evals.runner import run_case
from evals.schema import load_cases
from tests.fakes import FakeLLM

CASES = load_cases(Path("evals/cases"))


def oracle_llms(case):
    o = case.oracle
    agent = FakeLLM(
        classification=Classification(intent=o.intent, order_id=o.order_id),
        decision=RefundDecision(refund_type=o.refund_type or "full", rationale="oracle"),
        reply=case.answer.reference,
    )
    return agent, FakeLLM(verdict=JudgeVerdict(score=5, rationale="oracle"))


def test_committed_yaml_matches_builder():
    built = {c.id: c.model_dump() for cases in build().values() for c in cases}
    committed = {c.id: c.model_dump() for c in CASES}
    assert committed == built


def test_case_set_shape():
    assert len(CASES) == 52
    assert Counter(c.slice for c in CASES) == {
        "happy": 10, "ineligible": 8, "ambiguous": 6, "missing_data": 6,
        "tool_failure": 8, "approval_rejected": 6, "injection": 8,
    }
    assert sum(any(t.startswith("tbp_target") for t in c.tags) for c in CASES) >= 8
    assert all(c.oracle is not None for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_baseline_with_oracle_outputs_passes_every_layer(case):
    rec = run_case(case, "baseline", 0, *oracle_llms(case))
    assert rec.crashed is None, rec.crashed
    assert rec.end_state_pass, rec.end_state_detail
    assert rec.constraints_pass, rec.constraints_detail
    assert rec.string_pass, rec.final_message


@pytest.mark.parametrize("variant", ["alt_history_early", "alt_recheck"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_valid_alternates_reach_the_same_end_state(case, variant):
    rec = run_case(case, variant, 0, *oracle_llms(case))
    assert rec.end_state_pass, rec.end_state_detail


def test_mutants_have_teeth():
    by_id = {c.id: c for c in CASES}
    a = run_case(by_id["I01"], "A", 0, *oracle_llms(by_id["I01"]))
    assert not a.end_state_pass  # refunds an out-of-window damaged item
    c = run_case(by_id["H01"], "C", 0, *oracle_llms(by_id["H01"]))
    assert not c.constraints_pass and c.end_state_pass
    b = run_case(by_id["F01"], "B", 0, *oracle_llms(by_id["F01"]))
    assert b.mutations_fired == ["B:false_success"]
