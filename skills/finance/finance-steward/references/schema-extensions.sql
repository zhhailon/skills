-- Finance Steward optional ledger extensions.
--
-- Load schema.sql first. Nothing in the core schema references anything here,
-- so a ledger is fully usable without this file. Apply it only when a task
-- needs one of these subsystems, and prefer applying the whole file so the
-- household-consistency triggers stay in place.
--
-- No script in this skill writes these tables. Populating them is a deliberate
-- act by the owner or by a task-specific tool.

PRAGMA foreign_keys = ON;

-- People and account ownership -------------------------------------------

CREATE TABLE household_members (
  id TEXT PRIMARY KEY,
  household_id TEXT NOT NULL REFERENCES households(id),
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member', 'dependent')),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  UNIQUE (household_id, display_name)
) STRICT;

CREATE TABLE account_owners (
  account_id TEXT NOT NULL REFERENCES accounts(id),
  member_id TEXT NOT NULL REFERENCES household_members(id),
  ownership_role TEXT NOT NULL DEFAULT 'owner' CHECK (ownership_role IN ('owner', 'joint_owner', 'authorized_user', 'beneficiary')),
  PRIMARY KEY (account_id, member_id)
) STRICT;

-- Encrypted counterparty identifiers --------------------------------------
--
-- Do not use this table until the deployment has a documented key management
-- story: where the key lives, who can read it, and how it is rotated. Without
-- one, store only `masked_suffix` on the counterparty and leave this empty.
-- `identifier_hash` is for equality lookup; it must be a keyed hash (HMAC),
-- because a bare SHA-256 of a card or account number is brute-forceable.

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

-- Tags --------------------------------------------------------------------

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

-- Relationships between transactions --------------------------------------

CREATE TABLE transaction_links (
  from_transaction_id TEXT NOT NULL REFERENCES transactions(id),
  to_transaction_id TEXT NOT NULL REFERENCES transactions(id),
  link_type TEXT NOT NULL CHECK (link_type IN ('refund_of', 'reimbursement_for', 'duplicate_of', 'related')),
  PRIMARY KEY (from_transaction_id, to_transaction_id, link_type),
  CHECK (from_transaction_id <> to_transaction_id)
) STRICT;

-- Receipt line items ------------------------------------------------------

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

-- Budgets -----------------------------------------------------------------

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

-- Recurring rules ---------------------------------------------------------

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

-- Savings goals -----------------------------------------------------------

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

-- Statement reconciliation sessions ---------------------------------------

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

-- Triggers ----------------------------------------------------------------

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

-- Views -------------------------------------------------------------------

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
