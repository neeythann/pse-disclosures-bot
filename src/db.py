from __future__ import annotations

import sqlite3
from os import getenv
from typing import Iterable, Sequence, Set

DB_PATH = getenv("DB_PATH", "pse_disclosures.db")

TABLE_COLUMNS: dict[str, list[str]] = {
    "company_disclosures": ["_id", "company_name", "title", "form_type", "date", "circular_number"],
    "dividends": ["_id", "company_name", "security_type", "dividend_type", "rate", "ex_date", "record_date", "payment_date", "circular_number"],
    "stock_rights": ["_id", "company_name", "entitlement_ratio", "offer_price", "ex_rights_date", "offer_start", "offer_end", "circular_number"],
}


class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(path)
        self._create_tables()

    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        for table, cols in TABLE_COLUMNS.items():
            col_defs = ", ".join(
                ["edge_no TEXT PRIMARY KEY"]
                + ["{} TEXT".format(c) for c in cols]
                + ["created_at TEXT DEFAULT CURRENT_TIMESTAMP"]
            )
            cur.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(table, col_defs))
        self.conn.commit()

    def is_empty(self, table: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM {}".format(table))
        return cur.fetchone()[0] == 0

    def get_existing_edge_nos(self, table: str, edge_nos: Iterable[str]) -> Set[str]:
        edge_nos = list(edge_nos)
        if not edge_nos:
            return set()
        placeholders = ",".join("?" for _ in edge_nos)
        cur = self.conn.cursor()
        cur.execute(
            "SELECT edge_no FROM {} WHERE edge_no IN ({})".format(table, placeholders),
            edge_nos,
        )
        return {row[0] for row in cur.fetchall()}

    def insert(self, table: str, items: Sequence) -> None:
        if not items:
            return
        cols = TABLE_COLUMNS[table]
        all_cols = ["edge_no"] + cols
        placeholders = ",".join("?" for _ in all_cols)
        sql = "INSERT OR IGNORE INTO {} ({}) VALUES ({})".format(
            table, ",".join(all_cols), placeholders
        )
        cur = self.conn.cursor()
        rows = [[getattr(item, c) for c in all_cols] for item in items]
        cur.executemany(sql, rows)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
