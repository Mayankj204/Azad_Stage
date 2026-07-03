-- 2026-05-26
-- MGJ Overall Activities form: WWW – MGJ Linkages now records a 3-stage
-- funnel (Interested → Registered → Enrollment) instead of the old
-- Enabled / Enrollments pair. Also drops 2 Leader-Log fields
-- (Vaccinations Linked, Boys in Unpaid-Care Campaign) from the form.
--
-- Schema change: ADD 3 new integer columns. The 4 old columns
--   (www_enabled_women, www_enrollments,
--    leader_vaccinations, leader_unpaid_care_boys)
-- are LEFT INTACT so existing historical data is preserved — the
-- backend / dashboard simply stop reading + writing to them.

BEGIN;

ALTER TABLE mgj_monthly_activities
    ADD COLUMN IF NOT EXISTS www_women_interested INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS www_women_registered INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS www_women_enrollment INT DEFAULT 0;

COMMIT;

-- Sanity check
SELECT column_name, data_type, column_default
  FROM information_schema.columns
 WHERE table_schema='mis_azad'
   AND table_name='mgj_monthly_activities'
   AND column_name IN ('www_women_interested','www_women_registered','www_women_enrollment')
 ORDER BY column_name;
