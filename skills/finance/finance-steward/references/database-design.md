# Canonical Household Finance Database Design

## Contents

1. Design goals
2. Core accounting model
3. Entity map
4. Transaction invariants
5. Derived registers and exports
6. Import and validation pipeline
7. Privacy boundary
8. Budgeting and planning
9. Reconciliation and corrections
10. Migration and verification

## 1. Design Goals

Use a local relational database as the source of truth for household cash flow, budgets, obligations, savings goals, and net worth. Optimize for:

- correct transfers, refunds, reimbursements, credit-card payments, and split purchases;
- multiple household members, institutions, accounts, and currencies;
- LLM-first imports with deterministic staging, source provenance, and reconciliation;
- idempotency, reconciliation, and immutable posted history;
- useful human views without leaking sensitive identifiers to models;
- SQLite operation today and a clean path to PostgreSQL later.

Do not copy the surface schema of a finance product. Combine these proven ideas:

- double-entry journal for correctness;
- separate counterparty and classification dimensions;
- payee aliases and rules for normalization;
- import IDs/hashes and reconciliation state for auditability;
- budgets, subscriptions, tags, and goals as optional layers over the ledger.

Use [schema.sql](schema.sql) for exact SQLite types, constraints, indexes, and triggers.

## 2. Core Accounting Model

Represent each economic event as one `transactions` journal header plus at least two `postings`.

Use signed posting amounts:

- asset increase: positive;
- asset decrease: negative;
- liability increase: negative;
- liability decrease: positive;
- expense increase: positive;
- income increase: negative;
- equity increase: negative.

Require every posted transaction to satisfy:

```text
SUM(postings.base_amount_minor) = 0
```

Examples in USD minor units:

```text
Restaurant purchase with checking:
  Checking              -2500
  Expense:Dining        +2500

Restaurant purchase with credit card:
  Credit Card           -2500
  Expense:Dining        +2500

Credit-card payment:
  Checking             -10000
  Credit Card          +10000

Salary:
  Checking             +500000
  Income:Salary        -500000

Transfer:
  Checking             -100000
  Savings              +100000
```

Store money as integer minor units. Never use binary floating-point. Store each posting's native `amount_minor` and the household-base-currency `base_amount_minor`. Same-currency postings use identical values; FX postings retain the conversion basis in `exchange_rate_num` and `exchange_rate_den`.

## 3. Entity Map

```text
households
  ├─ household_members ─ account_owners
  ├─ institutions ─ accounts
  ├─ counterparties ─ counterparty_aliases
  │                  └─ counterparty_identifiers (private)
  ├─ transactions ─ postings ─ accounts
  │              │          └─ posting_tags ─ tags
  │              ├─ transaction_tags ─ tags
  │              ├─ transaction_links
  │              ├─ receipt_items
  │              └─ transaction_sources ─ import_records
  ├─ source_files ─ import_batches ─ import_records
  │                              └─ validation_runs
  ├─ budgets ─ budget_periods ─ budget_allocations
  ├─ recurring_rules
  ├─ savings_goals ─ goal_contributions
  └─ reconciliations ─ reconciliation_items
```

### Accounts

Use one chart of accounts for both real financial accounts and reporting categories:

- `asset`: checking, savings, cash, brokerage, property;
- `liability`: credit card, mortgage, loan;
- `expense`: hierarchical spending categories such as `Food:Dining`;
- `income`: salary, interest, and explicit miscellaneous income;
- `equity`: opening balances and explicit accounting adjustments.

Only asset/liability accounts normally have an institution and sensitive identifier. Use parent accounts for hierarchy. Derive balances from postings; never store a mutable `current_balance` on the account.

Record a refund as a negative posting to the original expense category by default. Use an income account only when the event is genuinely new income under an explicit household accounting policy.

### Counterparties

Keep who was paid separate from why money was spent:

```text
counterparty = Chipotle
category account = Expense:Food:Dining
```

Normalize noisy bank descriptions through `counterparty_aliases`. Store bank-account/IBAN/card identifiers only in `counterparty_identifiers`, using ciphertext plus a keyed lookup hash and masked suffix. Never put full identifiers in descriptions, notes, tags, or model prompts.

### Transactions and Postings

Put shared facts on `transactions`: event date, optional posted date, description, normalized counterparty, status, notes, and reversal link. Put amounts and account effects on `postings`. Split a mixed receipt across several expense postings while retaining one transaction and one counterparty.

Use `transaction_links` for semantic relationships such as `refund_of`, `reimbursement_for`, `duplicate_of`, and `related`. A transfer between household accounts is one balanced transaction, not two unrelated transactions.

### Source and Audit Entities

Use:

- `source_files` for immutable original-file identity and storage path;
- `import_batches` for one execution or uploaded archive;
- `import_records` for one extracted transaction candidate from any source format;
- `transaction_sources` for many-to-many provenance;
- `validation_runs` for parser/model agreement without retaining model-visible sensitive text;
- `audit_events` for append-only mutation evidence;
- `balance_snapshots` for statement opening/closing or after-transaction balances.

## 4. Transaction Invariants

Enforce these invariants in application logic and database triggers where possible:

1. Create transactions as `draft`, insert postings, validate, then change to `posted`.
2. Require at least two postings and zero base-currency sum before posting.
3. Make posted transactions and postings immutable. Correct mistakes with a reversing transaction and a replacement transaction.
4. Require one currency per posting and explicit base-currency conversion.
5. Use a stable `dedupe_key` scoped to the household. Prefer bank external ID; otherwise hash normalized account, date, amount, description, and source locator.
6. Allow one source record to support multiple transactions and one transaction to be corroborated by multiple source records.
7. Never infer a missing statement balance, counterparty identifier, or posting date.
8. Preserve raw source values outside conversational output; normalization must not destroy provenance.
9. Require every linked account, counterparty, member, source, budget, and goal to belong to the same household as the transaction or parent object.

## 5. Derived Registers and Exports

Use `household_account_register` as the normal account-scoped register:

```text
日期 | 本方账户 | 账户流入 | 账户流出 | 账面累计 | 交易类型 | 对方/商户 | 核对状态 | 备注
```

The view returns one row per posted asset/liability posting. Query it for one account at a time; a transfer correctly appears once in each affected account. Interpret `account_inflow_minor` and `account_outflow_minor` only as movements in the selected account's signed ledger balance. They are not household income or expense. In particular, a credit-card payment is an account inflow that reduces a liability, not income.

Use `household_transaction_analysis` for household-wide income and expense reporting. Derive `income_minor` only from income-account postings and `expense_minor` only from expense-account postings, both in household base currency. Preserve negative income or expense values for reversals and refunds. Classify a posted transaction as:

- `income` when it changes income accounts only;
- `expense` when it changes expense accounts only, including negative expense refunds;
- `mixed` when it changes both income and expense accounts;
- `transfer` when it changes at least two asset/liability accounts and no income or expense account;
- `adjustment` otherwise, including equity-only opening and correction entries.

Determine the classification from the presence of income and expense postings, not from their net totals. Category reclassifications can net to zero while still containing expense postings.

Do not flatten multi-valued dimensions into scalar register columns. Query these normalized companion views instead:

- `household_transaction_categories`: one row per income/expense posting;
- `household_transaction_budgets`: one row per matching expense category, budget, and period;
- `household_transaction_tag_assignments`: one row per transaction-level or posting-level tag.

Use transaction tags for properties of the whole transaction. Use posting tags when a property applies only to one split, such as a reimbursable portion. Aggregate each companion view independently at the final presentation boundary; never raw-join categories, budgets, and tags and then sum amounts, because their many-to-many product duplicates activity. Scope budget activity to one `budget_id`. Retrieve allocation and rollover values once through `budget_allocation_id` rather than summing them from activity rows.

The original bank-flow layout remains a valid optional export:

```text
日期 | 收入 | 支出 | 余额 | 摘要 | 对方户名 | 对方银行 | 对方账号 | 备注
```

Generate this export from the account register and related tables only when requested. Treat `对方银行` and `对方账号` as private optional metadata. Mask the account identifier by default. Do not make either field mandatory for card purchases.

## 6. Import and Validation Pipeline

Use the bundled `scripts/finance_stage.py` and the LLM extraction contract. Process exactly one source file at a time:

1. Hash and store the immutable original in `source_files`.
2. Use the available LLM in a fresh context to review every page and extract only allowed transaction fields.
3. Repeat from the source in another fresh context. The same model is acceptable; label it `same_model_fresh_context` rather than model-independent verification.
4. Reconcile both transaction multisets with the bundled script and stop on missing, extra, uncertain, or duplicate records.
5. Stage normalized dates, integer amounts, sanitized descriptions, page locators, hashes, and dedupe keys locally without writing ledger entries.
6. Store model identities, run mode, source and extraction hashes, counts, status, and differences in `validation_runs`.
7. Create draft transactions and postings only after staging and validation succeed.
8. Post only after balance, duplicate, count, total, and validation checks pass.
9. Link every posted transaction back to its source record.

The private owner may give the current source file to the active model for extraction. Keep model output transaction-only; never persist balances, account owner data, account identifiers, addresses, source paths, or unrelated raw text in extraction JSON.

## 7. Privacy Boundary

Protect four layers separately:

- **Operational:** restrict filesystem and database access; use encrypted storage or SQLCipher where appropriate.
- **Field:** encrypt full identifiers; store a masked suffix and keyed hash for matching.
- **Conversational:** expose only requested aggregates or masked register fields.
- **Model:** use an allowlist, not a denylist. The validator receives only date, description, amount, and currency.

Provide model-safe database views that expose an explicitly sanitized description and exclude all identifier, ciphertext, path, raw payload, balance, member, account, counterparty, and institution fields. Never grant a model unrestricted SQL access to the base tables.

## 8. Budgeting and Planning

Use category accounts as budget dimensions. A `budget` names a plan; `budget_periods` define non-overlapping date windows; `budget_allocations` assign integer base-currency amounts to expense accounts. Derive actual spending from postings instead of copying it into budget tables.

Support optional rollover explicitly per allocation. Do not silently treat income as budget replenishment. Use tags for orthogonal dimensions rather than multiplying categories.

Use `recurring_rules` for expected or generated subscriptions, income, transfers, and bills. Distinguish:

- `monitor`: expect an imported transaction and flag missing/amount drift;
- `generate`: create a draft transaction when no external source will arrive.

Use `savings_goals` as named targets linked to asset accounts. Goal contributions reference postings; they do not create imaginary balances or lock real money.

## 9. Reconciliation and Corrections

Store statement balances as `balance_snapshots`. Reconcile an asset/liability account over a period by linking its postings to a `reconciliations` row and comparing the derived closing balance with the source snapshot.

Do not mark a transaction reconciled globally when only one account posting was checked. Store clearing and reconciliation at the posting level.

For correction:

1. create a reversal with all posting signs inverted;
2. link it through `reverses_transaction_id` or `transaction_links`;
3. post the corrected replacement;
4. retain both entries and append an audit event.

## 10. Migration and Verification

Never migrate a live legacy ledger destructively in place. Create a separate v2 database and migrate in deterministic batches.

For each batch, verify:

- source-file count and SHA-256 values;
- transaction count and distinct dedupe keys;
- per-account/per-month inflow and outflow totals;
- every posted transaction has at least two postings and balances to zero;
- opening/closing balances and reconciliation differences;
- parser/model validation status;
- no sensitive identifier appears in model-safe views or logs.

Keep the old ledger read-only until totals and representative transaction histories match and the owner explicitly approves cutover.
