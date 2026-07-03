-- 024: Sangini monthly entries (AK module).
-- A Sangini is a community volunteer tracked monthly with activity counts +
-- a list of capacity trainings attended that month.

CREATE TABLE IF NOT EXISTS sangini_entries (
  id                       SERIAL PRIMARY KEY,
  month                    DATE NOT NULL,                    -- first-of-month representation
  sangini_name             VARCHAR(200) NOT NULL,

  -- Basic details
  active_leaders           INT NOT NULL DEFAULT 0,
  active_addas             INT NOT NULL DEFAULT 0,
  active_adda_members      INT NOT NULL DEFAULT 0,

  -- Home Visits
  home_visits              INT DEFAULT 0,
  home_visit_participants  INT DEFAULT 0,
  home_visit_male          INT DEFAULT 0,
  home_visit_female        INT DEFAULT 0,

  -- Phone Calls
  phone_calls              INT DEFAULT 0,

  -- Choupal
  choupals                 INT DEFAULT 0,
  choupal_participants     INT DEFAULT 0,
  choupal_male             INT DEFAULT 0,
  choupal_female           INT DEFAULT 0,

  status                   VARCHAR(20) DEFAULT 'Active',
  created_by               INT,
  created_at               TIMESTAMPTZ DEFAULT NOW(),
  updated_at               TIMESTAMPTZ DEFAULT NOW(),
  deleted_at               TIMESTAMPTZ
);

-- Only one entry per (Sangini, month) among NON-deleted rows. Using a partial
-- unique index so soft-deletes don't block re-creating an entry under the same
-- month + name (a plain UNIQUE constraint would).
CREATE UNIQUE INDEX IF NOT EXISTS uq_sangini_entry_active
  ON sangini_entries (month, LOWER(sangini_name))
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_sangini_entries_month      ON sangini_entries(month);
CREATE INDEX IF NOT EXISTS idx_sangini_entries_name       ON sangini_entries(sangini_name);
CREATE INDEX IF NOT EXISTS idx_sangini_entries_status     ON sangini_entries(status);
CREATE INDEX IF NOT EXISTS idx_sangini_entries_deleted_at ON sangini_entries(deleted_at);


-- Child rows: capacity trainings attended in that month's entry.
-- Multiple rows per entry, each (name + date).
CREATE TABLE IF NOT EXISTS sangini_trainings (
  id               SERIAL PRIMARY KEY,
  entry_id         INT NOT NULL REFERENCES sangini_entries(id) ON DELETE CASCADE,
  training_name    VARCHAR(300) NOT NULL,
  training_date    DATE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sangini_trainings_entry ON sangini_trainings(entry_id);
