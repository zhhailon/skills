#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import finance_stage as fs


class FinanceStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "statement.pdf"
        self.source.write_bytes(b"private statement")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def extraction(self, run_id: str, *, amount: int = -1234, model: str = "openclaw-auto") -> dict:
        return {
            "schema_version": fs.EXTRACTION_SCHEMA,
            "model": model,
            "run_id": run_id,
            "source_sha256": fs.sha256_file(self.source),
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

    def run_stage(self, first: dict, second: dict) -> tuple[int, dict]:
        first_path = self.root / "first.json"
        second_path = self.root / "second.json"
        output = self.root / "staging.jsonl"
        first_path.write_text(json.dumps(first))
        second_path.write_text(json.dumps(second))
        code = fs.run(Namespace(
            source=str(self.source), extraction=str(first_path), verification=str(second_path),
            output=str(output), account_key="test-account",
        ))
        return code, json.loads(output.with_suffix(".jsonl.manifest.json").read_text())

    def test_same_model_fresh_context_can_stage(self) -> None:
        code, manifest = self.run_stage(self.extraction("run-a"), self.extraction("run-b"))
        self.assertEqual(code, 0)
        self.assertEqual(manifest["verification_mode"], "same_model_fresh_context")
        record = json.loads((self.root / "staging.jsonl").read_text())
        self.assertEqual(record["description"], "CAFE [masked-id]")

    def test_different_results_need_review(self) -> None:
        code, manifest = self.run_stage(self.extraction("run-a"), self.extraction("run-b", amount=-999))
        self.assertEqual(code, 2)
        self.assertEqual(manifest["status"], "needs_review")
        self.assertEqual(manifest["reconciliation"]["missing_count"], 1)

    def test_forbidden_fields_fail(self) -> None:
        first = self.extraction("run-a")
        first["transactions"][0]["balance"] = "private"
        with self.assertRaises(fs.StageFailure):
            self.run_stage(first, self.extraction("run-b"))


if __name__ == "__main__":
    unittest.main()
