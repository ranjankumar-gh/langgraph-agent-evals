from agent.prompts import Classification, RefundDecision
from evals.checks.answer import JudgeVerdict
from evals.runner_part2 import ArmLLMs, namespace, namespaces_for, run_group
from evals.schema import Case
from tests.fakes import FakeLLM

ORDER = {"order_id": "ORD-1001", "customer_id": "C-01", "item": "headphones", "category": "electronics"}
COMMON = {"risk": "low", "difficulty": "easy", "customer_id": "C-01",
          "request": "Order ORD-1001: the headphones arrived broken."}
REFUND_CONSTRAINTS = {"required": ["lookup_order", "check_eligibility", "issue_refund"],
                      "ordering": [["lookup_order", "check_eligibility"], ["check_eligibility", "issue_refund"]],
                      "max_calls": {"lookup_order": 2, "issue_refund": 1}}
REFUND_PATH = ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]

ELIGIBLE = Case.model_validate({
    **COMMON, "id": "T01", "slice": "happy",
    "env": {"orders": [{**ORDER, "price": 149.0, "delivered_on": "2026-06-10"}]},
    "end_states": [{"refund_count": 1, "refund_type": "full", "amount": 149.0}],
    "constraints": REFUND_CONSTRAINTS, "reference_trajectory": REFUND_PATH,
    "answer": {"reference": "Confirms a full refund of 149.00", "mention_amount": 149.0},
})
INELIGIBLE = Case.model_validate({
    **COMMON, "id": "T02", "slice": "ineligible",
    "env": {"orders": [{**ORDER, "price": 149.0, "delivered_on": "2026-04-01"}]},
    "end_states": [{"refund_count": 0}],
    "constraints": {"required": ["lookup_order", "check_eligibility"], "forbidden": ["issue_refund"],
                    "ordering": [["lookup_order", "check_eligibility"]], "max_calls": {"lookup_order": 2}},
    "reference_trajectory": REFUND_PATH[:3],
    "answer": {"reference": "Explains the 30-day refund window has passed; no refund is issued."},
})
APPROVAL = Case.model_validate({
    **COMMON, "id": "T03", "slice": "happy", "approval": "approve",
    "env": {"orders": [{**ORDER, "price": 1500.0, "delivered_on": "2026-06-10"}]},
    "end_states": [{"refund_count": 1, "refund_type": "full", "amount": 1500.0}],
    "constraints": REFUND_CONSTRAINTS, "reference_trajectory": REFUND_PATH,
    "answer": {"reference": "Confirms a full refund of 1500.00", "mention_amount": 1500.0},
})


def arm_llms(changes, reply="Your full refund of 149.00 has been issued.", crash_agent=False):
    def agent():
        llm = FakeLLM(classification=Classification(intent="damaged", order_id="ORD-1001"),
                      decision=RefundDecision(refund_type="full", rationale="broken"), reply=reply)
        if crash_agent:
            llm.responses = []
        return llm

    return {ns: ArmLLMs(agent(), FakeLLM(verdict=JudgeVerdict(score=5, rationale="ok"))) for ns in namespaces_for(changes)}


def by(rows, arm, change):
    (row,) = [r for r in rows if r["arm"] == arm and r["change"] == change]
    return row


def test_namespaces_share_d_draws_with_e_and_fork_draws_with_naive():
    assert namespace("baseline", "baseline") == ""
    assert namespace("full", "D") == namespace("full", "E") == "p2-full-D"
    assert namespace("fork", "E") == namespace("fork_naive", "D") == "p2-fork-D"
    assert namespaces_for(["baseline", "D", "E"]) == ["", "p2-fork-D", "p2-fork-baseline", "p2-full-D", "p2-full-baseline"]


def test_group_emits_a_baseline_row_then_three_rows_per_change():
    rows = run_group(ELIGIBLE, 0, ["baseline", "D"], arm_llms(["baseline", "D"]))
    assert [(r["arm"], r["change"]) for r in rows] == [
        ("baseline", "baseline"),
        ("full", "baseline"), ("fork", "baseline"), ("fork_naive", "baseline"),
        ("full", "D"), ("fork", "D"), ("fork_naive", "D"),
    ]
    assert all({"policy", "judge"} <= set(r["cost"]) for r in rows)


def test_paired_fork_of_the_noop_change_reproduces_the_baseline():
    rows = run_group(ELIGIBLE, 0, ["baseline"], arm_llms(["baseline"]))
    base, fork = by(rows, "baseline", "baseline"), by(rows, "fork", "baseline")
    assert (fork["end_state_pass"], fork["constraints_pass"]) == (base["end_state_pass"], base["constraints_pass"]) == (True, True)
    assert [c["name"] for c in fork["tool_calls"]] == REFUND_PATH
    assert fork["fork"]["fork_point_step"] == 4 and fork["fork"]["inherited"] is False
    assert fork["fork"]["carried_limit"] == 20


def test_fork_rows_carry_the_baseline_prefix_in_node_sequence():
    rows = run_group(ELIGIBLE, 0, ["D"], arm_llms(["D"]))
    assert by(rows, "fork", "D")["node_sequence"] == [
        "classify_request", "lookup_order", "get_refund_history", "check_eligibility",
        "compute_refund", "issue_refund", "respond",
    ]


def test_naive_fork_of_the_noop_change_fails_end_state_and_constraints():
    rows = run_group(ELIGIBLE, 0, ["baseline"], arm_llms(["baseline"]))
    naive = by(rows, "fork_naive", "baseline")
    assert len(naive["refunds"]) == 2
    assert naive["end_state_pass"] is False
    assert naive["constraints_pass"] is False and "issue_refund called 2 times" in naive["constraints_detail"]


def test_no_fork_point_inherits_and_records_routing():
    rows = run_group(INELIGIBLE, 0, ["D", "E"], arm_llms(["D", "E"], reply="Sorry, the 30-day window has passed."))
    for change, routing_ok in (("D", True), ("E", False)):
        for arm in ("fork", "fork_naive"):
            row = by(rows, arm, change)
            assert row["fork"]["inherited"] is True and row["fork"]["fork_point_step"] is None
            assert row["fork"]["routing_ok"] is routing_ok
            assert row["end_state_pass"] is True  # inherited from the baseline
            assert row["variant"] == change
    full_e = by(rows, "full", "E")
    assert full_e["end_state_pass"] is False and full_e["mutations_fired"] == ["E:damaged_fast_path"]


def test_approval_case_forks_through_the_interrupt():
    rows = run_group(APPROVAL, 0, ["D"], arm_llms(["D"], reply="Your full refund of 1500.00 has been issued."))
    fork = by(rows, "fork", "D")
    assert fork["crashed"] is None and fork["end_state_pass"] is True
    assert "request_approval" in fork["node_sequence"]


def test_baseline_crash_still_emits_every_row():
    rows = run_group(ELIGIBLE, 0, ["D"], arm_llms(["D"], crash_agent=True))
    assert len(rows) == 4
    assert by(rows, "baseline", "baseline")["crashed"].startswith("AssertionError")
    fork = by(rows, "fork", "D")
    assert fork["fork"]["inherited"] is True and fork["fork"]["routing_detail"] == "baseline crashed"
