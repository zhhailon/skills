#!/usr/bin/env python3
"""Self-tests for the standard-library finance importer."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path

import finance_import as fi


def common_args(path: Path, output: Path, **overrides: object) -> Namespace:
    values = {
        "path": str(path), "output": str(output), "format": "auto", "profile": None,
        "account_key": "test-account", "currency": "USD", "minor_units": 2,
        "sign_mode": "as-is", "statement_end": None, "delimiter": None, "encoding": None,
    }
    values.update(overrides)
    return Namespace(**values)


class ImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def stage(self, name: str, content: str, **overrides: object) -> list[dict]:
        source = self.root / name
        source.write_text(content, encoding="utf-8")
        output = self.root / f"{name}.jsonl"
        code = fi.command_stage(common_args(source, output, **overrides))
        self.assertEqual(code, 0)
        return fi.read_jsonl(output)

    def test_csv_debit_credit_and_identifier_masking(self) -> None:
        records = self.stage(
            "transactions.csv",
            "Transaction Date,Description,Debit,Credit,Balance,Reference\n"
            "08/01/2026,CAFE 123456789,12.34,,100.00,R1\n"
            "08/02/2026,PAYROLL,,500.00,600.00,R2\n",
        )
        self.assertEqual([row["amount_minor"] for row in records], [-1234, 50000])
        self.assertEqual(records[0]["description"], "CAFE [masked-id]")
        self.assertEqual(fi.validate_records(records)["status"], "valid")

    def test_credit_card_sign_inversion(self) -> None:
        records = self.stage("card.csv", "Date,Description,Amount\n2026-08-01,MEAL,25.00\n", sign_mode="invert")
        self.assertEqual(records[0]["amount_minor"], -2500)

    def test_ofx_and_fitid(self) -> None:
        records = self.stage(
            "bank.ofx",
            "OFXHEADER:100\n<OFX><CURDEF>USD<BANKTRANLIST><STMTTRN>"
            "<DTPOSTED>20260801120000<TRNAMT>-42.50<FITID>abc123<NAME>SHOP"
            "</STMTTRN></BANKTRANLIST></OFX>",
        )
        self.assertEqual(records[0]["transaction_date"], "2026-08-01")
        self.assertEqual(records[0]["amount_minor"], -4250)
        self.assertEqual(records[0]["external_id"], "abc123")

    def test_qif(self) -> None:
        records = self.stage("bank.qif", "!Type:Bank\nD08/01/2026\nT-9.99\nPCafe\nN7\n^\n")
        self.assertEqual(records[0]["amount_minor"], -999)
        self.assertEqual(records[0]["description"], "Cafe")

    def test_xlsx_without_openpyxl(self) -> None:
        source = self.root / "bank.xlsx"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>"
                "<row r='1'><c r='A1' t='inlineStr'><is><t>Date</t></is></c><c r='B1' t='inlineStr'><is><t>Description</t></is></c><c r='C1' t='inlineStr'><is><t>Amount</t></is></c></row>"
                "<row r='2'><c r='A2' t='inlineStr'><is><t>2026-08-01</t></is></c><c r='B2' t='inlineStr'><is><t>Store</t></is></c><c r='C2'><v>-12.34</v></c></row>"
                "</sheetData></worksheet>",
            )
        output = self.root / "xlsx.jsonl"
        self.assertEqual(fi.command_stage(common_args(source, output)), 0)
        self.assertEqual(fi.read_jsonl(output)[0]["amount_minor"], -1234)

    def test_profiled_text_partial_date(self) -> None:
        profile = self.root / "profile.json"
        profile.write_text(json.dumps({
            "name": "test", "currency": "USD", "sign_mode": "invert",
            "line_pattern": r"^(?P<date>\d{2}/\d{2}) (?P<description>.+?) (?P<amount>-?\d+\.\d{2})$",
        }))
        records = self.stage(
            "statement.txt", "07/31 SHOP 10.00\n08/01 PAYMENT -5.00\n",
            profile=str(profile), statement_end="2026-08-04",
        )
        self.assertEqual([(row["transaction_date"], row["amount_minor"]) for row in records], [
            ("2026-07-31", -1000), ("2026-08-01", 500),
        ])

    def test_minimal_pdf_text_layer(self) -> None:
        source = self.root / "statement.pdf"
        stream = b"BT 1 0 0 1 10 700 Tm (08/01 SHOP 10.00) Tj ET"
        source.write_bytes(b"%PDF-1.4\n1 0 obj << /Length 48 >> stream\n" + stream + b"\nendstream\nendobj\n%%EOF")
        text, metadata = fi.extract_pdf_text(source)
        self.assertIn("08/01 SHOP 10.00", text)
        self.assertEqual(metadata["extractor"], "bundled-pdf-text-v1")


if __name__ == "__main__":
    unittest.main()
