-- 045_internship_report_employment.sql
-- Adds two outcome-tracking columns to internship_reports so FLPs can
-- record whether the internship led to employment, and the resulting
-- monthly salary. Both nullable — older reports stay valid.

SET search_path TO mis_azad, public;

ALTER TABLE internship_reports
  ADD COLUMN IF NOT EXISTS employed_after  VARCHAR(10),   -- 'Yes' / 'No'
  ADD COLUMN IF NOT EXISTS monthly_salary  NUMERIC(12, 2);
