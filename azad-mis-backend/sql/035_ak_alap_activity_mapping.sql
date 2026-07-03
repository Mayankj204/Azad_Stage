-- ALAP Activity Mapping — one record per (alap_id, month). The `data`
-- JSONB stores all per-category inputs keyed by category index, so adding
-- or reordering categories on the frontend doesn't need a DB migration.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_alap_activity_mapping (
  id          SERIAL PRIMARY KEY,
  alap_id     INTEGER NOT NULL REFERENCES ak_alaps(id) ON DELETE CASCADE,
  month       VARCHAR(20) NOT NULL,
  data        JSONB NOT NULL DEFAULT '{}',
  status      VARCHAR(20) DEFAULT 'Draft',
  deleted_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  created_by  VARCHAR(100)
);

-- Partial unique index: one live record per (alap, month). Soft-deleted
-- rows can co-exist so historical data is recoverable.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ak_alap_activity_mapping_alap_month_live
  ON ak_alap_activity_mapping(alap_id, month) WHERE deleted_at IS NULL;
