-- 031: Add training_type to mgj_leader_topics so topics segregate by training kind.
-- Allowed values today: 'Pakhwada Input', 'Pakhwada Sport', 'Leadership Development'.
SET search_path TO mis_azad, public;

ALTER TABLE mgj_leader_topics
  ADD COLUMN IF NOT EXISTS training_type VARCHAR(50);

-- The old uniqueness was global on LOWER(name). Now the same topic name can exist
-- under different training types (e.g. "Discipline" makes sense under both
-- Leadership Development and Pakhwada Sport), so the uniqueness becomes
-- per (name, training_type).
DROP INDEX IF EXISTS uq_mgj_leader_topics_name;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_leader_topics_name_type
  ON mgj_leader_topics (LOWER(name), COALESCE(training_type, ''))
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_mgj_leader_topics_type
  ON mgj_leader_topics (training_type) WHERE deleted_at IS NULL;
