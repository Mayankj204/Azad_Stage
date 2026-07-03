-- 056_ak_alumni_capacity_training.sql
-- 2026-06-04: AK Alumni "Capacity Training" dropdown — new field per
-- user spec "Add Capacity Training Dropdown in Alumni Module".
--
-- capacity_training        — one of: 'Feminist Way of Mentoring',
--                                    'Community Mobilization',
--                                    'Perspective Building on Adolescents',
--                                    'Other'.
-- other_capacity_training  — free text, populated only when
--                            capacity_training = 'Other'. Trimmed +
--                            capped at 100 chars on the frontend.
--
-- Both columns nullable so existing rows stay valid. Frontend marks
-- the field required at SUBMIT time (new records only) — the backend
-- inline-edit endpoint stays permissive of NULLs for these columns.

SET search_path TO mis_azad;

ALTER TABLE ak_alumni
  ADD COLUMN IF NOT EXISTS capacity_training       VARCHAR(80),
  ADD COLUMN IF NOT EXISTS other_capacity_training VARCHAR(100);
