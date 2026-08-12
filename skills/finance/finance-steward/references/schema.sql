PRAGMA foreign_keys = ON;

CREATE TABLE currencies (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  minor_units INTEGER NOT NULL DEFAULT 2 CHECK (minor_units BETWEEN 0 AND 8)
) STRICT;

CREATE TABLE households (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_currency_code TEXT NOT NULL REFERENCES currencies(code),
  timezone TEXT NOT NULL,
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE household_members (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member', 'dependent')),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  UNIQUE (household_id, display_name)
) STRICT;

CREATE TABLE institutions (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  name TEXT NOT NULL,
  country_code TEXT,
  website TEXT,
  UNIQUE (household_id, name)
) STRICT;

CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  parent_account_id TEXT REFERENCES accounts(id),
  institution_id TEXT REFERENCES institutions(id),
  name TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK (account_type IN ('asset', 'liability', 'equity', 'income', 'expense')),
  subtype TEXT,
  currency_code TEXT REFERENCES currencies(code),
  masked_identifier TEXT,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  opened_on TEXT,
  closed_on TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (household_id, name),
  CHECK (closed_on IS NULL OR opened_on IS NULL OR closed_on >= opened_on),
  CHECK (account_type NOT IN ('asset', 'liability') OR currency_code IS NOT NULL)
) STRICT;

CREATE INDEX accounts_household_type_idx ON accounts(household_id, account_type);
CREATE INDEX accounts_parent_idx ON accounts(parent_account_id);

CREATE TABLE account_owners (
  account_id TEXT NOT NULL REFERENCES accounts(id),
  member_id TEXT NOT NULL REFERENCES household_members(id),
  ownership_role TEXT NOT NULL DEFAULT 'owner' CHECK (ownership_role IN ('owner', 'joint_owner', 'authorized_user', 'beneficiary')),
  PRIMARY KEY (account_id, member_id)
) STRICT;

CREATE TABLE counterparties (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  display_name TEXT NOT NULL,
  counterparty_type TEXT NOT NULL DEFAULT 'merchant' CHECK (counterparty_type IN ('merchant', 'person', 'employer', 'government', 'financial_institution', 'other')),
  institution_id TEXT REFERENCES institutions(id),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  UNIQUE (household_id, display_name)
) STRICT;

CREATE TABLE counterparty_aliases (
  id TEXT PRIMARY KEY,
  counterparty_id TEXT NOT NULL REFERENCES counterparties(id),
  normalized_alias TEXT NOT NULL,
  match_type TEXT NOT NULL DEFAULT 'exact' CHECK (match_type IN ('exact', 'contains', 'regex')),
  priority INTEGER NOT NULL DEFAULT 100,
  UNIQUE (counterparty_id, normalized_alias, match_type)
) STRICT;

CREATE TABLE counterparty_identifiers (
  id TEXT PRIMARY KEY,
  counterparty_id TEXT NOT NULL REFERENCES counterparties(id),
  institution_id TEXT REFERENCES institutions(id),
  identifier_type TEXT NOT NULL CHECK (identifier_type IN ('bank_account', 'iban', 'card', 'other')),
  identifier_ciphertext BLOB NOT NULL,
  identifier_hash BLOB NOT NULL,
  masked_suffix TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (identifier_type, identifier_hash)
) STRICT;

CREATE TABLE source_files (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
  original_name TEXT NOT NULL,
  media_type TEXT,
  byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
  stored_path TEXT NOT NULL,
  received_at TEXT NOT NULL,
  UNIQUE (household_id, sha256)
) STRICT;

CREATE TABLE import_batches (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  source_file_id TEXT REFERENCES source_files(id),
  importer_name TEXT NOT NULL,
  importer_version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'validated', 'committed', 'failed', 'cancelled')),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(summary_json))
) STRICT;

CREATE TABLE import_records (
  id TEXT PRIMARY KEY,
  import_batch_id TEXT NOT NULL REFERENCES import_batches(id),
  source_file_id TEXT NOT NULL REFERENCES source_files(id),
  source_locator TEXT NOT NULL,
  record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
  parsed_date TEXT,
  parsed_amount_minor INTEGER,
  parsed_currency_code TEXT REFERENCES currencies(code),
  parsed_description TEXT,
  sanitized_description TEXT,
  raw_payload_path TEXT,
  parse_status TEXT NOT NULL CHECK (parse_status IN ('parsed', 'skipped', 'ambiguous', 'failed')),
  error_code TEXT,
  UNIQUE (source_file_id, source_locator),
  UNIQUE (source_file_id, record_hash)
) STRICT;

CREATE TABLE transactions (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  transaction_date TEXT NOT NULL,
  posted_date TEXT,
  description TEXT NOT NULL,
  counterparty_id TEXT REFERENCES counterparties(id),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'void')),
  dedupe_key TEXT NOT NULL,
  notes TEXT,
  reverses_transaction_id TEXT REFERENCES transactions(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (household_id, dedupe_key)
) STRICT;

CREATE INDEX transactions_household_date_idx ON transactions(household_id, transaction_date);
CREATE INDEX transactions_counterparty_idx ON transactions(counterparty_id);

CREATE TABLE postings (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  account_id TEXT NOT NULL REFERENCES accounts(id),
  amount_minor INTEGER NOT NULL CHECK (amount_minor <> 0),
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  base_amount_minor INTEGER NOT NULL CHECK (base_amount_minor <> 0),
  exchange_rate_num INTEGER CHECK (exchange_rate_num IS NULL OR exchange_rate_num > 0),
  exchange_rate_den INTEGER CHECK (exchange_rate_den IS NULL OR exchange_rate_den > 0),
  memo TEXT,
  cleared_at TEXT,
  reconciled_at TEXT,
  created_at TEXT NOT NULL,
  CHECK ((exchange_rate_num IS NULL) = (exchange_rate_den IS NULL))
) STRICT;

CREATE INDEX postings_transaction_idx ON postings(transaction_id);
CREATE INDEX postings_account_idx ON postings(account_id, transaction_id);

CREATE TABLE transaction_sources (
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  import_record_id TEXT NOT NULL REFERENCES import_records(id),
  relationship TEXT NOT NULL DEFAULT 'primary' CHECK (relationship IN ('primary', 'corroborates', 'attachment')),
  PRIMARY KEY (transaction_id, import_record_id)
) STRICT;

CREATE TABLE validation_runs (
  id TEXT PRIMARY KEY,
  import_batch_id TEXT NOT NULL REFERENCES import_batches(id),
  source_file_id TEXT NOT NULL REFERENCES source_files(id),
  validator_kind TEXT NOT NULL CHECK (validator_kind IN ('deterministic', 'model', 'manual')),
  validator_name TEXT NOT NULL,
  validator_version TEXT,
  sanitized_input_sha256 TEXT CHECK (sanitized_input_sha256 IS NULL OR length(sanitized_input_sha256) = 64),
  parser_count INTEGER CHECK (parser_count IS NULL OR parser_count >= 0),
  validator_count INTEGER CHECK (validator_count IS NULL OR validator_count >= 0),
  difference_count INTEGER CHECK (difference_count IS NULL OR difference_count >= 0),
  status TEXT NOT NULL CHECK (status IN ('matched', 'mismatch', 'passed', 'failed', 'needs_review')),
  details_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details_json)),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE tags (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  name TEXT NOT NULL,
  color TEXT,
  UNIQUE (household_id, name)
) STRICT;

CREATE TABLE transaction_tags (
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  tag_id TEXT NOT NULL REFERENCES tags(id),
  PRIMARY KEY (transaction_id, tag_id)
) STRICT;

CREATE TABLE posting_tags (
  posting_id TEXT NOT NULL REFERENCES postings(id),
  tag_id TEXT NOT NULL REFERENCES tags(id),
  PRIMARY KEY (posting_id, tag_id)
) STRICT;

CREATE TABLE transaction_links (
  from_transaction_id TEXT NOT NULL REFERENCES transactions(id),
  to_transaction_id TEXT NOT NULL REFERENCES transactions(id),
  link_type TEXT NOT NULL CHECK (link_type IN ('refund_of', 'reimbursement_for', 'duplicate_of', 'related')),
  PRIMARY KEY (from_transaction_id, to_transaction_id, link_type),
  CHECK (from_transaction_id <> to_transaction_id)
) STRICT;

CREATE TABLE receipt_items (
  id TEXT PRIMARY KEY,
  transaction_id TEXT NOT NULL REFERENCES transactions(id),
  source_file_id TEXT REFERENCES source_files(id),
  line_number INTEGER,
  description TEXT NOT NULL,
  quantity_milli INTEGER,
  unit_price_minor INTEGER,
  amount_minor INTEGER NOT NULL,
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  category_account_id TEXT REFERENCES accounts(id),
  confidence_milli INTEGER CHECK (confidence_milli IS NULL OR confidence_milli BETWEEN 0 AND 1000)
) STRICT;

CREATE TABLE balance_snapshots (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  effective_at TEXT NOT NULL,
  balance_minor INTEGER NOT NULL,
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('opening', 'closing', 'after_transaction', 'manual', 'bank_sync')),
  source_file_id TEXT REFERENCES source_files(id),
  import_record_id TEXT REFERENCES import_records(id),
  verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
  UNIQUE (account_id, effective_at, snapshot_type, source_file_id)
) STRICT;

CREATE TABLE budgets (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  name TEXT NOT NULL,
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  UNIQUE (household_id, name)
) STRICT;

CREATE TABLE budget_periods (
  id TEXT PRIMARY KEY,
  budget_id TEXT NOT NULL REFERENCES budgets(id),
  starts_on TEXT NOT NULL,
  ends_on TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  UNIQUE (budget_id, starts_on, ends_on),
  CHECK (ends_on >= starts_on)
) STRICT;

CREATE TABLE budget_allocations (
  id TEXT PRIMARY KEY,
  budget_period_id TEXT NOT NULL REFERENCES budget_periods(id),
  category_account_id TEXT NOT NULL REFERENCES accounts(id),
  allocated_minor INTEGER NOT NULL CHECK (allocated_minor >= 0),
  rollover_minor INTEGER NOT NULL DEFAULT 0,
  UNIQUE (budget_period_id, category_account_id)
) STRICT;

CREATE TABLE recurring_rules (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  name TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('monitor', 'generate')),
  rrule TEXT NOT NULL,
  counterparty_id TEXT REFERENCES counterparties(id),
  source_account_id TEXT REFERENCES accounts(id),
  destination_account_id TEXT REFERENCES accounts(id),
  expected_amount_minor INTEGER,
  tolerance_minor INTEGER NOT NULL DEFAULT 0 CHECK (tolerance_minor >= 0),
  currency_code TEXT REFERENCES currencies(code),
  next_due_on TEXT,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  UNIQUE (household_id, name)
) STRICT;

CREATE TABLE savings_goals (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  name TEXT NOT NULL,
  target_account_id TEXT REFERENCES accounts(id),
  target_minor INTEGER NOT NULL CHECK (target_minor > 0),
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  target_date TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'cancelled')),
  UNIQUE (household_id, name)
) STRICT;

CREATE TABLE goal_contributions (
  goal_id TEXT NOT NULL REFERENCES savings_goals(id),
  posting_id TEXT NOT NULL REFERENCES postings(id),
  allocated_minor INTEGER NOT NULL CHECK (allocated_minor > 0),
  PRIMARY KEY (goal_id, posting_id)
) STRICT;

CREATE TABLE reconciliations (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  starts_on TEXT NOT NULL,
  ends_on TEXT NOT NULL,
  opening_balance_minor INTEGER,
  closing_balance_minor INTEGER NOT NULL,
  currency_code TEXT NOT NULL REFERENCES currencies(code),
  source_file_id TEXT REFERENCES source_files(id),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'balanced', 'closed', 'disputed')),
  created_at TEXT NOT NULL,
  closed_at TEXT,
  UNIQUE (account_id, starts_on, ends_on),
  CHECK (ends_on >= starts_on)
) STRICT;

CREATE TABLE reconciliation_items (
  reconciliation_id TEXT NOT NULL REFERENCES reconciliations(id),
  posting_id TEXT NOT NULL REFERENCES postings(id),
  matched INTEGER NOT NULL DEFAULT 1 CHECK (matched IN (0, 1)),
  PRIMARY KEY (reconciliation_id, posting_id)
) STRICT;

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'agent', 'system')),
  actor_id TEXT,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  before_sha256 TEXT CHECK (before_sha256 IS NULL OR length(before_sha256) = 64),
  after_sha256 TEXT CHECK (after_sha256 IS NULL OR length(after_sha256) = 64),
  occurred_at TEXT NOT NULL
) STRICT;

CREATE INDEX audit_events_entity_idx ON audit_events(entity_type, entity_id, occurred_at);

CREATE TRIGGER budget_period_no_overlap_insert
BEFORE INSERT ON budget_periods
WHEN EXISTS (
  SELECT 1
  FROM budget_periods AS existing
  WHERE existing.budget_id = NEW.budget_id
    AND existing.starts_on <= NEW.ends_on
    AND existing.ends_on >= NEW.starts_on
)
BEGIN
  SELECT RAISE(ABORT, 'budget periods must not overlap within a budget');
END;

CREATE TRIGGER budget_period_no_overlap_update
BEFORE UPDATE OF budget_id, starts_on, ends_on ON budget_periods
WHEN EXISTS (
  SELECT 1
  FROM budget_periods AS existing
  WHERE existing.budget_id = NEW.budget_id
    AND existing.id <> OLD.id
    AND existing.starts_on <= NEW.ends_on
    AND existing.ends_on >= NEW.starts_on
)
BEGIN
  SELECT RAISE(ABORT, 'budget periods must not overlap within a budget');
END;

CREATE TRIGGER transaction_tag_household_must_match_insert
BEFORE INSERT ON transaction_tags
WHEN (SELECT household_id FROM transactions WHERE id = NEW.transaction_id)
   <> (SELECT household_id FROM tags WHERE id = NEW.tag_id)
BEGIN
  SELECT RAISE(ABORT, 'transaction and tag belong to different households');
END;

CREATE TRIGGER transaction_tag_household_must_match_update
BEFORE UPDATE OF transaction_id, tag_id ON transaction_tags
WHEN (SELECT household_id FROM transactions WHERE id = NEW.transaction_id)
   <> (SELECT household_id FROM tags WHERE id = NEW.tag_id)
BEGIN
  SELECT RAISE(ABORT, 'transaction and tag belong to different households');
END;

CREATE TRIGGER posting_tag_household_must_match_insert
BEFORE INSERT ON posting_tags
WHEN (
  SELECT t.household_id
  FROM postings AS p
  JOIN transactions AS t ON t.id = p.transaction_id
  WHERE p.id = NEW.posting_id
) <> (SELECT household_id FROM tags WHERE id = NEW.tag_id)
BEGIN
  SELECT RAISE(ABORT, 'posting and tag belong to different households');
END;

CREATE TRIGGER posting_tag_household_must_match_update
BEFORE UPDATE OF posting_id, tag_id ON posting_tags
WHEN (
  SELECT t.household_id
  FROM postings AS p
  JOIN transactions AS t ON t.id = p.transaction_id
  WHERE p.id = NEW.posting_id
) <> (SELECT household_id FROM tags WHERE id = NEW.tag_id)
BEGIN
  SELECT RAISE(ABORT, 'posting and tag belong to different households');
END;

CREATE TRIGGER post_transaction_requires_balance
BEFORE UPDATE OF status ON transactions
WHEN NEW.status = 'posted' AND OLD.status <> 'posted'
BEGIN
  SELECT CASE
    WHEN (SELECT COUNT(*) FROM postings WHERE transaction_id = NEW.id) < 2
      THEN RAISE(ABORT, 'posted transaction requires at least two postings')
    WHEN COALESCE((SELECT SUM(base_amount_minor) FROM postings WHERE transaction_id = NEW.id), 0) <> 0
      THEN RAISE(ABORT, 'posted transaction is not balanced in base currency')
  END;
END;

CREATE TRIGGER posting_household_must_match_transaction
BEFORE INSERT ON postings
WHEN (SELECT household_id FROM accounts WHERE id = NEW.account_id)
   <> (SELECT household_id FROM transactions WHERE id = NEW.transaction_id)
BEGIN
  SELECT RAISE(ABORT, 'posting account and transaction belong to different households');
END;

CREATE TRIGGER transaction_counterparty_household_must_match_insert
BEFORE INSERT ON transactions
WHEN NEW.counterparty_id IS NOT NULL
 AND (SELECT household_id FROM counterparties WHERE id = NEW.counterparty_id) <> NEW.household_id
BEGIN
  SELECT RAISE(ABORT, 'counterparty and transaction belong to different households');
END;

CREATE TRIGGER transaction_counterparty_household_must_match_update
BEFORE UPDATE OF counterparty_id, household_id ON transactions
WHEN NEW.counterparty_id IS NOT NULL
 AND (SELECT household_id FROM counterparties WHERE id = NEW.counterparty_id) <> NEW.household_id
BEGIN
  SELECT RAISE(ABORT, 'counterparty and transaction belong to different households');
END;

CREATE TRIGGER prevent_posting_insert_into_posted_transaction
BEFORE INSERT ON postings
WHEN (SELECT status FROM transactions WHERE id = NEW.transaction_id) = 'posted'
BEGIN
  SELECT RAISE(ABORT, 'posted transactions are immutable');
END;

CREATE TRIGGER prevent_posting_update_on_posted_transaction
BEFORE UPDATE ON postings
WHEN (SELECT status FROM transactions WHERE id = OLD.transaction_id) = 'posted'
BEGIN
  SELECT RAISE(ABORT, 'posted transactions are immutable');
END;

CREATE TRIGGER prevent_posting_delete_on_posted_transaction
BEFORE DELETE ON postings
WHEN (SELECT status FROM transactions WHERE id = OLD.transaction_id) = 'posted'
BEGIN
  SELECT RAISE(ABORT, 'posted transactions are immutable');
END;

CREATE TRIGGER prevent_posted_transaction_mutation
BEFORE UPDATE ON transactions
WHEN OLD.status = 'posted'
BEGIN
  SELECT RAISE(ABORT, 'posted transactions are immutable; create a reversal');
END;

CREATE VIEW validator_safe_import_records AS
SELECT
  id AS import_record_id,
  parsed_date AS transaction_date,
  sanitized_description AS description,
  parsed_amount_minor AS signed_amount_minor,
  parsed_currency_code AS currency_code
FROM import_records
WHERE parse_status = 'parsed'
  AND sanitized_description IS NOT NULL;

CREATE VIEW household_transaction_analysis AS
WITH transaction_activity AS (
  SELECT
    t.household_id,
    t.id AS transaction_id,
    t.transaction_date,
    t.posted_date,
    h.base_currency_code,
    SUM(CASE
      WHEN a.account_type = 'income' THEN -p.base_amount_minor
      ELSE 0
    END) AS income_minor,
    SUM(CASE
      WHEN a.account_type = 'expense' THEN p.base_amount_minor
      ELSE 0
    END) AS expense_minor,
    SUM(CASE
      WHEN a.account_type = 'income' THEN 1
      ELSE 0
    END) AS income_posting_count,
    SUM(CASE
      WHEN a.account_type = 'expense' THEN 1
      ELSE 0
    END) AS expense_posting_count,
    SUM(CASE
      WHEN a.account_type IN ('asset', 'liability') THEN 1
      ELSE 0
    END) AS financial_posting_count
  FROM transactions AS t
  JOIN households AS h ON h.id = t.household_id
  JOIN postings AS p ON p.transaction_id = t.id
  JOIN accounts AS a ON a.id = p.account_id
  WHERE t.status = 'posted'
  GROUP BY
    t.household_id,
    t.id,
    t.transaction_date,
    t.posted_date,
    h.base_currency_code
)
SELECT
  household_id,
  transaction_id,
  transaction_date,
  posted_date,
  base_currency_code,
  CASE
    WHEN income_posting_count > 0 AND expense_posting_count > 0 THEN 'mixed'
    WHEN income_posting_count > 0 THEN 'income'
    WHEN expense_posting_count > 0 THEN 'expense'
    WHEN financial_posting_count >= 2 THEN 'transfer'
    ELSE 'adjustment'
  END AS transaction_kind,
  income_minor,
  expense_minor,
  income_posting_count,
  expense_posting_count,
  financial_posting_count
FROM transaction_activity;

CREATE VIEW household_account_register AS
SELECT
  t.household_id,
  t.id AS transaction_id,
  p.id AS posting_id,
  t.transaction_date,
  t.posted_date,
  a.id AS account_id,
  a.name AS account_name,
  a.account_type,
  p.currency_code,
  p.amount_minor AS signed_amount_minor,
  CASE WHEN p.amount_minor > 0 THEN p.amount_minor ELSE 0 END AS account_inflow_minor,
  CASE WHEN p.amount_minor < 0 THEN -p.amount_minor ELSE 0 END AS account_outflow_minor,
  SUM(p.amount_minor) OVER (
    PARTITION BY p.account_id
    ORDER BY
      t.transaction_date,
      COALESCE(t.posted_date, t.transaction_date),
      t.created_at,
      p.id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS ledger_running_balance_minor,
  analysis.transaction_kind,
  t.counterparty_id,
  counterparty.display_name AS counterparty_name,
  CASE
    WHEN p.reconciled_at IS NOT NULL THEN 'reconciled'
    WHEN p.cleared_at IS NOT NULL THEN 'cleared'
    ELSE 'pending'
  END AS reconciliation_state,
  t.description,
  t.notes AS transaction_notes,
  p.memo AS posting_memo
FROM transactions AS t
JOIN postings AS p ON p.transaction_id = t.id
JOIN accounts AS a ON a.id = p.account_id
JOIN household_transaction_analysis AS analysis ON analysis.transaction_id = t.id
LEFT JOIN counterparties AS counterparty ON counterparty.id = t.counterparty_id
WHERE t.status = 'posted'
  AND a.account_type IN ('asset', 'liability');

CREATE VIEW household_transaction_categories AS
SELECT
  t.household_id,
  t.id AS transaction_id,
  p.id AS category_posting_id,
  a.id AS category_account_id,
  a.name AS category_name,
  a.account_type AS category_type,
  CASE
    WHEN a.account_type = 'income' THEN -p.base_amount_minor
    ELSE p.base_amount_minor
  END AS activity_minor,
  h.base_currency_code
FROM transactions AS t
JOIN households AS h ON h.id = t.household_id
JOIN postings AS p ON p.transaction_id = t.id
JOIN accounts AS a ON a.id = p.account_id
WHERE t.status = 'posted'
  AND a.account_type IN ('income', 'expense');

CREATE VIEW household_transaction_budgets AS
SELECT
  category.household_id,
  category.transaction_id,
  category.category_posting_id,
  category.category_account_id,
  category.category_name,
  budget.id AS budget_id,
  budget.name AS budget_name,
  period.id AS budget_period_id,
  period.starts_on,
  period.ends_on,
  allocation.id AS budget_allocation_id,
  category.activity_minor AS actual_minor,
  category.base_currency_code
FROM household_transaction_categories AS category
JOIN transactions AS t ON t.id = category.transaction_id
JOIN budget_allocations AS allocation
  ON allocation.category_account_id = category.category_account_id
JOIN budget_periods AS period
  ON period.id = allocation.budget_period_id
 AND t.transaction_date BETWEEN period.starts_on AND period.ends_on
JOIN budgets AS budget
  ON budget.id = period.budget_id
 AND budget.household_id = category.household_id
WHERE category.category_type = 'expense';

CREATE VIEW household_transaction_tag_assignments AS
SELECT
  t.household_id,
  t.id AS transaction_id,
  NULL AS posting_id,
  'transaction' AS assignment_scope,
  tag.id AS tag_id,
  tag.name AS tag_name,
  tag.color AS tag_color,
  NULL AS tagged_base_amount_minor,
  h.base_currency_code
FROM transactions AS t
JOIN households AS h ON h.id = t.household_id
JOIN transaction_tags AS assignment ON assignment.transaction_id = t.id
JOIN tags AS tag
  ON tag.id = assignment.tag_id
 AND tag.household_id = t.household_id
WHERE t.status = 'posted'
UNION ALL
SELECT
  t.household_id,
  t.id AS transaction_id,
  p.id AS posting_id,
  'posting' AS assignment_scope,
  tag.id AS tag_id,
  tag.name AS tag_name,
  tag.color AS tag_color,
  p.base_amount_minor AS tagged_base_amount_minor,
  h.base_currency_code
FROM transactions AS t
JOIN households AS h ON h.id = t.household_id
JOIN postings AS p ON p.transaction_id = t.id
JOIN posting_tags AS assignment ON assignment.posting_id = p.id
JOIN tags AS tag
  ON tag.id = assignment.tag_id
 AND tag.household_id = t.household_id
WHERE t.status = 'posted';
