-- 2026-05-27
-- MGJ Member form: capture year-of-attainment for the primary education
-- qualification, gate the work-detail fields on "Are you working?", and
-- support a per-member education history (added via the View page's
-- "Add current education qualification" button).
--
-- Schema additions only — existing `education`, `education_other`,
-- `still_studying`, `studying_what`, `career_status` columns are left
-- intact so historical data remains accessible.

BEGIN;

ALTER TABLE mgj_members
    ADD COLUMN IF NOT EXISTS education_year INT,
    ADD COLUMN IF NOT EXISTS is_working     VARCHAR(10);

-- Per-member history of education qualifications. Each row is one
-- "snapshot" added via the View page; the first row matches what the
-- user entered on the Add/Edit form; later rows are appended over time
-- as the member earns new qualifications.
CREATE TABLE IF NOT EXISTS mgj_member_education_history (
    id                  SERIAL PRIMARY KEY,
    member_id           INT NOT NULL REFERENCES mgj_members(id) ON DELETE CASCADE,
    year                INT NOT NULL,
    qualification       VARCHAR(100) NOT NULL,
    qualification_other VARCHAR(200),     -- set only when qualification = 'Others'
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_member_education_history_member
    ON mgj_member_education_history(member_id)
    WHERE deleted_at IS NULL;

COMMIT;

-- Sanity
SELECT column_name, data_type
  FROM information_schema.columns
 WHERE table_schema='mis_azad' AND table_name='mgj_members'
   AND column_name IN ('education_year','is_working')
 ORDER BY column_name;

SELECT column_name, data_type, is_nullable
  FROM information_schema.columns
 WHERE table_schema='mis_azad' AND table_name='mgj_member_education_history'
 ORDER BY ordinal_position;
