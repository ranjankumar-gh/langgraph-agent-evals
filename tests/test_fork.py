from datetime import date

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from agent.graph import build_graph, make_routers
from agent.prompts import Classification, RefundDecision
from agent.tools import Tools
from env.db import create_db
from env.fixtures import EnvSpec, OrderSpec
from evals.fork import carried_limit, check_routing, find_fork_point, fork_run, history, record_run
from tests.fakes import FakeLLM

REFUND_PATH = ["lookup_order", "get_refund_history", "check_eligibility", "issue_refund"]


def world(price=149.0, delivered_on="2026-06-10") -> Tools:
    env = EnvSpec(orders=[OrderSpec(order_id="ORD-1001", customer_id="C-01", item="tv",
                                    category="electronics", price=price, delivered_on=delivered_on)])
    return Tools(create_db(env), date.fromisoformat(env.today), {})


def graph_for(variant, tools, saver, fired=None):
    llm = FakeLLM(classification=Classification(intent="damaged", order_id="ORD-1001"),
                  decision=RefundDecision(refund_type="full", rationale="r"))
    return build_graph(variant, llm, tools, seed=0, fired=fired if fired is not None else [], checkpointer=saver)


def record(tools, saver, *, approval=None, limit=25):
    graph = graph_for("baseline", tools, saver)
    rec = record_run(graph, tools, request="ORD-1001 arrived broken", customer_id="C-01",
                     thread_id="t", approval=approval, recursion_limit=limit)
    return graph, rec


def refunds(tools):
    return [tuple(r) for r in tools.conn.execute("SELECT refund_type, amount FROM refunds WHERE refund_id LIKE 'RF-%'")]


def test_record_run_snapshots_every_step():
    tools, saver = world(price=1500.0), InMemorySaver()
    graph, rec = record(tools, saver, approval="approve")
    ids = [s.config["configurable"]["checkpoint_id"] for s in history(graph, "t") if s.metadata["step"] >= 1]
    assert ids and all(i in rec.snapshots for i in ids)
    assert rec.nodes[-1] == "respond"


def test_fork_point_is_the_checkpoint_before_the_changed_node():
    tools, saver = world(), InMemorySaver()
    graph, _ = record(tools, saver)
    fp = find_fork_point(history(graph, "t"), "compute_refund")
    assert fp.next == ("compute_refund",) and fp.metadata["step"] == 4


def test_no_fork_point_when_the_baseline_never_reaches_the_node():
    tools, saver = world(delivered_on="2026-04-01"), InMemorySaver()
    graph, _ = record(tools, saver)
    assert find_fork_point(history(graph, "t"), "compute_refund") is None


def test_paired_fork_runs_on_the_world_as_it_was_at_the_fork_point():
    tools, saver = world(), InMemorySaver()
    graph, rec = record(tools, saver)
    fp = find_fork_point(history(graph, "t"), "compute_refund")
    forked = tools.restored(rec.snapshots[fp.config["configurable"]["checkpoint_id"]])
    values, nodes = fork_run(graph_for("D", forked, saver), fp, approval=None)
    assert nodes == ["compute_refund", "issue_refund", "respond"]
    assert [c.name for c in forked.log] == REFUND_PATH
    assert refunds(forked) == [("full", 149.0)]
    assert refunds(tools) == [("full", 149.0)]  # the baseline's own world is unchanged


def test_naive_fork_on_the_left_behind_world_double_refunds():
    tools, saver = world(), InMemorySaver()
    graph, _ = record(tools, saver)
    fp = find_fork_point(history(graph, "t"), "compute_refund")
    naive = tools.restored(tools.snapshot())  # the world as the baseline left it
    fork_run(graph_for("baseline", naive, saver), fp, approval=None)
    assert refunds(naive) == [("full", 149.0), ("full", 149.0)]
    assert [c.name for c in naive.log].count("issue_refund") == 2


def test_fork_resumes_an_approval_interrupt_on_its_own_branch():
    tools, saver = world(price=1500.0), InMemorySaver()
    graph, rec = record(tools, saver, approval="approve")
    fp = find_fork_point(history(graph, "t"), "compute_refund")
    snap = rec.snapshots[fp.config["configurable"]["checkpoint_id"]]
    for variant in ("D", "baseline"):  # two forks from one point: each resumes its own pause
        forked = tools.restored(snap)
        _, nodes = fork_run(graph_for(variant, forked, saver), fp, approval="approve")
        assert nodes == ["compute_refund", "request_approval", "issue_refund", "respond"]
        assert refunds(forked) == [("full", 1500.0)]


def test_check_routing_flags_e_where_the_baseline_refused():
    tools, saver = world(delivered_on="2026-04-01"), InMemorySaver()
    graph, _ = record(tools, saver)
    hist = history(graph, "t")
    ok, detail = check_routing(hist, make_routers("E", []))
    assert not ok and "check_eligibility" in detail and "compute_refund" in detail
    assert check_routing(hist, make_routers("D", [])) == (True, "ok")


def test_check_routing_passes_e_up_to_the_fork_point_on_an_eligible_order():
    tools, saver = world(), InMemorySaver()
    graph, _ = record(tools, saver)
    hist = history(graph, "t")
    fp = find_fork_point(hist, "compute_refund")
    assert check_routing(hist, make_routers("E", []), until=fp) == (True, "ok")


def test_carried_limit_arithmetic():
    assert carried_limit(8, 4) == 3
    assert carried_limit(25, 4) == 20


def test_a_fork_gets_a_fresh_recursion_budget_unless_it_is_carried():
    """The full non-approval refund run needs recursion_limit 8 (steps 0-7); its fork point
    is step 4. A raw fork under limit 7 finishes - a budget the full run did not have. The
    carried limit makes the fork stop exactly where the full run would."""
    with pytest.raises(GraphRecursionError):
        record(world(), InMemorySaver(), limit=7)

    tools, saver = world(), InMemorySaver()
    graph, rec = record(tools, saver)
    fp = find_fork_point(history(graph, "t"), "compute_refund")
    snap = rec.snapshots[fp.config["configurable"]["checkpoint_id"]]

    raw = graph_for("baseline", tools.restored(snap), saver)
    raw.invoke(None, {**fp.config, "recursion_limit": 7})  # fresh budget: no error

    with pytest.raises(GraphRecursionError):
        fork_run(graph_for("baseline", tools.restored(snap), saver), fp, approval=None, recursion_limit=7)
    fork_run(graph_for("baseline", tools.restored(snap), saver), fp, approval=None, recursion_limit=8)
