-- 044_mgj_members_dropout.sql
-- Adds dropout (walkout) columns to mgj_members so the MGJ view page can
-- mark a member as Dropout the same way FLP and AK already do.
-- Naming mirrors flp_records / ak_leaders for cross-module consistency.

SET search_path TO mis_azad, public;

ALTER TABLE mgj_members
  ADD COLUMN IF NOT EXISTS walkout_date   DATE,
  ADD COLUMN IF NOT EXISTS walkout_reason TEXT;
