"""Part 1.3 valid alternates V1-V6 (docs/part-1.3-preregistration.md): each makes the tool calls
its author described, and reaches the same end state and reply facts as the baseline."""
import pytest

from agent.graph import render_facts
from tests.test_graph import REFUND_PATH, calls, make, refunds, run

CHECKED = ["lookup_order", "get_refund_history", "check_eligibility"]


def outcome(variant, **kw):
    approval = kw.pop("approval", None)
    graph, tools, conn, fired, llm = make(variant, **kw)
    values, _ = run(graph, approval=approval)
    return calls(tools), refunds(conn), render_facts(values), fired, llm


SCENARIOS = {
    "happy": {},
    "partial": {"intent": "missing_part", "refund_type": "partial"},
    "not_found": {"order_id": "ORD-9999"},
    "lookup_fails": {"faults": {"lookup_order": "error"}},
    "history_fails": {"faults": {"get_refund_history": "error"}},
    "refund_fails": {"faults": {"issue_refund": "error"}},
    "ineligible": {"delivered_on": "2026-04-01"},
    "approved": {"price": 1500.0, "approval": "approve"},
    "rejected": {"price": 1500.0, "approval": "reject"},
}


@pytest.mark.parametrize("variant", ["V1", "V2", "V3", "V4", "V5", "V6"])
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_same_outcome_and_reply_facts_as_baseline(variant, scenario):
    _, base_refunds, base_facts, _, _ = outcome("baseline", **dict(SCENARIOS[scenario]))
    _, v_refunds, v_facts, _, _ = outcome(variant, **dict(SCENARIOS[scenario]))
    assert v_refunds == base_refunds
    assert v_facts == base_facts


def test_v1_retries_a_failed_lookup_once():
    c, _, _, fired, _ = outcome("V1", faults={"lookup_order": "error"})
    assert c == ["lookup_order", "lookup_order"] and fired == ["V1:retried_lookup_order"]
    c, _, _, fired, _ = outcome("V1")
    assert c == REFUND_PATH and fired == []


def test_v1_never_retries_the_write():
    c, _, _, _, _ = outcome("V1", faults={"issue_refund": "error"})
    assert c == REFUND_PATH


def test_v2_reads_history_alongside_a_failed_lookup():
    assert outcome("V2", order_id="ORD-9999")[0] == ["lookup_order", "get_refund_history"]
    assert outcome("V2", faults={"lookup_order": "error"})[0] == ["lookup_order", "get_refund_history"]
    assert outcome("V2")[0] == REFUND_PATH


def test_v3_reads_history_after_every_write_attempt():
    assert outcome("V3")[0] == REFUND_PATH + ["get_refund_history"]
    assert outcome("V3", faults={"issue_refund": "error"})[0] == REFUND_PATH + ["get_refund_history"]
    assert outcome("V3", price=1500.0, approval="reject")[0] == CHECKED


def test_v4_discards_a_speculative_plan_when_ineligible():
    c, r, facts, fired, llm = outcome("V4", delivered_on="2026-04-01")
    assert c == CHECKED and r == [] and "Planned refund" not in facts
    assert fired == ["V4:speculative_plan_discarded"]
    assert outcome("V4")[0] == REFUND_PATH


@pytest.mark.parametrize("variant", ["V5", "V6"])
def test_refactors_make_identical_tool_calls(variant):
    for kw in SCENARIOS.values():
        assert outcome(variant, **dict(kw))[0] == outcome("baseline", **dict(kw))[0]
