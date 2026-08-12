---
name: finance-steward
description: Independently ingest, validate, organize, query, and analyze private household financial records across agents. Use for downloaded bank or credit-card statements, CSV/TSV/XLSX transaction exports, OFX/QFX/QBO/QIF files, text-layer PDFs, receipts, spending summaries, reconciliation, categorization, and duplicate-safe batches. Use the bundled standard-library importer and portable staging contract; require no OpenClaw command, external finance service, workspace tool, database path, LLM provider, or network API.
---

# Finance Steward

Operate private financial records without exposing unrelated account data or flooding conversation context. Prefer deterministic extraction. Treat model review as an optional second pass over sanitized staging fields, never as an importer dependency.

## Use the Canonical Data Model

Read [references/database-design.md](references/database-design.md) before creating or changing a ledger schema, importing a new source format, migrating legacy transaction data, or designing a finance report. Use [references/schema.sql](references/schema.sql) as the canonical SQLite DDL for a new ledger.

Treat the nine-column bank-flow layout as a presentation view, not the storage schema. Store authoritative values in the double-entry journal, derive income, expense, and running balance, and keep counterparty identity separate from accounting category. Do not deploy or depend on Actual Budget, Firefly III, or another finance service.

## Use the Bundled Importer

Resolve paths relative to this `SKILL.md`. Run `scripts/finance_import.py` with `uv run python`; do not search for or install a workspace-specific finance command. Read [references/import-contract.md](references/import-contract.md) before importing a new file format, creating a profile, interpreting a warning, or loading staging records into a ledger.

Keep the importer usable with the Python standard library and no network access. Keep its JSONL staging output separate from any database implementation so another agent can reproduce and inspect the import.

## Enforce Privacy Boundaries

- Process financial records only in a direct, private conversation with the owner. Refuse to inspect, summarize, search, or quote them in a group or shared channel.
- Keep originals, extracted files, and the ledger in the configured local persistent finance directory.
- Never place a full PDF, statement, CSV, ZIP, or OCR dump in the conversation or model prompt.
- Expose only transaction fields needed for validation: date, merchant or description, amount, and currency when needed.
- Never expose account or routing numbers, statement addresses, legal names, login data, balances, limits, interest details, rewards identifiers, or unrelated statement text to a model or conversational output.
- Never print secrets or credentials. Refer to configured environment variables or secret stores by name only.
- Query an LLM-safe view or explicitly select sanitized fields; never expose identifier ciphertext, account numbers, raw payload paths, balances, or source documents to a model.
- Ask for explicit confirmation before connecting an external account or performing transfers, payments, trades, orders, or account-setting changes. Treat read-only local imports and ledger queries as separate from those actions.

## Import Files

Work on exactly one source file at a time. For an archive, enumerate members locally, extract one supported file into private storage, finish its staging and review, then continue. Use a fresh isolated session or turn per file when available.

Inspect without exposing transaction contents:

```bash
uv run python <skill-dir>/scripts/finance_import.py inspect "/path/to/download"
```

Stage CSV, TSV, XLSX, OFX, QFX, QBO, or QIF using automatic detection:

```bash
uv run python <skill-dir>/scripts/finance_import.py stage "/path/to/download" \
  --account-key "stable-local-account-key" \
  --output "/private/staging/download.jsonl"
```

Use a reviewed JSON profile for PDF or extracted statement text. Supply the verified closing date when rows omit a year:

```bash
uv run python <skill-dir>/scripts/finance_import.py stage "/path/to/statement.pdf" \
  --profile <skill-dir>/assets/import-profiles/chase-card-layout.json \
  --statement-end 2026-08-04 \
  --account-key "stable-local-account-key" \
  --output "/private/staging/statement.jsonl"
```

Use `--sign-mode invert` or a profile sign mode when a credit-card export reports purchases as positive numbers. Verify the sign with a known purchase and payment before acceptance.

Treat bundled bank profiles as examples tied to a layout, not universal institution guarantees. If a file has unfamiliar headers or statement rows, create a local JSON profile using the import contract. Keep personal values out of the profile; include only column labels, regular expressions, date formats, currency, and sign rules.

Return `failed` for binary XLS, encrypted PDFs, scanned image-only PDFs, undecodable custom-font PDFs, and unmatched layouts. Preserve the source and request a different bank export such as CSV, OFX, QFX, QBO, or QIF. Never infer transactions from an unreliable extraction.

## Validate Before Accepting Transactions

Run the bundled validator on every staging file:

```bash
uv run python <skill-dir>/scripts/finance_import.py validate "/private/staging/download.jsonl"
```

Accept only `status=staged` from `stage` and `status=valid` from `validate`. Independently verify source record count, sign convention, duplicate count, and—when available—statement totals or closing-balance movement. Treat every warning, skipped matched line, count mismatch, duplicate dedupe key, or PDF layout change as unresolved.

An agent may perform provider-neutral second-pass review when useful. Give it only transaction date, sanitized description, signed amount, and currency. Compare its structured result with staging locally. Do not require Qwen, Kimi, LiteLLM, OpenAI, or any other model/provider for a deterministic import to run.

## Control Batch Context

For every file:

1. Run only the command needed for that file.
2. Inspect structured command output, not the entire source.
3. Record only status and counts in the response.
4. End that file's isolated session before starting the next file.

Use this concise progress format:

```text
<filename>: imported_or_seen=<n>, skipped=<n>, validation=<matched|mismatch|not-supported>
```

Do not list merchants or amounts in routine progress messages. After a batch, report aggregate file and transaction counts plus any filenames that require review.

## Query and Analyze

Use accepted staging records or the canonical ledger rather than reopening source documents. Query the normalized views documented in [references/database-design.md](references/database-design.md); keep the importer independent from a specific SQLite path or service.

State the time range, account scope, currency, and sign convention behind any analysis. Distinguish observed ledger facts from estimates or recommendations. Use conservative categories, disclose uncertainty, and avoid silently recategorizing reviewed transactions.

When answering spending, budgeting, or reconciliation questions:

1. Query only the fields and date range needed.
2. Check for duplicates, missing periods, parser mismatches, and unsupported files before drawing conclusions.
3. Explain material anomalies without disclosing unrelated transaction details.
4. Treat financial guidance as general analysis, not legal, tax, or fiduciary advice.

## Preserve Idempotency and Auditability

- Preserve the staging manifest, source SHA-256, record hashes, source locators, and dedupe keys; do not manually duplicate entries after a retry.
- Preserve originals and validation metadata so imports can be audited.
- Report `imported_or_seen` separately from `skipped`; do not describe both as newly inserted transactions.
- Never delete or rewrite source files or ledger entries without an explicit request and a verified backup or recovery path.
