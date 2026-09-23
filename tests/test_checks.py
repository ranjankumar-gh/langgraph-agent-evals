import sqlite3

import pytest

from env.db import create_db
from env.fixtures import EnvSpec
from evals.checks.answer import JudgeVerdict, answer_check, mentions_amount, string_check
from evals.checks.end_state import check_end_state
from evals.checks.trajectory import check_constraints, match_trajectory
from evals.schema import AnswerSpec, Case, EndState, TrajectoryConstraints
from tests.fakes import FakeLLM


def db_with_refund(refund_type="full", amount=120.0) -> sqlite3.Connection:
    conn = create_db(EnvSpec())
    conn.execute("INSERT INTO refunds VALUES ('RF-0001', 'ORD-1', 'C-01', ?, ?, '2026-06-15')", (refund_type, amount))
    conn.execute("INSERT INTO refunds VALUES ('PRIOR-00', 'ORD-0', 'C-01', 'full', 20, '2026-06-01')")
    return conn


def test_end_state_accepts_any_listed_state():
    conn = db_with_refund("full", 120.0)
    acceptable = [EndState(refund_count=1, refund_type="store_credit", amount=120.0),
                  EndState(refund_count=1, refund_type="full", amount=120.0)]
    assert check_end_state(conn, acceptable).passed
    assert not check_end_state(conn, [EndState(refund_count=0)]).passed


def test_end_state_ignores_seeded_prior_refunds():
    conn = create_db(EnvSpec())
    conn.execute("INSERT INTO refunds VALUES ('PRIOR-00', 'ORD-0', 'C-01', 'full', 20, '2026-06-01')")
    assert check_end_state(conn, [EndState(refund_count=0)]).passed


def test_end_state_amount_mismatch_fails():
    conn = db_with_refund("full", 119.0)
    result = check_end_state(conn, [EndState(refund_count=1, refund_type="full", amount=120.0)])
    assert not result.passed
    assert "119.0" in result.detail


CONSTRAINTS = TrajectoryConstraints(
    required=["lookup_order", "check_eligibility", "issue_refund"],
    forbidden=[],
    ordering=[("lookup_order", "check_eligibility"), ("check_eligibility", "issue_refund")],
    max_calls={"lookup_order": 2, "issue_refund": 1},
)


def test_constraints_pass_on_reference_path():
    calls = ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]
    assert check_constraints(calls, CONSTRAINTS).passed


def test_constraints_flag_missing_check_and_after_without_before():
    result = check_constraints(["lookup_order", "issue_refund"], CONSTRAINTS)
    assert not result.passed
    assert "missing required check_eligibility" in result.detail
    assert "issue_refund called without check_eligibility" in result.detail


def test_constraints_flag_order_and_max_calls():
    calls = ["check_eligibility", "lookup_order", "lookup_order", "lookup_order", "issue_refund"]
    result = check_constraints(calls, CONSTRAINTS)
    assert "check_eligibility before lookup_order" in result.detail
    assert "lookup_order called 3 times (max 2)" in result.detail


def test_constraints_flag_forbidden():
    c = TrajectoryConstraints(forbidden=["issue_refund"])
    assert "forbidden issue_refund called" in check_constraints(["issue_refund"], c).detail


REF = ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]


@pytest.mark.parametrize(
    ("observed", "strict", "unordered", "subset", "superset"),
    [
        (REF, True, True, True, True),
        (["get_refund_history", "lookup_order", "check_eligibility", "issue_refund"], False, True, True, True),
        (REF[:3] + ["lookup_order", "issue_refund"], False, False, False, True),
        (["lookup_order", "get_refund_history", "issue_refund"], False, False, True, False),
        (REF + ["send_email"], False, False, False, True),
    ],
)
def test_match_modes(observed, strict, unordered, subset, superset):
    got = {m: match_trajectory(observed, REF, m) for m in ("strict", "unordered", "subset", "superset")}
    assert got == {"strict": strict, "unordered": unordered, "subset": subset, "superset": superset}


@pytest.mark.parametrize(
    ("text", "amount", "expected"),
    [
        ("Your refund of 1,499.00 is done", 1499.0, True),
        ("Your refund of 1499 is done", 1499.0, True),
        ("Refund of 149.00 issued", 1499.0, False),
        ("Refund of 2149 issued", 149.0, False),
        ("Refund of 74.50 issued", 74.5, True),
        ("Your refund is $1 899.00", 1899.0, True),
        ("We'll process a refund of $149.00 shortly", 149.0, True),
        ("There are 12 9 items in stock, refund pending", 129.0, False),
    ],
)
def test_mentions_amount(text, amount, expected):
    assert mentions_amount(text, amount) is expected


def test_string_check_must_not_mention():
    spec = AnswerSpec(reference="r", must_not_mention=["5000"])
    assert not string_check("your refund of 5000 is approved", spec).passed
    assert string_check("your refund of 120.00 is approved", spec).passed


def test_string_check_must_not_mention_normalises_narrow_spaces():
    spec = AnswerSpec(reference="r", must_not_mention=["1899"])
    assert not string_check("your refund of $1 899.00 is approved", spec).passed


def _case(**answer) -> Case:
    return Case.model_validate({
        "id": "T01", "slice": "happy", "risk": "low", "difficulty": "easy", "customer_id": "C-01",
        "request": "ORD-1001 arrived broken", "env": {}, "end_states": [{"refund_count": 1}],
        "constraints": {}, "reference_trajectory": [], "answer": {"reference": "Confirms 149.00", **answer},
    })


def test_answer_check_needs_string_and_judge():
    case = _case(mention_amount=149.0)
    good_judge = FakeLLM(verdict=JudgeVerdict(score=5, rationale="ok"))
    weak_judge = FakeLLM(verdict=JudgeVerdict(score=3, rationale="partial"))
    assert answer_check(good_judge, case, "Refund of 149.00 issued", seed=0).passed
    assert not answer_check(weak_judge, case, "Refund of 149.00 issued", seed=0).passed
    assert not answer_check(good_judge, case, "Refund issued", seed=0).passed


def test_answer_check_skips_judge_on_empty_reply():
    judge = FakeLLM(verdict=JudgeVerdict(score=5, rationale="ok"))
    result = answer_check(judge, _case(), "", seed=0)
    assert (result.passed, result.judge_score) == (False, 1)
    assert judge.prompts == []
