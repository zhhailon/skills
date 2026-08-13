#!/usr/bin/env python3
"""Validate and stage two fresh-context LLM transaction extractions."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


EXTRACTION_SCHEMA = "finance-steward-llm-extraction-v1"
STAGING_SCHEMA = "finance-steward-import-v1"
ALLOWED_ROOT_FIELDS = {
    "schema_version", "model", "run_id", "source_sha256", "total_pages",
    "reviewed_pages", "transaction_count", "complete", "uncertainties",
    "transactions",
}
ALLOWED_TRANSACTION_FIELDS = {
    "transaction_date", "posted_date", "description", "amount_minor",
    "currency", "source_page", "source_index", "status",
}


class StageFailure(Exception):
    """A staging failure safe to report without dumping source contents."""


def safe_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def canonical_description(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).upper()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text)).strip()


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StageFailure(f"{label} is not readable valid JSON") from error
    if not isinstance(value, dict):
        raise StageFailure(f"{label} root must be an object")
    return value


def validate_extraction(value: dict[str, Any], source_sha256: str, label: str) -> list[dict[str, Any]]:
    unknown = set(value) - ALLOWED_ROOT_FIELDS
    if unknown:
        raise StageFailure(f"{label} contains fields outside the extraction schema")
    if value.get("schema_version") != EXTRACTION_SCHEMA:
        raise StageFailure(f"{label} schema version is unsupported")
    if not normalize_text(value.get("model")) or not normalize_text(value.get("run_id")):
        raise StageFailure(f"{label} model and run_id are required")
    if value.get("source_sha256") != source_sha256:
        raise StageFailure(f"{label} source hash does not match")
    if value.get("complete") is not True:
        raise StageFailure(f"{label} is incomplete")
    total_pages = value.get("total_pages")
    reviewed_pages = value.get("reviewed_pages")
    if not isinstance(total_pages, int) or isinstance(total_pages, bool) or total_pages < 1:
        raise StageFailure(f"{label} total_pages is invalid")
    if reviewed_pages != list(range(1, total_pages + 1)):
        raise StageFailure(f"{label} did not review every page exactly once")
    if not isinstance(value.get("uncertainties"), list):
        raise StageFailure(f"{label} uncertainties must be an array")
    transactions = value.get("transactions")
    if not isinstance(transactions, list):
        raise StageFailure(f"{label} transactions must be an array")
    if value.get("transaction_count") != len(transactions):
        raise StageFailure(f"{label} transaction count does not match array length")

    normalized: list[dict[str, Any]] = []
    for index, transaction in enumerate(transactions, start=1):
        if not isinstance(transaction, dict) or set(transaction) - ALLOWED_TRANSACTION_FIELDS:
            raise StageFailure(f"{label} transaction {index} contains fields outside the extraction schema")
        date = transaction.get("transaction_date")
        try:
            dt.date.fromisoformat(date)
        except (TypeError, ValueError) as error:
            raise StageFailure(f"{label} transaction {index} date is invalid") from error
        posted_date = transaction.get("posted_date")
        if posted_date is not None:
            try:
                dt.date.fromisoformat(posted_date)
            except (TypeError, ValueError) as error:
                raise StageFailure(f"{label} transaction {index} posted_date is invalid") from error
        description = normalize_text(transaction.get("description"))
        if not description:
            raise StageFailure(f"{label} transaction {index} description is empty")
        amount_minor = transaction.get("amount_minor")
        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor == 0:
            raise StageFailure(f"{label} transaction {index} amount_minor is invalid")
        currency = normalize_text(transaction.get("currency")).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise StageFailure(f"{label} transaction {index} currency is invalid")
        source_page = transaction.get("source_page")
        if not isinstance(source_page, int) or isinstance(source_page, bool) or not 1 <= source_page <= total_pages:
            raise StageFailure(f"{label} transaction {index} source_page is invalid")
        source_index = transaction.get("source_index", index)
        if not isinstance(source_index, int) or isinstance(source_index, bool) or source_index < 1:
            raise StageFailure(f"{label} transaction {index} source_index is invalid")
        normalized.append({
            "transaction_date": date,
            "posted_date": posted_date,
            "description": description,
            "amount_minor": amount_minor,
            "currency": currency,
            "source_page": source_page,
            "source_index": source_index,
            "status": normalize_text(transaction.get("status")).lower() or None,
        })
    return normalized


def match_key(record: dict[str, Any]) -> tuple[str, int, str, str]:
    return (
        record["transaction_date"], record["amount_minor"], record["currency"],
        canonical_description(record["description"]),
    )


def compare(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> dict[str, int | bool]:
    left = collections.Counter(match_key(record) for record in first)
    right = collections.Counter(match_key(record) for record in second)
    missing = sum((left - right).values())
    extra = sum((right - left).values())
    return {
        "first_count": len(first),
        "verification_count": len(second),
        "missing_count": missing,
        "extra_count": extra,
        "matched": not missing and not extra,
    }


def staged_records(records: list[dict[str, Any]], source_sha256: str, account_key: str) -> list[dict[str, Any]]:
    staged = []
    for record in records:
        canonical = "|".join([
            account_key, record["transaction_date"], str(record["amount_minor"]),
            record["currency"], canonical_description(record["description"]),
        ])
        locator = f"page:{record['source_page']}:item:{record['source_index']}"
        staged.append({
            "schema_version": STAGING_SCHEMA,
            "source_sha256": source_sha256,
            "source_locator": locator,
            "transaction_date": record["transaction_date"],
            "posted_date": record["posted_date"],
            "description": record["description"],
            "amount_minor": record["amount_minor"],
            "currency": record["currency"],
            "balance_minor": None,
            "external_id": None,
            "status": record["status"],
            "record_hash": sha256_bytes(f"{source_sha256}|{locator}|{canonical}".encode()),
            "dedupe_key": sha256_bytes(canonical.encode()),
        })
    return staged


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)
    return sha256_file(path)


def run(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    first_path = Path(args.extraction).expanduser().resolve()
    verification_path = Path(args.verification).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise StageFailure("source file does not exist")
    source_hash = sha256_file(source)
    first_object = load_object(first_path, "extraction")
    verification_object = load_object(verification_path, "verification")
    if first_object.get("run_id") == verification_object.get("run_id"):
        raise StageFailure("verification must use a fresh run_id")
    first_model = normalize_text(first_object.get("model"))
    verification_model = normalize_text(verification_object.get("model"))
    verification_mode = "cross_model" if first_model != verification_model else "same_model_fresh_context"
    first = validate_extraction(first_object, source_hash, "extraction")
    verification = validate_extraction(verification_object, source_hash, "verification")
    reconciliation = compare(first, verification)
    uncertainties = len(first_object["uncertainties"]) + len(verification_object["uncertainties"])
    status = "staged" if reconciliation["matched"] and not uncertainties else "needs_review"
    records = staged_records(first, source_hash, args.account_key)
    duplicate_count = sum(count > 1 for count in collections.Counter(record["dedupe_key"] for record in records).values())
    if duplicate_count:
        status = "needs_review"
    output_hash = write_jsonl(output, records)
    manifest = {
        "schema_version": STAGING_SCHEMA,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_sha256": source_hash,
        "extraction_method": "llm",
        "extraction_model": first_model,
        "verification_model": verification_model,
        "verification_mode": verification_mode,
        "reconciliation": reconciliation,
        "uncertainty_count": uncertainties,
        "duplicate_dedupe_key_count": duplicate_count,
        "record_count": len(records),
        "account_key_hash": sha256_bytes(args.account_key.encode()),
        "output_sha256": output_hash,
        "status": status,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    safe_json({
        "record_count": len(records), "verification_mode": verification_mode,
        "missing_count": reconciliation["missing_count"], "extra_count": reconciliation["extra_count"],
        "uncertainty_count": uncertainties, "duplicate_dedupe_key_count": duplicate_count,
        "status": status,
    })
    return 0 if status == "staged" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile and stage two fresh-context LLM transaction extractions.")
    parser.add_argument("source")
    parser.add_argument("--extraction", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--account-key", default="unspecified")
    return parser


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except StageFailure as error:
        safe_json({"status": "failed", "error": str(error)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
