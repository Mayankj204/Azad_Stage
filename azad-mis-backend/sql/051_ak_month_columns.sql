-- 2026-05-30: Add reporting Month + multi-leader columns per user request.
--
-- ak_trainings.training_month
--   Free-form month label (January..December) chosen on the Add Training
--   form. Distinct from training_date so the user can categorise a training
--   into a different reporting month than its literal date.
--
-- ak_adda_details.detail_month
--   Same idea, on the Adda Add-Details popup.
--
-- ak_adda_details.attended_leader_ids
--   JSONB array of ak_leaders.id ints — atomic on-row storage of the
--   leaders who attended this specific adda monthly meeting. Stored as
--   a list rather than a junction table because:
--     - lookups are read-mostly and per-detail (small N)
--     - we avoid touching ak_leaders ↔ ak_adda_details FK plumbing
--     - JSONB supports cheap `?` / `@>` membership checks for future filters
--   Default to '[]' so existing rows behave as "no attendees recorded".
--
-- All additions are idempotent (IF NOT EXISTS) so re-running the migration
-- on a partially-applied stage / live DB is safe.

ALTER TABLE ak_trainings
  ADD COLUMN IF NOT EXISTS training_month VARCHAR(20);

ALTER TABLE ak_adda_details
  ADD COLUMN IF NOT EXISTS detail_month VARCHAR(20);

ALTER TABLE ak_adda_details
  ADD COLUMN IF NOT EXISTS attended_leader_ids JSONB DEFAULT '[]'::jsonb;
