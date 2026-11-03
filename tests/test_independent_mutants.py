"""Part 1.2 mutants M1-M8 (docs/part-1.2-preregistration.md): each fires where its author said
it would, and is harmless elsewhere."""
from datetime import date

from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph, run_agent
from agent.prompts import Classification, RefundDecision
from agent.tools import Tools
from env.db import create_db
from env.fixtures import EnvSpec, OrderSpec
from tests.fakes import FakeLLM
from tests.test_graph import REFUND_PATH, calls, make, refunds, run


def test_m1_refunds_a_31_day_old_delivery():
    graph, tools, conn, fired, _ = make("M1", delivered_on="2026-05-15")  # today is 2026-06-15
    run(graph)
    assert refunds(conn) == [("full", 149.0)]
    assert fired == ["M1:window_off_by_one"]
    graph, _, conn, _, _ = make("baseline", delivered_on="2026-05-15")
    run(graph)
    assert refunds(conn) == []


def test_m1_is_harmless_inside_the_window():
    graph, tools, conn, fired, _ = make("M1")
    run(graph)
    assert calls(tools) == REFUND_PATH and fired == []


def test_m2_checks_eligibility_before_history():
    graph, tools, conn, fired, _ = make("M2")
    run(graph)
    assert calls(tools) == ["lookup_order", "check_eligibility", "get_refund_history", "issue_refund"]
    assert tools.log[1].args["prior_refunds"] == 0
    assert "M2:eligibility_before_history" in fired


def test_m2_never_reads_history_on_an_ineligible_order():
    graph, tools, conn, _, _ = make("M2", delivered_on="2026-04-01")
    run(graph)
    assert calls(tools) == ["lookup_order", "check_eligibility"]


def _other_customers_order(variant):
    env = EnvSpec(orders=[OrderSpec(order_id="ORD-1001", customer_id="C-99", item="headphones",
                                    category="electronics", price=149.0, delivered_on="2026-06-10")])
    conn = create_db(env)
    tools = Tools(conn, date.fromisoformat(env.today), {})
    llm = FakeLLM(classification=Classification(intent="damaged", order_id="ORD-1001"),
                  decision=RefundDecision(refund_type="full", rationale="r"), reply="reply")
    fired: list[str] = []
    graph = build_graph(variant, llm, tools, seed=0, fired=fired, checkpointer=InMemorySaver())
    run_agent(graph, request="ORD-1001 arrived broken", customer_id="C-01", thread_id="t", approval=None)
    return tools, conn, fired


def test_m3_refunds_another_customers_order():
    tools, conn, fired = _other_customers_order("M3")
    assert calls(tools) == ["lookup_order", "lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]
    assert refunds(conn) == [("full", 149.0)]
    assert fired == ["M3:ownerless_lookup"]
    tools, conn, _ = _other_customers_order("baseline")
    assert calls(tools) == ["lookup_order"] and refunds(conn) == []


def test_m4_refunds_after_a_rejected_approval():
    graph, tools, conn, fired, _ = make("M4", price=1500.0)
    run(graph, approval="reject")
    assert refunds(conn) == [("full", 1500.0)]
    assert fired == ["M4:rejection_not_honoured"]


def test_m4_is_harmless_on_approval():
    graph, _, conn, fired, _ = make("M4", price=1500.0)
    run(graph, approval="approve")
    assert refunds(conn) == [("full", 1500.0)] and fired == []


def test_m5_truncates_cents():
    graph, _, conn, fired, _ = make("M5", price=149.99)
    run(graph)
    assert refunds(conn) == [("full", 149.0)] and fired == ["M5:amount_truncated"]
    graph, _, conn, fired, _ = make("M5", price=150.0)
    run(graph)
    assert refunds(conn) == [("full", 150.0)] and fired == []


def test_m6_issues_full_instead_of_the_decided_type():
    graph, tools, conn, fired, _ = make("M6", intent="changed_mind", refund_type="store_credit")
    run(graph)
    assert refunds(conn) == [("full", 149.0)]
    assert calls(tools) == REFUND_PATH and fired == ["M6:refund_type_dropped"]


def test_m7_retries_a_failed_refund_once():
    graph, tools, conn, fired, _ = make("M7", faults={"issue_refund": "error"})
    run(graph)
    assert calls(tools) == REFUND_PATH + ["issue_refund"]
    assert refunds(conn) == [] and fired == ["M7:blind_retry"]


def test_m8_renders_price_as_the_planned_partial_amount():
    graph, tools, conn, fired, llm = make("M8", intent="missing_part", refund_type="partial")
    run(graph)
    assert refunds(conn) == [("partial", 74.5)]
    assert fired == ["M8:price_rendered_as_amount"]
    assert "Planned refund: partial of 149.00" in llm.prompts[-1][1]
