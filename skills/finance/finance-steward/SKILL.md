---
name: finance-steward
description: Ingest, reconcile, organize, query, and analyze private household financial records across agents. Use for bank or credit-card statements, transaction exports, receipts, spending summaries, reconciliation, categorization, duplicate-safe batches, and ledger design. Use the currently available LLM for document extraction; require no named model, provider, finance service, or bank integration.
---

# Finance Steward

Process one private financial file at a time. Use the available LLM to identify transactions; do not infer PDF layouts with regular expressions or statement profiles.

## Guard Privacy

- Work only in a direct private conversation with the owner.
- Keep sources and staging files in private persistent storage.
- Send the model only the current file or current page. Keep batches out of one context.
- Emit only transaction date, posted date when present, sanitized description, signed amount in minor units, currency, source page, source index, and status.
- Exclude account and routing numbers, balances, addresses, names, limits, interest, rewards identifiers, login data, and unrelated text from extraction JSON and conversation output.
- Report routine progress as counts and status. Do not list merchants or amounts unless resolving a specific mismatch with the owner.

## Extract with the Available LLM

Read [references/import-contract.md](references/import-contract.md) before importing files or interpreting a mismatch.

For each file:

1. Start a fresh isolated session. In Telegram/OpenClaw, use `/new` or a unique session ID.
2. Give the current file to the available model. Do not require Qwen, Kimi, or any second provider; `openclaw-auto` is sufficient.
3. Review every page exactly once and write the first extraction JSON defined by the import contract.
4. Start another fresh session using the available model. Give it the source file, not the first result, and write a second extraction JSON using the same schema.
5. Run `scripts/finance_stage.py` to reconcile and stage both results.

The second pass is a fresh-context reconciliation. When both passes use the same model, record `same_model_fresh_context`; treat it as useful error detection, not model-independent confirmation. If the environment happens to route the passes to different models, the script records `cross_model`. Model diversity is optional.

Use native document input when available. If the runtime cannot read a PDF directly, render or extract one page locally and send pages sequentially within that file's isolated session. Preserve page numbers. Never use a row regex or statement profile to decide what counts as a transaction.

## Reconcile and Stage

Run the bundled standard-library script with `uv`:

```bash
uv run python <skill-dir>/scripts/finance_stage.py /private/source.pdf \
  --extraction /private/first.json \
  --verification /private/second.json \
  --account-key stable-local-account-key \
  --output /private/staging/source.jsonl
```

The script does not parse documents or call a model. It only:

- rejects forbidden fields and malformed transaction records;
- requires complete page coverage and distinct run IDs;
- compares both extractions as multisets;
- creates record hashes, dedupe keys, JSONL, and a manifest.

Accept `status=staged`. Stop on `needs_review` or `failed`. A mismatch means the two LLM passes disagree; show only mismatch counts, then use a new session to resolve the specific records. A duplicate dedupe key may represent two real purchases: ask the owner before removing either record.

## Control Batch Context

For an archive, enumerate members locally without exposing names or contents. Extract one supported file, finish both LLM passes and reconciliation, then begin the next file with a fresh session. Keep each file's source, two extraction JSON files, staging JSONL, and manifest together.

Use this progress format:

```text
<file index>/<total>: transactions=<n>, reconciliation=<matched|mismatch>, verification=<same_model_fresh_context|cross_model>, status=<staged|needs_review|failed>
```

After a batch, report aggregate file and transaction counts plus only the file indexes requiring review.

## Use the Canonical Ledger

Read [references/database-design.md](references/database-design.md) before creating or changing a ledger schema, migrating records, or designing a finance report. Use [references/schema.sql](references/schema.sql) as the canonical SQLite DDL.

Treat the nine-column bank-flow layout as a presentation view. Store authoritative values in the double-entry journal, derive income, expense, and running balance, and keep counterparty identity separate from accounting category. Do not require Actual Budget, Firefly III, or another service.

Query accepted staging records or the ledger rather than reopening statements. State the time range, account scope, currency, and sign convention. Check unresolved files and duplicates before drawing conclusions. Ask for explicit confirmation before connecting accounts or performing transfers, payments, trades, orders, or account-setting changes.

## Preserve Auditability

- Preserve originals, both extraction JSON files, source hashes, page locators, staging manifests, record hashes, and dedupe keys.
- Use a stable opaque account key; never put an account number in it.
- Never delete or rewrite sources or accepted ledger entries without explicit approval and a recovery path.
