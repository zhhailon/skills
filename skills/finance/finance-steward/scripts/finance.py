#!/usr/bin/env python3
"""Finance Steward pipeline: stage two fresh-context LLM extractions, then load them.

Two subcommands, one acceptance gate between them:

  stage  reconcile two independent LLM extractions of one source file into
         staging JSONL plus a manifest. Exits non-zero unless status=staged.
  load   verify an accepted manifest and write it into the canonical SQLite
         ledger. Refuses any manifest that is not status=staged.

Neither subcommand parses documents or calls a model.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import mimetypes
import re
import sqlite3
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


class FinanceFailure(Exception):
    """A failure safe to report without dumping financial records."""


# --- shared helpers ------------------------------------------------------


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
        raise FinanceFailure(f"{label} is not readable valid JSON") from error
    if not isinstance(value, dict):
        raise FinanceFailure(f"{label} root must be an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise FinanceFailure("staging JSONL contains a non-object record")
                records.append(value)
    except (OSError, json.JSONDecodeError) as error:
        raise FinanceFailure("staging JSONL is not readable valid JSONL") from error
    if not records:
        raise FinanceFailure("staging JSONL contains no records")
    return records


# --- stage ---------------------------------------------------------------


def validate_extraction(value: dict[str, Any], source_sha256: str, label: str) -> list[dict[str, Any]]:
    unknown = set(value) - ALLOWED_ROOT_FIELDS
    if unknown:
        raise FinanceFailure(f"{label} contains fields outside the extraction schema")
    if value.get("schema_version") != EXTRACTION_SCHEMA:
        raise FinanceFailure(f"{label} schema version is unsupported")
    if not normalize_text(value.get("model")) or not normalize_text(value.get("run_id")):
        raise FinanceFailure(f"{label} model and run_id are required")
    if value.get("source_sha256") != source_sha256:
        raise FinanceFailure(f"{label} source hash does not match")
    if value.get("complete") is not True:
        raise FinanceFailure(f"{label} is incomplete")
    total_pages = value.get("total_pages")
    reviewed_pages = value.get("reviewed_pages")
    if not isinstance(total_pages, int) or isinstance(total_pages, bool) or total_pages < 1:
        raise FinanceFailure(f"{label} total_pages is invalid")
    if reviewed_pages != list(range(1, total_pages + 1)):
        raise FinanceFailure(f"{label} did not review every page exactly once")
    if not isinstance(value.get("uncertainties"), list):
        raise FinanceFailure(f"{label} uncertainties must be an array")
    transactions = value.get("transactions")
    if not isinstance(transactions, list):
        raise FinanceFailure(f"{label} transactions must be an array")
    if value.get("transaction_count") != len(transactions):
        raise FinanceFailure(f"{label} transaction count does not match array length")

    normalized: list[dict[str, Any]] = []
    for index, transaction in enumerate(transactions, start=1):
        if not isinstance(transaction, dict) or set(transaction) - ALLOWED_TRANSACTION_FIELDS:
            raise FinanceFailure(f"{label} transaction {index} contains fields outside the extraction schema")
        date = transaction.get("transaction_date")
        try:
            dt.date.fromisoformat(date)
        except (TypeError, ValueError) as error:
            raise FinanceFailure(f"{label} transaction {index} date is invalid") from error
        posted_date = transaction.get("posted_date")
        if posted_date is not None:
            try:
                dt.date.fromisoformat(posted_date)
            except (TypeError, ValueError) as error:
                raise FinanceFailure(f"{label} transaction {index} posted_date is invalid") from error
        description = normalize_text(transaction.get("description"))
        if not description:
            raise FinanceFailure(f"{label} transaction {index} description is empty")
        amount_minor = transaction.get("amount_minor")
        if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor == 0:
            raise FinanceFailure(f"{label} transaction {index} amount_minor is invalid")
        currency = normalize_text(transaction.get("currency")).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise FinanceFailure(f"{label} transaction {index} currency is invalid")
        source_page = transaction.get("source_page")
        if not isinstance(source_page, int) or isinstance(source_page, bool) or not 1 <= source_page <= total_pages:
            raise FinanceFailure(f"{label} transaction {index} source_page is invalid")
        source_index = transaction.get("source_index", index)
        if not isinstance(source_index, int) or isinstance(source_index, bool) or source_index < 1:
            raise FinanceFailure(f"{label} transaction {index} source_index is invalid")
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


def run_stage(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    first_path = Path(args.extraction).expanduser().resolve()
    verification_path = Path(args.verification).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise FinanceFailure("source file does not exist")
    source_hash = sha256_file(source)
    first_object = load_object(first_path, "extraction")
    verification_object = load_object(verification_path, "verification")
    if first_object.get("run_id") == verification_object.get("run_id"):
        raise FinanceFailure("verification must use a fresh run_id")
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


# --- load ----------------------------------------------------------------


def initialize(
    conn: sqlite3.Connection,
    schema_path: Path,
    extensions_path: Path | None,
    household_id: str,
    timezone: str,
    base_currency: str,
) -> str:
    """Apply the schema if absent, ensure the household row, return its base currency."""
    has_schema = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    if not has_schema:
        try:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
        except (OSError, sqlite3.Error) as error:
            raise FinanceFailure("canonical schema could not be initialized") from error
    if extensions_path is not None:
        has_extensions = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tags'"
        ).fetchone()
        if not has_extensions:
            try:
                conn.executescript(extensions_path.read_text(encoding="utf-8"))
            except (OSError, sqlite3.Error) as error:
                raise FinanceFailure("schema extensions could not be initialized") from error
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO currencies(code, name, minor_units) VALUES(?, ?, 2)",
        (base_currency, base_currency),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO households(id, name, base_currency_code, timezone, created_at)
        VALUES(?, 'Local Household', ?, ?, ?)
        """,
        (household_id, base_currency, timezone, now),
    )
    row = conn.execute(
        "SELECT base_currency_code FROM households WHERE id=?", (household_id,)
    ).fetchone()
    if not row:
        raise FinanceFailure("household row could not be established")
    if str(row[0]) != base_currency:
        raise FinanceFailure(
            f"household base currency is {row[0]}, not {base_currency}"
        )
    return str(row[0])


def ensure_account(
    conn: sqlite3.Connection,
    account_id: str,
    household_id: str,
    name: str,
    account_type: str,
    currency_code: str | None,
    created_at: str,
) -> str:
    conn.execute(
        """
        INSERT OR IGNORE INTO accounts
          (id, household_id, name, account_type, currency_code, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (account_id, household_id, name, account_type, currency_code, created_at),
    )
    # An existing account wins the insert, so a contradicting type would otherwise be
    # dropped in silence and flip the sign convention for every later import.
    existing = conn.execute(
        "SELECT account_type, currency_code FROM accounts WHERE id=?", (account_id,)
    ).fetchone()
    if not existing:
        raise FinanceFailure("account row could not be established")
    if existing[0] != account_type:
        raise FinanceFailure(
            f"account already exists as '{existing[0]}', not '{account_type}'"
        )
    if currency_code is not None and existing[1] != currency_code:
        raise FinanceFailure(
            f"account already exists in {existing[1]}, not {currency_code}"
        )
    return account_id


def validate_staging(
    source: Path, staging: Path, manifest: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[str, str]:
    source_hash = sha256_file(source)
    staging_hash = sha256_file(staging)
    if manifest.get("status") != "staged":
        raise FinanceFailure("staging manifest is not accepted")
    if manifest.get("source_sha256") != source_hash:
        raise FinanceFailure("source hash does not match staging manifest")
    if manifest.get("output_sha256") != staging_hash:
        raise FinanceFailure("staging hash does not match manifest")
    if manifest.get("record_count") != len(records):
        raise FinanceFailure("staging record count does not match manifest")
    if not manifest.get("reconciliation", {}).get("matched"):
        raise FinanceFailure("staging reconciliation is not matched")
    if manifest.get("uncertainty_count") != 0:
        raise FinanceFailure("staging has unresolved uncertainties")
    if manifest.get("duplicate_dedupe_key_count") != 0:
        raise FinanceFailure("staging has unresolved duplicate keys")
    for index, record in enumerate(records, start=1):
        if record.get("schema_version") != STAGING_SCHEMA:
            raise FinanceFailure(f"staging record {index} schema is unsupported")
        if record.get("source_sha256") != source_hash:
            raise FinanceFailure(f"staging record {index} source hash does not match")
    return source_hash, staging_hash


def run_load(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    staging = Path(args.staging).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    ledger = Path(args.ledger).expanduser().resolve()
    schema = Path(args.schema).expanduser().resolve()
    extensions = Path(args.extensions).expanduser().resolve() if args.extensions else None
    if not source.is_file() or not staging.is_file() or not manifest_path.is_file() or not schema.is_file():
        raise FinanceFailure("source, staging, manifest, or schema file is missing")
    if extensions is not None and not extensions.is_file():
        raise FinanceFailure("schema extensions file is missing")
    if bool(args.account_key) != bool(args.account_type):
        raise FinanceFailure("posting requires both --account-key and --account-type")
    manifest = load_object(manifest_path, "staging manifest")
    records = load_jsonl(staging)
    source_hash, staging_hash = validate_staging(source, staging, manifest, records)
    account_hash = None
    if args.account_key:
        account_hash = sha256_bytes(args.account_key.encode())
        expected = manifest.get("account_key_hash")
        if expected is not None and expected != account_hash:
            raise FinanceFailure("account key does not match the staging manifest")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    source_id = f"source-{source_hash}"
    batch_id = f"batch-{staging_hash}"
    validation_id = f"validation-{staging_hash}"
    inserted_transactions = 0
    existing_transactions = 0
    inserted_records = 0
    posted_transactions = 0
    already_posted_transactions = 0
    unposted_foreign_currency = 0

    conn = sqlite3.connect(ledger)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            base_currency = initialize(
                conn, schema, extensions, args.household_id, args.timezone, args.base_currency
            )
            for currency in sorted({str(record["currency"]) for record in records}):
                conn.execute(
                    "INSERT OR IGNORE INTO currencies(code, name, minor_units) VALUES(?, ?, 2)",
                    (currency, currency),
                )
            statement_account_id = None
            expense_account_id = None
            income_account_id = None
            if account_hash is not None:
                statement_account_id = ensure_account(
                    conn, f"account-{account_hash}", args.household_id,
                    args.account_name or f"Account {account_hash[:12]}",
                    args.account_type, base_currency, now,
                )
                expense_account_id = ensure_account(
                    conn, "account-uncategorized-expense", args.household_id,
                    "Uncategorized Expense", "expense", None, now,
                )
                income_account_id = ensure_account(
                    conn, "account-uncategorized-income", args.household_id,
                    "Uncategorized Income", "income", None, now,
                )
            conn.execute(
                """
                INSERT INTO source_files
                  (id, household_id, sha256, original_name, media_type, byte_size, stored_path, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(household_id, sha256) DO UPDATE SET
                  stored_path=excluded.stored_path,
                  byte_size=excluded.byte_size
                """,
                (
                    source_id, args.household_id, source_hash, source.name,
                    mimetypes.guess_type(source.name)[0], source.stat().st_size, str(source), now,
                ),
            )
            conn.execute(
                """
                INSERT INTO import_batches
                  (id, household_id, source_file_id, importer_name, importer_version, status, started_at, summary_json)
                VALUES (?, ?, ?, 'finance-steward', 'llm-v1', 'running', ?, '{}')
                ON CONFLICT(id) DO UPDATE SET status='running', completed_at=NULL
                """,
                (batch_id, args.household_id, source_id, now),
            )
            for record in records:
                record_id = f"record-{record['record_hash']}"
                before = conn.total_changes
                conn.execute(
                    """
                    INSERT OR IGNORE INTO import_records
                      (id, import_batch_id, source_file_id, source_locator, record_hash,
                       parsed_date, parsed_amount_minor, parsed_currency_code, parsed_description,
                       sanitized_description, raw_payload_path, parse_status, error_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'parsed', NULL)
                    """,
                    (
                        record_id, batch_id, source_id, record["source_locator"], record["record_hash"],
                        record["transaction_date"], record["amount_minor"], record["currency"],
                        record["description"], record["description"],
                    ),
                )
                inserted_records += int(conn.total_changes > before)
                transaction_id = f"transaction-{record['dedupe_key']}"
                before = conn.total_changes
                conn.execute(
                    """
                    INSERT OR IGNORE INTO transactions
                      (id, household_id, transaction_date, posted_date, description, status,
                       dedupe_key, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'draft', ?, NULL, ?, ?)
                    """,
                    (
                        transaction_id, args.household_id, record["transaction_date"],
                        record.get("posted_date"), record["description"], record["dedupe_key"], now, now,
                    ),
                )
                transaction_inserted = conn.total_changes > before
                if transaction_inserted:
                    inserted_transactions += 1
                else:
                    existing_transactions += 1
                    row = conn.execute(
                        "SELECT id FROM transactions WHERE household_id=? AND dedupe_key=?",
                        (args.household_id, record["dedupe_key"]),
                    ).fetchone()
                    if row:
                        transaction_id = str(row[0])
                conn.execute(
                    """
                    INSERT OR IGNORE INTO transaction_sources(transaction_id, import_record_id, relationship)
                    VALUES (?, ?, ?)
                    """,
                    (transaction_id, record_id, "primary" if transaction_inserted else "corroborates"),
                )
                if statement_account_id is None:
                    continue
                if record["currency"] != base_currency:
                    # No exchange-rate source is defined, so base_amount_minor cannot be
                    # derived honestly. Leave the transaction as a draft for the owner.
                    unposted_foreign_currency += 1
                    continue
                current_status = conn.execute(
                    "SELECT status FROM transactions WHERE id=?", (transaction_id,)
                ).fetchone()
                if not current_status or current_status[0] != "draft":
                    if current_status and current_status[0] == "posted":
                        already_posted_transactions += 1
                    continue
                amount = int(record["amount_minor"])
                category_account_id = expense_account_id if amount < 0 else income_account_id
                for suffix, account_id, leg_amount in (
                    ("a", statement_account_id, amount),
                    ("b", category_account_id, -amount),
                ):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO postings
                          (id, transaction_id, account_id, amount_minor, currency_code,
                           base_amount_minor, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"posting-{record['dedupe_key']}-{suffix}", transaction_id, account_id,
                            leg_amount, base_currency, leg_amount, now,
                        ),
                    )
                # The post_transaction_requires_balance trigger aborts the whole load
                # if these two legs are missing or do not sum to zero.
                conn.execute(
                    "UPDATE transactions SET status='posted', updated_at=? WHERE id=?",
                    (now, transaction_id),
                )
                posted_transactions += 1
            details = {
                "verification_mode": manifest.get("verification_mode"),
                "missing_count": manifest.get("reconciliation", {}).get("missing_count"),
                "extra_count": manifest.get("reconciliation", {}).get("extra_count"),
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO validation_runs
                  (id, import_batch_id, source_file_id, validator_kind, validator_name,
                   validator_version, sanitized_input_sha256, parser_count, validator_count,
                   difference_count, status, details_json, created_at)
                VALUES (?, ?, ?, 'model', ?, 'fresh-context-v1', ?, ?, ?, 0, 'matched', ?, ?)
                """,
                (
                    validation_id, batch_id, source_id, manifest.get("verification_mode", "model"),
                    staging_hash, len(records), len(records), json.dumps(details, sort_keys=True), now,
                ),
            )
            summary = {
                "record_count": len(records),
                "inserted_transactions": inserted_transactions,
                "existing_transactions": existing_transactions,
                "posted_transactions": posted_transactions,
                "already_posted_transactions": already_posted_transactions,
                "unposted_foreign_currency": unposted_foreign_currency,
            }
            conn.execute(
                "UPDATE import_batches SET status='committed', completed_at=?, summary_json=? WHERE id=?",
                (now, json.dumps(summary, sort_keys=True), batch_id),
            )
    except sqlite3.Error as error:
        raise FinanceFailure("canonical ledger load failed") from error
    finally:
        conn.close()
    safe_json({
        "record_count": len(records), "inserted_records": inserted_records,
        "inserted_transactions": inserted_transactions, "existing_transactions": existing_transactions,
        "posted_transactions": posted_transactions,
        "already_posted_transactions": already_posted_transactions,
        "unposted_foreign_currency": unposted_foreign_currency,
        "status": "committed",
    })
    return 0


# --- entry point ---------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage = subparsers.add_parser("stage", help="reconcile and stage two fresh-context LLM extractions")
    stage.add_argument("source")
    stage.add_argument("--extraction", required=True)
    stage.add_argument("--verification", required=True)
    stage.add_argument("--output", required=True)
    stage.add_argument("--account-key", default="unspecified")
    stage.set_defaults(handler=run_stage)

    load = subparsers.add_parser("load", help="load accepted staging into the canonical SQLite ledger")
    load.add_argument("--source", required=True)
    load.add_argument("--staging", required=True)
    load.add_argument("--manifest", required=True)
    load.add_argument("--ledger", required=True)
    load.add_argument("--schema", required=True)
    load.add_argument("--extensions", help="optional schema-extensions.sql to apply alongside the core schema")
    load.add_argument("--household-id", default="household-local")
    load.add_argument("--timezone", default="America/New_York")
    load.add_argument("--base-currency", default="USD")
    load.add_argument(
        "--account-key",
        help="stable opaque account key; with --account-type, posts balanced double-entry",
    )
    load.add_argument(
        "--account-type", choices=("asset", "liability"),
        help="ledger type of the statement account; required with --account-key",
    )
    load.add_argument("--account-name", help="display name for the statement account")
    load.set_defaults(handler=run_load)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except FinanceFailure as error:
        safe_json({"status": "failed", "error": str(error)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
