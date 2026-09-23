from datetime import date

import pytest

from agent.tools import ToolError, Tools
from env.db import create_db
from env.fixtures import EnvSpec, OrderSpec, PriorRefundSpec

TODAY = date(2026, 6, 15)


def make_tools(*, delivered_on="2026-06-10", category="electronics", priors=0, faults=None):
    env = EnvSpec(
        orders=[
            OrderSpec(
                order_id="ORD-1001",
                customer_id="C-01",
                item="headphones",
                category=category,
                price=149.0,
                delivered_on=delivered_on,
            )
        ],
        prior_refunds=[
            PriorRefundSpec(order_id=f"ORD-00{i}", customer_id="C-01", amount=20.0, created_on="2026-06-01")
            for i in range(priors)
        ],
        faults=faults or {},
    )
    conn = create_db(env)
    return Tools(conn, TODAY, dict(env.faults)), conn


def test_lookup_scoped_to_customer():
    tools, _ = make_tools()
    assert tools.lookup_order("ORD-1001", "C-01")["item"] == "headphones"
    assert tools.lookup_order("ORD-1001", "C-02") is None
    assert [c.name for c in tools.log] == ["lookup_order", "lookup_order"]


def test_refund_history_counts_last_90_days():
    tools, _ = make_tools(priors=2)
    assert tools.get_refund_history("C-01") == 2
    assert tools.get_refund_history("C-02") == 0


@pytest.mark.parametrize(
    ("kwargs", "priors", "eligible", "reason_fragment"),
    [
        ({}, 0, True, "within policy"),
        ({"delivered_on": None}, 0, False, "not been delivered"),
        ({"category": "gift_card"}, 0, False, "not refundable"),
        ({"delivered_on": "2026-05-15"}, 0, False, "30-day refund window"),
        ({"delivered_on": "2026-05-16"}, 0, True, "within policy"),
        ({}, 2, False, "refund limit"),
    ],
)
def test_eligibility_rules(kwargs, priors, eligible, reason_fragment):
    tools, _ = make_tools(**kwargs)
    order = tools.lookup_order("ORD-1001", "C-01")
    result = tools.check_eligibility(order, priors)
    assert result["eligible"] is eligible
    assert reason_fragment in result["reason"]


def test_issue_refund_writes_row():
    tools, conn = make_tools()
    refund_id = tools.issue_refund("ORD-1001", "C-01", "full", 149.0)
    assert refund_id == "RF-0001"
    row = conn.execute("SELECT refund_type, amount, created_on FROM refunds WHERE refund_id = 'RF-0001'").fetchone()
    assert tuple(row) == ("full", 149.0, "2026-06-15")


def test_injected_fault_is_logged_then_raised():
    tools, conn = make_tools(faults={"issue_refund": "error"})
    with pytest.raises(ToolError):
        tools.issue_refund("ORD-1001", "C-01", "full", 149.0)
    assert tools.log[-1].name == "issue_refund"
    assert tools.log[-1].ok is False
    assert conn.execute("SELECT COUNT(*) FROM refunds WHERE refund_id LIKE 'RF-%'").fetchone()[0] == 0
