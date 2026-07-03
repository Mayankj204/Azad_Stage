-- ============================================================================
-- Migration 046: Hindi / Bengali / Tamil columns on the geography masters.
-- ----------------------------------------------------------------------------
-- Background:
--   The mobile FLP survey app supports English / Hindi / Bengali / Tamil.
--   Every label, placeholder and option in the form is already localised,
--   but the State / District / Centre / Area dropdown VALUES come from
--   these geography master tables, which until now stored only the English
--   name. When a surveyor switched the app to Hindi, the dropdowns still
--   showed "East Delhi", "Kailash Nagar" etc. in Latin script.
--
-- Fix:
--   Carry three extra columns per table (name_hi / name_bn / name_ta).
--   The web Add/Edit master form is UNCHANGED — the admin still enters
--   only the English name — and the backend auto-transliterates on save
--   (see new_geography.py POST/PUT handlers, which call into
--   utils_transliterate.transliterate_all()). Existing rows are
--   one-shot-backfilled by scripts/backfill_geo_translations.py.
--
-- Idempotent: every ADD COLUMN uses IF NOT EXISTS, so this migration can
-- be re-applied on databases where some columns already exist.
-- ============================================================================

ALTER TABLE new_states
  ADD COLUMN IF NOT EXISTS state_name_hi TEXT,
  ADD COLUMN IF NOT EXISTS state_name_bn TEXT,
  ADD COLUMN IF NOT EXISTS state_name_ta TEXT;

ALTER TABLE new_districts
  ADD COLUMN IF NOT EXISTS district_name_hi TEXT,
  ADD COLUMN IF NOT EXISTS district_name_bn TEXT,
  ADD COLUMN IF NOT EXISTS district_name_ta TEXT;

ALTER TABLE new_centres
  ADD COLUMN IF NOT EXISTS centre_name_hi TEXT,
  ADD COLUMN IF NOT EXISTS centre_name_bn TEXT,
  ADD COLUMN IF NOT EXISTS centre_name_ta TEXT;

ALTER TABLE new_areas
  ADD COLUMN IF NOT EXISTS area_name_hi TEXT,
  ADD COLUMN IF NOT EXISTS area_name_bn TEXT,
  ADD COLUMN IF NOT EXISTS area_name_ta TEXT;
