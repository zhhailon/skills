---
name: finance-steward
description: Ingest, reconcile, organize, query, and analyze private household financial records across agents. Use for bank or credit-card statements, transaction exports, receipts, spending summaries, reconciliation, categorization, duplicate-safe batches, and ledger design. Use the currently available LLM for document extraction; require no named model, provider, finance service, or bank integration.
---

# Finance Steward

Process one private financial file at a time. Use the available LLM to identify transactions; do not infer PDF layouts with regular expressions or statement profiles.

## Use the Private-Model Trust Boundary

- Treat the configured default model as a private deployment controlled by the owner. It may read the complete current statement, including account metadata, balances, and identity fields; sending the source to it is inside the trusted boundary.
- Keep sources, model artifacts, staging files, and the ledger in private persistent storage.
- Give the model one file at a time to control context, not to redact the file. Split by page only when the runtime cannot consume the document directly.
- Keep extraction JSON transaction-focused because it is a stable interchange schema. This is data modeling, not protection from the private model.
- Preserve transaction descriptions needed for reconciliation; do not mask identifiers merely because a model reads them.
- Keep routine progress messages concise. Show full sensitive fields only when the owner asks or when resolving a specific discrepancy.
- Treat external APIs, shared channels, logs, and exports as outside the private-model boundary. Require explicit approval before sending financial data to them.

## Extract with the Available LLM

Read [references/import-contract.md](references/import-contract.md) before importing files or interpreting a mismatch.

For each file:

1. Start a fresh isolated session, using whatever the runtime provides for that — a new-session command or a unique session ID.
2. Give the current file to the model the runtime already provides. Do not require a particular model, a particular provider, or a second one.
3. Review every page exactly once and write the first extraction JSON defined by the import contract.
4. Start another fresh session using the available model. Give it the source file, not the first result, and write a second extraction JSON using the same schema.
5. Run `scripts/finance.py stage` to reconcile and stage both results.

The second pass is a fresh-context reconciliation. When both passes use the same model, record `same_model_fresh_context`; treat it as useful error detection, not model-independent confirmation. If the environment happens to route the passes to different models, the script records `cross_model`. Model diversity is optional.

Use native document input when available. If the runtime cannot read a PDF directly, render or extract one page locally and send pages sequentially within that file's isolated session. Preserve page numbers. Never use a row regex or statement profile to decide what counts as a transaction.

## Reconcile and Stage

Run the bundled script with any Python 3.9 or newer. It imports only the standard library, so it needs no package manager, virtual environment, or installed dependency. The ledger needs SQLite 3.37 or newer, because the schema uses `STRICT` tables:

```bash
python3 <skill-dir>/scripts/finance.py stage /private/source.pdf \
  --extraction /private/first.json \
  --verification /private/second.json \
  --account-key stable-local-account-key \
  --output /private/staging/source.jsonl
```

The script does not parse documents or call a model. It only:

- rejects fields outside the extraction schema and malformed transaction records;
- requires complete page coverage and distinct run IDs;
- compares both extractions as multisets;
- creates record hashes, dedupe keys, JSONL, and a manifest.

Accept `status=staged`. Stop on `needs_review` or `failed`. A mismatch means the two LLM passes disagree; show only mismatch counts, then use a new session to resolve the specific records. A duplicate dedupe key may represent two real purchases: ask the owner before removing either record.

Load accepted staging into the canonical SQLite ledger:

```bash
python3 <skill-dir>/scripts/finance.py load \
  --source /private/source.pdf \
  --staging /private/staging/source.jsonl \
  --manifest /private/staging/source.jsonl.manifest.json \
  --schema <skill-dir>/references/schema.sql \
  --ledger /private/ledger.sqlite \
  --account-key stable-local-account-key \
  --account-type liability
```

The loader records source provenance, the import batch, parsed import records, validation evidence, and idempotent transactions. It re-verifies the manifest and refuses anything that is not `status=staged`.

`--account-key` and `--account-type` go together and turn posting on. The key must hash to the `account_key_hash` the staging manifest recorded, so a batch cannot be posted to the wrong account. Use `asset` for a bank account and `liability` for a credit card. With them, the loader posts each transaction as two balanced legs: the statement account, and `Uncategorized Expense` or `Uncategorized Income`. Recategorize later by reversing and reposting; posted transactions are immutable.

Account identity and type never come from the statement. The extraction schema has no account, balance, routing, or holder field, so the model cannot report them even though it can read them. You supply them, and the loader rejects a later run that contradicts an established account type, account currency, or household base currency rather than silently keeping the first value.

Nothing can check that `--account-key` is the *right* key for a given statement. The key feeds every dedupe key, so importing one account's statement under another account's key stages clean and duplicates the whole statement under the wrong account. Keep one key per real account, record the mapping outside the ledger, and confirm it before importing an unfamiliar file.

Omit both flags to load drafts only and invent nothing. The loader still never invents counterparties, real categories, or an exchange rate: a record whose currency differs from the household base currency stays a draft and is reported as `unposted_foreign_currency`.

## Control Batch Context

For an archive, enumerate members locally. Extract one supported file, finish both LLM passes and reconciliation, then begin the next file with a fresh session. Keep each file's source, two extraction JSON files, staging JSONL, and manifest together.

Use this progress format:

```text
<file index>/<total>: transactions=<n>, reconciliation=<matched|mismatch>, verification=<same_model_fresh_context|cross_model>, status=<staged|needs_review|failed>
```

After a batch, report aggregate file and transaction counts plus only the file indexes requiring review.

## Use the Canonical Ledger

Read [references/database-design.md](references/database-design.md) before creating or changing a ledger schema, migrating records, or designing a finance report. Use [references/schema.sql](references/schema.sql) as the canonical SQLite DDL; it holds only what ingest, posting, and audit need.

[references/schema-extensions.sql](references/schema-extensions.sql) adds optional subsystems: tags, budgets, savings goals, recurring rules, reconciliation sessions, receipt line items, account ownership, and encrypted counterparty identifiers. No script writes them. Apply it with `--extensions` only when a task needs one, and read its notes on key management before storing any identifier.

Treat the nine-column bank-flow layout as a presentation view. Store authoritative values in the double-entry journal, derive income, expense, and running balance, and keep counterparty identity separate from accounting category. Do not require an external budgeting, accounting, or bank-aggregation service.

Query accepted staging records or the ledger rather than reopening statements. State the time range, account scope, currency, and sign convention. Check unresolved files and duplicates before drawing conclusions. Ask for explicit confirmation before connecting accounts or performing transfers, payments, trades, orders, or account-setting changes.

## Preserve Auditability

- Preserve originals, both extraction JSON files, source hashes, page locators, staging manifests, record hashes, and dedupe keys.
- Use a stable opaque account key; never put an account number in it.
- Never delete or rewrite sources or accepted ledger entries without explicit approval and a recovery path.
