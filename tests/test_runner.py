from evals.checks.answer import JudgeVerdict
from evals.runner import run_case
from evals.schema import Case
from agent.prompts import Classification, RefundDecision
from tests.fakes import FakeLLM

CASE = Case.model_validate({
    "id": "T01", "slice": "happy", "risk": "low", "difficulty": "easy", "customer_id": "C-01",
    "request": "Order ORD-1001: the headphones arrived broken.",
    "env": {"orders": [{"order_id": "ORD-1001", "customer_id": "C-01", "item": "headphones",
                        "category": "electronics", "price": 149.0, "delivered_on": "2026-06-10"}]},
    "end_states": [{"refund_count": 1, "refund_type": "full", "amount": 149.0}],
    "constraints": {"required": ["lookup_order", "check_eligibility", "issue_refund"],
                    "ordering": [["lookup_order", "check_eligibility"], ["check_eligibility", "issue_refund"]],
                    "max_calls": {"lookup_order": 2, "issue_refund": 1}},
    "reference_trajectory": ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"],
    "answer": {"reference": "Confirms a full refund of 149.00", "mention_amount": 149.0},
})


def llms(reply="Your full refund of 149.00 has been issued."):
    agent = FakeLLM(classification=Classification(intent="damaged", order_id="ORD-1001"),
                    decision=RefundDecision(refund_type="full", rationale="broken"), reply=reply)
    judge = FakeLLM(verdict=JudgeVerdict(score=5, rationale="matches"))
    return agent, judge


def test_baseline_passes_every_layer():
    rec = run_case(CASE, "baseline", 0, *llms())
    assert (rec.end_state_pass, rec.constraints_pass, rec.answer_pass) == (True, True, True)
    assert rec.mode_pass == {"strict": True, "unordered": True, "subset": True, "superset": True}
    assert rec.crashed is None and rec.mutations_fired == []


def test_mutant_a_is_trajectory_blind():
    rec = run_case(CASE, "A", 0, *llms())
    assert rec.answer_pass and rec.end_state_pass
    assert not rec.constraints_pass
    assert rec.mutations_fired == ["A:skipped_eligibility"]


def test_crash_is_recorded_not_raised():
    agent, judge = llms()
    agent.responses = []  # structured() now raises AssertionError inside the graph
    rec = run_case(CASE, "baseline", 0, agent, judge)
    assert rec.crashed.startswith("AssertionError")
    assert not rec.answer_pass


def test_judge_failure_is_a_grading_error_not_a_crash():
    agent, judge = llms()
    judge.responses = []  # structured() raises AssertionError in answer_check
    rec = run_case(CASE, "baseline", 0, agent, judge)
    assert rec.crashed is None
    assert rec.grading_error.startswith("AssertionError")
    assert rec.answer_pass is False
