-- 022: Add `org_type_other` column to organizations (free text used when org_type = 'Other').
-- Idempotent so it's safe to re-run.

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS org_type_other VARCHAR(200);
