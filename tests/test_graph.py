from datetime import date

from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph, run_agent
from agent.prompts import Classification, RefundDecision
from agent.tools import Tools
from env.db import create_db
from env.fixtures import EnvSpec, OrderSpec
from tests.fakes import FakeLLM

REFUND_PATH = ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]


def make(variant, *, price=149.0, faults=None, intent="damaged", refund_type="full", order_id="ORD-1001",
         delivered_on="2026-06-10"):
    env = EnvSpec(
        orders=[OrderSpec(order_id="ORD-1001", customer_id="C-01", item="headphones", category="electronics",
                          price=price, delivered_on=delivered_on)],
        faults=faults or {},
    )
    conn = create_db(env)
    tools = Tools(conn, date.fromisoformat(env.today), dict(env.faults))
    llm = FakeLLM(
        classification=Classification(intent=intent, order_id=order_id),
        decision=RefundDecision(refund_type=refund_type, rationale="r"),
        reply="reply",
    )
    fired: list[str] = []
    graph = build_graph(variant, llm, tools, seed=0, fired=fired, checkpointer=InMemorySaver())
    return graph, tools, conn, fired, llm


def run(graph, approval=None):
    return run_agent(graph, request="ORD-1001 arrived broken", customer_id="C-01", thread_id="t", approval=approval)


def calls(tools):
    return [c.name for c in tools.log]


def refunds(conn):
    return [tuple(r) for r in conn.execute("SELECT refund_type, amount FROM refunds WHERE refund_id LIKE 'RF-%'")]


def test_baseline_happy_path():
    graph, tools, conn, fired, _ = make("baseline")
    values, nodes = run(graph)
    assert calls(tools) == REFUND_PATH
    assert refunds(conn) == [("full", 149.0)]
    assert values["refund_id"] == "RF-0001"
    assert nodes[0] == "classify_request" and nodes[-1] == "respond"
    assert fired == []


def test_partial_refund_is_half_price():
    graph, _, conn, _, _ = make("baseline", intent="missing_part", refund_type="partial")
    run(graph)
    assert refunds(conn) == [("partial", 74.5)]


def test_ineligible_order_is_not_refunded():
    graph, tools, conn, _, _ = make("baseline", delivered_on="2026-04-01")
    run(graph)
    assert calls(tools) == REFUND_PATH[:3]
    assert refunds(conn) == []


def test_no_order_id_calls_no_tools():
    graph, tools, _, _, llm = make("baseline", order_id=None)
    _, nodes = run(graph)
    assert calls(tools) == []
    assert nodes == ["classify_request", "respond"]
    assert "Order id: not provided" in llm.prompts[-1][1]


def test_approval_approved_then_refunded():
    graph, tools, conn, _, _ = make("baseline", price=1499.0)
    _, nodes = run(graph, approval="approve")
    assert "request_approval" in nodes
    assert refunds(conn) == [("full", 1499.0)]


def test_approval_rejected_means_no_refund():
    graph, tools, conn, _, llm = make("baseline", price=1499.0)
    run(graph, approval="reject")
    assert "issue_refund" not in calls(tools)
    assert refunds(conn) == []
    assert "Approval: rejected" in llm.prompts[-1][1]


def test_alt_history_early_reorders_reads():
    graph, tools, conn, fired, _ = make("alt_history_early")
    run(graph)
    assert calls(tools) == ["get_refund_history", "lookup_order", "check_eligibility", "issue_refund"]
    assert refunds(conn) == [("full", 149.0)]
    assert fired == []


def test_alt_recheck_rereads_order_before_refund():
    graph, tools, conn, fired, _ = make("alt_recheck")
    run(graph)
    assert calls(tools) == REFUND_PATH[:3] + ["lookup_order", "issue_refund"]
    assert refunds(conn) == [("full", 149.0)]
    assert fired == []


def test_mutant_a_skips_eligibility_for_damaged():
    graph, tools, conn, fired, _ = make("A", delivered_on="2026-04-01")
    run(graph)
    assert "check_eligibility" not in calls(tools)
    assert refunds(conn) == [("full", 149.0)]
    assert fired == ["A:skipped_eligibility"]


def test_mutant_a_checks_eligibility_for_other_intents():
    graph, tools, _, fired, _ = make("A", intent="changed_mind", refund_type="store_credit")
    run(graph)
    assert "check_eligibility" in calls(tools)
    assert fired == []


def test_mutant_b_reports_planned_status_after_failure():
    graph, _, conn, fired, llm = make("B", faults={"issue_refund": "error"})
    run(graph)
    assert refunds(conn) == []
    assert fired == ["B:false_success"]
    assert "Refund status: issued (full, 149.00)" in llm.prompts[-1][1]


def test_baseline_reports_failure_after_failure():
    graph, _, _, fired, llm = make("baseline", faults={"issue_refund": "error"})
    run(graph)
    assert fired == []
    assert "Refund status: not issued" in llm.prompts[-1][1]
    assert "Error: issue_refund failed" in llm.prompts[-1][1]


def test_mutant_c_looks_up_order_four_times():
    graph, tools, conn, fired, _ = make("C")
    run(graph)
    assert calls(tools).count("lookup_order") == 4
    assert refunds(conn) == [("full", 149.0)]
    assert fired.count("C:redundant_lookup") == 3


def test_lookup_failure_routes_to_respond():
    graph, tools, conn, _, llm = make("baseline", faults={"lookup_order": "error"})
    run(graph)
    assert calls(tools) == ["lookup_order"]
    assert refunds(conn) == []
    assert "Error: lookup_order failed" in llm.prompts[-1][1]
