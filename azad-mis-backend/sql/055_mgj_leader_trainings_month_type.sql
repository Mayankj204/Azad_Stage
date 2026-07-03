-- 055_mgj_leader_trainings_month_type.sql
-- 2026-06-01: MGJ Leader Training "Add Training" form now collects two
-- new required fields per user spec:
--   * Month            (one of 12 month names)
--   * Type of Training (Leadership Training / Refresher Training /
--                       Community Social Action Training)
--
-- Backend pydantic + INSERT/UPDATE were extended in routes/mgj_leader_training.py
-- this migration adds the two columns. Both nullable so existing rows survive.

ALTER TABLE mgj_leader_trainings
    ADD COLUMN IF NOT EXISTS month             VARCHAR(20),
    ADD COLUMN IF NOT EXISTS type_of_training  VARCHAR(64);

-- Soft sanity comment — values are validated app-side against fixed whitelists.
COMMENT ON COLUMN mgj_leader_trainings.month            IS 'January..December (validated app-side).';
COMMENT ON COLUMN mgj_leader_trainings.type_of_training IS 'Leadership Training | Refresher Training | Community Social Action Training (validated app-side).';
