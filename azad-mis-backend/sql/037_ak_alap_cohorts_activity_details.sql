-- Per-type Activity bundle (Topic / Details / Date for each checked Type).
-- Same pattern as ak_alap_trainings.type_details. Keyed by type label —
-- e.g. {"Monthly Session on SRHR/GBV": {"topic": "...", "details": "...",
-- "date": "..."}, "Campaign": {...}}.
SET search_path TO mis_azad, public;

ALTER TABLE ak_alap_cohorts
  ADD COLUMN IF NOT EXISTS activity_details JSONB NOT NULL DEFAULT '{}'::jsonb;
