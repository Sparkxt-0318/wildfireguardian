"""Stdlib sqlite3 persistence: subscriptions and family circles (spec §2, §9).

One short-lived connection per operation — no pooling, no threads to fight.
The database file location comes from ``WFG_DB_PATH`` (default ``guardian.db``).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    customer_id     TEXT PRIMARY KEY,
    subscription_id TEXT,
    plan            TEXT,
    status          TEXT NOT NULL DEFAULT 'inactive',
    renews_utc      TEXT,
    updated_utc     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS families (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  TEXT NOT NULL,
    member_name  TEXT NOT NULL,
    contact      TEXT NOT NULL,
    created_utc  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
"""


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    # -- subscriptions -----------------------------------------------------
    def upsert_subscription(
        self,
        customer_id: str,
        *,
        subscription_id: Optional[str] = None,
        plan: Optional[str] = None,
        status: str = "active",
        renews_utc: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions (customer_id, subscription_id, plan, status, renews_utc,
                                           updated_utc)
                VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                ON CONFLICT(customer_id) DO UPDATE SET
                    subscription_id = COALESCE(excluded.subscription_id, subscription_id),
                    plan            = COALESCE(excluded.plan, plan),
                    status          = excluded.status,
                    renews_utc      = COALESCE(excluded.renews_utc, renews_utc),
                    updated_utc     = excluded.updated_utc
                """,
                (customer_id, subscription_id, plan, status, renews_utc),
            )

    def get_subscription(self, customer_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE customer_id = ?", (customer_id,)
            ).fetchone()
        return dict(row) if row else None
