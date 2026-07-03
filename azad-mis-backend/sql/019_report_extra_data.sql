-- 019: Add extra_data JSONB column to centre_reports for storing
-- sub-parameter values, dynamic row details (Book Reading descriptions,
-- Personal Empowerment entries, Community Action projects, etc.) and
-- optional parent-row descriptions (Community Meeting, Opened Bank Account).
--
-- Shape of extra_data payload:
--   { "description": "optional text (for number_with_desc metrics)",
--     "rows": [ { ...per-field values per dynamicFields schema... } ] }
--
-- Safe/idempotent.

ALTER TABLE centre_reports
    ADD COLUMN IF NOT EXISTS extra_data JSONB;

-- Helpful index for querying non-empty dynamic rows by metric_key/month
CREATE INDEX IF NOT EXISTS idx_centre_reports_extra_data
    ON centre_reports ((extra_data IS NOT NULL));
