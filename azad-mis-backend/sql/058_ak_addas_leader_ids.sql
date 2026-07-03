-- 058_ak_addas_leader_ids.sql
-- 2026-06-04: AK Add Adda form gains multi-select leader support per
-- user spec "Modify Add Adda Form to Support Multiple Leader
-- Selection". A single Adda can now own multiple leaders.
--
-- leader_ids INTEGER[] — array of ak_leaders.id values, ordered by
--   first-pick. Always non-NULL after the backfill for existing rows.
-- leader_id INT — KEPT for backward compatibility. Continues to point
--   at the "primary" leader = leader_ids[1]. Older code paths that
--   read leader_id keep working unchanged.
--
-- Backfill: every existing row with a non-NULL leader_id gets
--   leader_ids = ARRAY[leader_id]. Rows that were already in the
--   awkward "no leader assigned" state stay NULL.

SET search_path TO mis_azad;

ALTER TABLE ak_addas
  ADD COLUMN IF NOT EXISTS leader_ids INTEGER[];

UPDATE ak_addas
  SET leader_ids = ARRAY[leader_id]::INTEGER[]
  WHERE leader_id IS NOT NULL
    AND (leader_ids IS NULL OR leader_ids = '{}'::INTEGER[]);

-- GIN index so the "leader already owns an active Adda" exclusion
-- query (uses ANY / && / UNNEST against leader_ids) stays fast as
-- the table grows.
CREATE INDEX IF NOT EXISTS idx_ak_addas_leader_ids_gin
  ON ak_addas USING GIN (leader_ids)
  WHERE deleted_at IS NULL;
