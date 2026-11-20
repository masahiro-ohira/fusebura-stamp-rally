"""Reproducible SQLite tests for the D1 scan-order migration and guarded INSERT.

Run from repository root:
    python -m unittest discover -s tests -v
No network, Cloudflare credentials, or production database is used.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "migrations" / "0001_unique_scan_order.sql").read_text(encoding="utf-8")
API = (ROOT / "functions" / "api.js").read_text(encoding="utf-8")
MATCH = re.search(
    r"\.prepare\(\s*`\s*(INSERT INTO stamps\s*\(participant_id, spot_id, scan_order\)[\s\S]*?)`\s*\)",
    API,
)
if not MATCH:
    raise RuntimeError("Guarded INSERT could not be found in functions/api.js")
INSERT_SQL = MATCH.group(1)

SCHEMA = """
CREATE TABLE stamps (
  id INTEGER PRIMARY KEY,
  participant_id TEXT NOT NULL,
  spot_id TEXT NOT NULL,
  acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  scan_order INTEGER NOT NULL
);
"""


def scan(db, participant_id, spot_id):
    return db.execute(
        INSERT_SQL,
        (participant_id, spot_id, participant_id, participant_id, spot_id),
    ).rowcount


class ScanOrderIndexTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA + MIGRATION)

    def tearDown(self):
        self.db.close()

    def test_index_is_unique_and_reapplicable(self):
        self.db.executescript(MIGRATION)
        indexes = self.db.execute("PRAGMA index_list('stamps')").fetchall()
        found = [row for row in indexes if row[1] == "idx_stamps_participant_scan_order"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], 1)

    def test_revisit_is_recorded_but_distinct_count_does_not_rise(self):
        self.assertEqual(scan(self.db, "p1", "v1"), 1)
        self.assertEqual(scan(self.db, "p1", "v1"), 0)
        self.assertEqual(scan(self.db, "p1", "v2"), 1)
        self.assertEqual(scan(self.db, "p1", "v1"), 1)
        rows = self.db.execute(
            "SELECT spot_id, scan_order FROM stamps WHERE participant_id = 'p1' ORDER BY scan_order"
        ).fetchall()
        self.assertEqual(rows, [("v1", 1), ("v2", 2), ("v1", 3)])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(DISTINCT spot_id) FROM stamps WHERE participant_id = 'p1'"
            ).fetchone()[0],
            2,
        )

    def test_different_participants_can_have_same_order(self):
        self.assertEqual(scan(self.db, "p1", "v1"), 1)
        self.assertEqual(scan(self.db, "p2", "v1"), 1)

    def test_forced_duplicate_order_is_blocked(self):
        self.assertEqual(scan(self.db, "p1", "v1"), 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO stamps (participant_id, spot_id, scan_order) VALUES (?, ?, ?)",
                ("p1", "v2", 1),
            )

    def test_migration_rejects_preexisting_duplicate(self):
        other = sqlite3.connect(":memory:")
        try:
            other.executescript(SCHEMA)
            other.execute(
                "INSERT INTO stamps (participant_id, spot_id, scan_order) VALUES ('p1', 'v1', 1)"
            )
            other.execute(
                "INSERT INTO stamps (participant_id, spot_id, scan_order) VALUES ('p1', 'v2', 1)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                other.executescript(MIGRATION)
            self.assertEqual(other.execute("SELECT COUNT(*) FROM stamps").fetchone()[0], 2)
        finally:
            other.close()

    def test_parallel_calls_remain_unique(self):
        for spot_ids, expected_changes in [
            (("v1", "v1"), [0, 1]),
            (("v1", "v2"), [1, 1]),
        ]:
            with self.subTest(spot_ids=spot_ids), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "scan.sqlite3"
                setup = sqlite3.connect(path)
                setup.executescript(SCHEMA + MIGRATION)
                setup.close()
                barrier = threading.Barrier(2)

                def worker(spot_id):
                    conn = sqlite3.connect(path, timeout=10)
                    try:
                        barrier.wait(timeout=10)
                        with conn:
                            return scan(conn, "p1", spot_id)
                    finally:
                        conn.close()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    counts = list(pool.map(worker, spot_ids))
                self.assertEqual(sorted(counts), expected_changes)
                check = sqlite3.connect(path)
                try:
                    orders = [
                        row[0] for row in check.execute(
                            "SELECT scan_order FROM stamps WHERE participant_id = 'p1' ORDER BY scan_order"
                        )
                    ]
                    self.assertEqual(orders, list(range(1, len(orders) + 1)))
                    self.assertEqual(len(orders), len(set(orders)))
                finally:
                    check.close()


if __name__ == "__main__":
    unittest.main()
