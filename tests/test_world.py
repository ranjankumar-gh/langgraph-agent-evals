from datetime import date

from agent.tools import Tools
from env.db import create_db
from env.fixtures import EnvSpec, OrderSpec


def fresh(reprice=None) -> Tools:
    env = EnvSpec(orders=[OrderSpec(order_id="ORD-1001", customer_id="C-01", item="headphones",
                                    category="electronics", price=149.0, delivered_on="2026-06-10")],
                  reprice_on_reread=reprice)
    return Tools(create_db(env), date.fromisoformat(env.today), {}, reprice_on_reread=reprice)


def refund_rows(tools: Tools):
    return [tuple(r) for r in tools.conn.execute("SELECT refund_id, amount FROM refunds ORDER BY refund_id")]


def test_restored_world_is_a_private_copy_of_the_snapshot_moment():
    tools = fresh()
    tools.lookup_order("ORD-1001", "C-01")
    snap = tools.snapshot()
    tools.issue_refund("ORD-1001", "C-01", "full", 149.0)

    copy = tools.restored(snap)
    assert [c.name for c in copy.log] == ["lookup_order"]
    assert refund_rows(copy) == []

    assert copy.issue_refund("ORD-1001", "C-01", "full", 149.0) == "RF-0001"
    assert refund_rows(copy) == [("RF-0001", 149.0)]
    assert refund_rows(tools) == [("RF-0001", 149.0)]  # the original world is untouched
    assert [c.name for c in tools.log] == ["lookup_order", "issue_refund"]


def test_restored_world_keeps_the_reread_counter():
    tools = fresh(reprice=99.0)
    tools.lookup_order("ORD-1001", "C-01")
    copy = tools.restored(tools.snapshot())
    assert copy.lookup_order("ORD-1001", "C-01")["price"] == 99.0  # second read sees the reprice


def test_restored_world_keeps_faults_and_clock():
    tools = fresh()
    tools.faults["issue_refund"] = "error"
    copy = tools.restored(tools.snapshot())
    assert copy.today == tools.today and copy.faults == {"issue_refund": "error"}
    assert copy.faults is not tools.faults
