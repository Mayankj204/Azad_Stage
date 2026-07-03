-- 054: AK Alumni Quarterly Updates
-- 2026-06-01: Persists the periodic refresh of a small set of "living"
-- fields on the Alumni record — Marital Status, Address, Monthly
-- Income, Phone Number. Each save creates a fresh snapshot tagged
-- with the current Indian-FY quarter label (e.g. "Q1-2026-27" for
-- Apr-Jun 2026), giving the team a full audit trail of how an
-- alumna's life situation evolves over time. The live ak_alumni row
-- is updated in lockstep so the View / Edit page always shows the
-- latest values; the snapshot table is the source of truth for
-- history queries.
--
-- We do NOT enforce one-snapshot-per-quarter — if the user revisits
-- and corrects an entry within the same quarter, both rows live on
-- so the audit trail stays faithful. The history table on the View
-- page presents them newest-first.

SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_alumni_quarterly_updates (
  id              SERIAL PRIMARY KEY,
  alumni_id       INT NOT NULL REFERENCES ak_alumni(id) ON DELETE CASCADE,
  quarter_label   VARCHAR(20) NOT NULL,   -- e.g. 'Q1-2026-27'
  marital_status  VARCHAR(50),
  address         TEXT,
  monthly_income  NUMERIC,                -- aliased to ak_alumni.monthly_salary on write
  mobile          VARCHAR(15),
  updated_by      VARCHAR(100),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ak_alumni_quarterly_alumni
  ON ak_alumni_quarterly_updates(alumni_id);

CREATE INDEX IF NOT EXISTS idx_ak_alumni_quarterly_quarter
  ON ak_alumni_quarterly_updates(quarter_label);
