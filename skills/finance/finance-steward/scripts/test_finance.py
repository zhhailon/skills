#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import finance as fin


ACCOUNT_KEY = "stable-local-account-key"
REFERENCES = Path(__file__).parents[1] / "references"


class StageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "statement.pdf"
        self.source.write_bytes(b"private statement")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def extraction(self, run_id: str, *, amount: int = -1234, model: str = "test-model") -> dict:
        return {
            "schema_version": fin.EXTRACTION_SCHEMA,
            "model": model,
            "run_id": run_id,
            "source_sha256": fin.sha256_file(self.source),
            "total_pages": 2,
            "reviewed_pages": [1, 2],
            "transaction_count": 1,
            "complete": True,
            "uncertainties": [],
            "transactions": [{
                "transaction_date": "2026-08-01",
                "posted_date": None,
                "description": "CAFE 123456789",
                "amount_minor": amount,
                "currency": "USD",
                "source_page": 2,
                "source_index": 1,
                "status": "posted",
            }],
        }

    def stage(self, first: dict, second: dict) -> tuple[int, dict]:
        first_path = self.root / "first.json"
        second_path = self.root / "second.json"
        output = self.root / "staging.jsonl"
        first_path.write_text(json.dumps(first))
        second_path.write_text(json.dumps(second))
        code = fin.run_stage(Namespace(
            source=str(self.source), extraction=str(first_path), verification=str(second_path),
            output=str(output), account_key="test-account",
        ))
        return code, json.loads(output.with_suffix(".jsonl.manifest.json").read_text())

    def test_same_model_fresh_context_can_stage(self) -> None:
        code, manifest = self.stage(self.extraction("run-a"), self.extraction("run-b"))
        self.assertEqual(code, 0)
        self.assertEqual(manifest["verification_mode"], "same_model_fresh_context")
        record = json.loads((self.root / "staging.jsonl").read_text())
        self.assertEqual(record["description"], "CAFE 123456789")

    def test_different_results_need_review(self) -> None:
        code, manifest = self.stage(self.extraction("run-a"), self.extraction("run-b", amount=-999))
        self.assertEqual(code, 2)
        self.assertEqual(manifest["status"], "needs_review")
        self.assertEqual(manifest["reconciliation"]["missing_count"], 1)

    def test_out_of_schema_fields_fail(self) -> None:
        first = self.extraction("run-a")
        first["transactions"][0]["balance"] = "private"
        with self.assertRaises(fin.FinanceFailure):
            self.stage(first, self.extraction("run-b"))


class LoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "statement.pdf"
        self.source.write_bytes(b"private statement")
        self.staging = self.root / "statement.jsonl"
        self.manifest = self.root / "manifest.json"
        self.ledger = self.root / "ledger.sqlite"
        self.schema = REFERENCES / "schema.sql"
        self.extensions = REFERENCES / "schema-extensions.sql"
        self.write_batch([self.record(1, -1234)])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self, index: int, amount_minor: int, currency: str = "USD") -> dict:
        return {
            "schema_version": fin.STAGING_SCHEMA,
            "source_sha256": fin.sha256_file(self.source),
            "source_locator": f"page:1:item:{index}",
            "transaction_date": "2026-08-01",
            "posted_date": None,
            "description": f"MERCHANT {index}",
            "amount_minor": amount_minor,
            "currency": currency,
            "balance_minor": None,
            "external_id": None,
            "status": "posted",
            "record_hash": fin.sha256_bytes(f"record-{index}".encode()),
            "dedupe_key": fin.sha256_bytes(f"dedupe-{index}".encode()),
        }

    def write_batch(self, records: list[dict]) -> None:
        self.staging.write_text("".join(json.dumps(record) + "\n" for record in records))
        self.manifest.write_text(json.dumps({
            "status": "staged",
            "source_sha256": fin.sha256_file(self.source),
            "output_sha256": fin.sha256_file(self.staging),
            "record_count": len(records),
            "verification_mode": "same_model_fresh_context",
            "reconciliation": {"matched": True, "missing_count": 0, "extra_count": 0},
            "uncertainty_count": 0,
            "duplicate_dedupe_key_count": 0,
            "account_key_hash": fin.sha256_bytes(ACCOUNT_KEY.encode()),
        }))

    def args(self, **overrides) -> Namespace:
        values = dict(
            source=str(self.source), staging=str(self.staging), manifest=str(self.manifest),
            ledger=str(self.ledger), schema=str(self.schema), extensions=None,
            household_id="household-local", timezone="America/New_York", base_currency="USD",
            account_key=None, account_type=None, account_name=None,
        )
        values.update(overrides)
        return Namespace(**values)

    def posting_args(self, **overrides) -> Namespace:
        values = {"account_key": ACCOUNT_KEY, "account_type": "liability"}
        values.update(overrides)
        return self.args(**values)

    def query(self, sql: str, *params):
        with sqlite3.connect(self.ledger) as conn:
            return conn.execute(sql, params).fetchall()

    def test_load_without_account_leaves_drafts(self) -> None:
        self.assertEqual(fin.run_load(self.args()), 0)
        self.assertEqual(fin.run_load(self.args()), 0)
        self.assertEqual(self.query("SELECT count(*) FROM source_files")[0][0], 1)
        self.assertEqual(self.query("SELECT count(*) FROM import_records")[0][0], 1)
        self.assertEqual(self.query("SELECT status FROM transactions")[0][0], "draft")
        self.assertEqual(self.query("SELECT count(*) FROM postings")[0][0], 0)

    def test_posting_creates_balanced_double_entry(self) -> None:
        self.write_batch([self.record(1, -1234), self.record(2, 500000)])
        self.assertEqual(fin.run_load(self.posting_args()), 0)
        self.assertEqual(
            self.query("SELECT count(*) FROM transactions WHERE status='posted'")[0][0], 2
        )
        balances = self.query(
            "SELECT transaction_id, sum(base_amount_minor), count(*) FROM postings GROUP BY transaction_id"
        )
        self.assertEqual(len(balances), 2)
        for _, total, legs in balances:
            self.assertEqual(total, 0)
            self.assertEqual(legs, 2)
        types = dict(self.query(
            """
            SELECT a.account_type, sum(p.amount_minor)
            FROM postings AS p JOIN accounts AS a ON a.id = p.account_id
            GROUP BY a.account_type
            """
        ))
        self.assertEqual(types["liability"], -1234 + 500000)
        self.assertEqual(types["expense"], 1234)
        self.assertEqual(types["income"], -500000)

    def test_posted_ledger_populates_analytical_views(self) -> None:
        self.write_batch([self.record(1, -1234), self.record(2, 500000)])
        self.assertEqual(fin.run_load(self.posting_args(account_name="Card")), 0)
        register = self.query(
            """
            SELECT account_name, signed_amount_minor, ledger_running_balance_minor, transaction_kind
            FROM household_account_register ORDER BY signed_amount_minor
            """
        )
        self.assertEqual([row[0] for row in register], ["Card", "Card"])
        self.assertEqual([row[1] for row in register], [-1234, 500000])
        self.assertEqual(register[-1][2], -1234 + 500000)
        self.assertEqual(sorted(row[3] for row in register), ["expense", "income"])
        categories = self.query(
            "SELECT category_type, activity_minor FROM household_transaction_categories ORDER BY category_type"
        )
        self.assertEqual(categories, [("expense", 1234), ("income", 500000)])

    def test_posting_is_idempotent(self) -> None:
        self.assertEqual(fin.run_load(self.posting_args()), 0)
        self.assertEqual(fin.run_load(self.posting_args()), 0)
        self.assertEqual(self.query("SELECT count(*) FROM postings")[0][0], 2)
        self.assertEqual(self.query("SELECT count(*) FROM transactions")[0][0], 1)
        self.assertEqual(self.query("SELECT status FROM transactions")[0][0], "posted")

    def test_foreign_currency_stays_draft(self) -> None:
        self.write_batch([self.record(1, -1234, currency="EUR")])
        self.assertEqual(fin.run_load(self.posting_args()), 0)
        self.assertEqual(self.query("SELECT status FROM transactions")[0][0], "draft")
        self.assertEqual(self.query("SELECT count(*) FROM postings")[0][0], 0)

    def test_account_key_must_match_manifest(self) -> None:
        with self.assertRaises(fin.FinanceFailure):
            fin.run_load(self.posting_args(account_key="a-different-key"))

    def test_account_type_requires_account_key(self) -> None:
        with self.assertRaises(fin.FinanceFailure):
            fin.run_load(self.args(account_type="asset"))

    def test_conflicting_account_type_is_rejected(self) -> None:
        self.assertEqual(fin.run_load(self.posting_args(account_type="liability")), 0)
        with self.assertRaises(fin.FinanceFailure):
            fin.run_load(self.posting_args(account_type="asset"))
        self.assertEqual(
            self.query("SELECT account_type FROM accounts WHERE id LIKE 'account-%' "
                       "AND account_type IN ('asset','liability')")[0][0],
            "liability",
        )

    def test_conflicting_base_currency_is_rejected(self) -> None:
        self.assertEqual(fin.run_load(self.posting_args()), 0)
        with self.assertRaises(fin.FinanceFailure):
            fin.run_load(self.posting_args(base_currency="EUR"))

    def test_extensions_are_optional_and_applicable(self) -> None:
        self.assertEqual(fin.run_load(self.posting_args(extensions=str(self.extensions))), 0)
        self.assertEqual(self.query("SELECT count(*) FROM tags")[0][0], 0)
        self.assertEqual(
            self.query("SELECT count(*) FROM household_transaction_budgets")[0][0], 0
        )

    def test_unmatched_manifest_is_rejected(self) -> None:
        value = json.loads(self.manifest.read_text())
        value["reconciliation"]["matched"] = False
        self.manifest.write_text(json.dumps(value))
        with self.assertRaises(fin.FinanceFailure):
            fin.run_load(self.args())


class PipelineTests(unittest.TestCase):
    """Stage a file and load its real output, with no hand-written staging fixtures."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "statement.pdf"
        self.source.write_bytes(b"private statement")
        self.staging = self.root / "staging.jsonl"
        self.ledger = self.root / "ledger.sqlite"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def extraction(self, run_id: str) -> dict:
        return {
            "schema_version": fin.EXTRACTION_SCHEMA,
            "model": "test-model",
            "run_id": run_id,
            "source_sha256": fin.sha256_file(self.source),
            "total_pages": 1,
            "reviewed_pages": [1],
            "transaction_count": 2,
            "complete": True,
            "uncertainties": [],
            "transactions": [
                {
                    "transaction_date": "2026-08-01", "posted_date": None,
                    "description": "CAFE", "amount_minor": -1234, "currency": "USD",
                    "source_page": 1, "source_index": 1, "status": "posted",
                },
                {
                    "transaction_date": "2026-08-02", "posted_date": None,
                    "description": "PAYROLL", "amount_minor": 500000, "currency": "USD",
                    "source_page": 1, "source_index": 2, "status": "posted",
                },
            ],
        }

    def test_stage_then_load_posts_a_balanced_ledger(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        first.write_text(json.dumps(self.extraction("run-a")))
        second.write_text(json.dumps(self.extraction("run-b")))
        self.assertEqual(fin.run_stage(Namespace(
            source=str(self.source), extraction=str(first), verification=str(second),
            output=str(self.staging), account_key=ACCOUNT_KEY,
        )), 0)
        self.assertEqual(fin.run_load(Namespace(
            source=str(self.source), staging=str(self.staging),
            manifest=str(self.staging) + ".manifest.json", ledger=str(self.ledger),
            schema=str(REFERENCES / "schema.sql"), extensions=None,
            household_id="household-local", timezone="America/New_York", base_currency="USD",
            account_key=ACCOUNT_KEY, account_type="asset", account_name="Checking",
        )), 0)
        with sqlite3.connect(self.ledger) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM transactions WHERE status='posted'").fetchone()[0], 2
            )
            self.assertEqual(conn.execute("SELECT sum(base_amount_minor) FROM postings").fetchone()[0], 0)
            self.assertEqual(
                conn.execute(
                    "SELECT max(ledger_running_balance_minor) FROM household_account_register"
                ).fetchone()[0],
                500000 - 1234,
            )


if __name__ == "__main__":
    unittest.main()
