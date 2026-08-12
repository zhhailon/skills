# Portable Import Contract

## Purpose

Use `scripts/finance_import.py` to convert one downloaded bank file into deterministic JSONL staging records. The script uses only the Python standard library. It does not call a bank, model, database, OpenClaw command, office suite, OCR binary, PDF utility, or network service.

## Commands

Inspect without printing transaction contents:

```bash
uv run python scripts/finance_import.py inspect statement.csv
```

Stage one file:

```bash
uv run python scripts/finance_import.py stage statement.csv \
  --output private-staging/statement.jsonl \
  --account-key checking-main
```

Validate an existing staging file:

```bash
uv run python scripts/finance_import.py validate private-staging/statement.jsonl
```

The CLI prints only counts, hashes, status, and local output paths. Transaction details remain in the private JSONL file.

## Supported Inputs

- CSV and TSV: detect common date, description, amount, debit, credit, balance, currency, status, and ID headers.
- XLSX: read the first worksheet directly from OOXML without `openpyxl`.
- OFX, QFX, and QBO: read `STMTTRN` records and preserve `FITID`.
- QIF: read date, amount, payee, memo, and transaction number.
- Text-layer PDF: use the bundled minimal PDF extractor plus a JSON line profile.
- Extracted text: use the same JSON line profile when PDF extraction is unavailable.

Binary XLS, encrypted PDFs, scanned image-only PDFs, and PDFs with undecodable custom font mappings are not deterministically supported. Return `failed` or `needs_review`; never infer missing rows.

## JSONL Record

Each line is one object:

```json
{
  "schema_version": "finance-steward-import-v1",
  "source_sha256": "...",
  "source_locator": "row:2",
  "transaction_date": "2026-08-01",
  "posted_date": null,
  "description": "SANITIZED MERCHANT",
  "amount_minor": -1234,
  "currency": "USD",
  "balance_minor": null,
  "external_id": null,
  "status": null,
  "record_hash": "...",
  "dedupe_key": "..."
}
```

Interpret `amount_minor` as movement in the selected bank account: positive increases its signed ledger balance and negative decreases it. For assets, deposits are normally positive and withdrawals negative. For liabilities, purchases increase liability and therefore are negative under the canonical ledger convention. Use `--sign-mode invert` when a credit-card export reports purchases as positive amounts.

Use a stable opaque `--account-key`. It participates in `dedupe_key` but is emitted only as a hash in the manifest. Use a separate downstream account mapping when creating ledger postings.

## Column Profiles

Use a profile when a delimited or XLSX export has unfamiliar headers:

```json
{
  "name": "bank-transactions-v1",
  "currency": "USD",
  "sign_mode": "as-is",
  "date_formats": ["%m/%d/%Y"],
  "columns": {
    "date": ["Effective Date"],
    "description": ["Narrative"],
    "debit": ["Money Out"],
    "credit": ["Money In"],
    "external_id": ["Bank Reference"]
  }
}
```

Valid column keys are `date`, `posted_date`, `description`, `amount`, `debit`, `credit`, `balance`, `currency`, `external_id`, and `status`.

## PDF and Text Profiles

Provide `line_pattern` with named capture groups. Supported groups are `date`, or `month` plus `day`, `posted_date`, `description`, `amount`, `debit`, `credit`, `balance`, `currency`, and `external_id`.

```json
{
  "name": "card-statement-v1",
  "currency": "USD",
  "sign_mode": "invert",
  "line_pattern": "^\\s*(?P<date>\\d{1,2}/\\d{1,2})\\s+(?P<description>.+?)\\s+\\$?(?P<amount>-?[0-9,]+\\.\\d{2})\\s*$"
}
```

When dates omit a year, pass the verified statement closing date:

```bash
uv run python scripts/finance_import.py stage statement.pdf \
  --profile assets/import-profiles/chase-card-layout.json \
  --statement-end 2026-08-04 \
  --account-key card-main \
  --output private-staging/statement.jsonl
```

Use `section_markers` when debit and credit tables print unsigned amounts. Each marker contains a regex `pattern` and `sign_mode` of `as-is` or `invert`. Treat bundled bank profiles as starting points: verify them against a locally inspected statement before accepting a new institution/layout version.

## Acceptance Gates

Accept a staged file only when:

1. the command returns `status=staged`;
2. `validate` returns `status=valid`;
3. the record count matches the source transaction count or a verified statement count;
4. the account sign convention has been checked with at least one known debit and credit;
5. no duplicate dedupe key remains unresolved;
6. for PDF, the profile version and statement layout were reviewed locally.

If an agent performs a second-pass review, expose only `transaction_date`, sanitized `description`, `amount_minor`, and `currency`. Model review is optional and provider-neutral; it is never a runtime dependency of the importer.
