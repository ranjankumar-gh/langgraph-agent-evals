"""Seeds a fresh in-memory SQLite database for one eval run."""
from __future__ import annotations

import sqlite3

from env.fixtures import EnvSpec

SCHEMA = """
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    item TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    delivered_on TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    refund_type TEXT NOT NULL,
    amount REAL NOT NULL,
    created_on TEXT NOT NULL
);
"""


def create_db(env: EnvSpec) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(o.order_id, o.customer_id, o.item, o.category, o.price, o.delivered_on, o.notes) for o in env.orders],
    )
    conn.executemany(
        "INSERT INTO refunds VALUES (?, ?, ?, 'full', ?, ?)",
        [
            (f"PRIOR-{i:02d}", r.order_id, r.customer_id, r.amount, r.created_on)
            for i, r in enumerate(env.prior_refunds)
        ],
    )
    conn.commit()
    return conn
