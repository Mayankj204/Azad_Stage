-- ALAP Cohorts (Young Women Group) — one record per cohort entry. The
-- spec doc (Basic Information of Young Women Group.docx) defines 21
-- fields including conditional ones for caste/community "Other" and
-- marital-status Married/Widow.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_alap_cohorts (
  id                     SERIAL PRIMARY KEY,
  group_name             VARCHAR(200) NOT NULL,
  name                   VARCHAR(200) NOT NULL,
  batch_no               INTEGER NOT NULL,
  date_of_birth          DATE NOT NULL,
  age                    INTEGER,
  address                TEXT NOT NULL,
  caste_category         VARCHAR(50),
  caste_other            VARCHAR(200),
  community              VARCHAR(50),
  community_other        VARCHAR(200),
  education_work_status  TEXT,
  family_members         INTEGER,
  monthly_family_income  NUMERIC(12,2),
  marital_status         VARCHAR(50),
  years_since_marriage   INTEGER,
  husband_occupation     VARCHAR(200),
  no_of_children         INTEGER,
  activity_type          VARCHAR(80),
  topic                  TEXT,
  details                TEXT,
  activity_date          DATE,
  status                 VARCHAR(20) DEFAULT 'Active',
  deleted_at             TIMESTAMPTZ,
  created_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_at             TIMESTAMPTZ DEFAULT NOW(),
  created_by             VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ak_alap_cohorts_group ON ak_alap_cohorts(group_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_alap_cohorts_name  ON ak_alap_cohorts(name)       WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_alap_cohorts_batch ON ak_alap_cohorts(batch_no)   WHERE deleted_at IS NULL;
