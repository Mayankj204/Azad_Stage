-- 065: WWW Master geography Phase 2 — Areas + Master Batches.
--
-- Builds on 064_www_master_geography.sql (which created www_states /
-- www_districts / www_centres).  Adds:
--   * www_areas         — 4th tier of the geo hierarchy (under centre)
--   * www_master_batches — master batch registry, scoped by centre
--
-- Mirrors the MGJ layout (mgj_areas + mgj_master_batches) exactly so
-- the CRUD route patterns stay clone-friendly.  Same conventions:
--   * code/name/status + audit (created_by, created_at, updated_at)
--   * soft-delete via deleted_at
--   * unique-per-parent name indexes scoped to non-deleted rows
--   * FK ON UPDATE CASCADE (admins can rename parent codes in-place)
--   * FK ON DELETE RESTRICT (children can't be orphaned by accident)
--
-- Stays fully independent of FLP / MGJ / AK — no cross-table FKs.
SET search_path TO mis_azad, public;


-- ---------- Areas ----------
CREATE TABLE IF NOT EXISTS www_areas (
  area_code      VARCHAR(30) PRIMARY KEY,
  area_name      VARCHAR(150) NOT NULL,
  centre_code    VARCHAR(20) NOT NULL REFERENCES www_centres(centre_code)   ON UPDATE CASCADE ON DELETE RESTRICT,
  district_code  VARCHAR(20) NOT NULL REFERENCES www_districts(district_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  state_code     VARCHAR(10) NOT NULL REFERENCES www_states(state_code)       ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_www_areas_name_per_centre
  ON www_areas (centre_code, LOWER(area_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_www_areas_centre     ON www_areas(centre_code);
CREATE INDEX IF NOT EXISTS idx_www_areas_district   ON www_areas(district_code);
CREATE INDEX IF NOT EXISTS idx_www_areas_state      ON www_areas(state_code);
CREATE INDEX IF NOT EXISTS idx_www_areas_status     ON www_areas(status);
CREATE INDEX IF NOT EXISTS idx_www_areas_deleted_at ON www_areas(deleted_at);


-- ---------- Master Batches ----------
-- NOTE: state_code and centre_code are nullable here (matches the MGJ
-- table shape after the 2026-06-10 stage change that removed the
-- Centre field from the MGJ Add-Batch modal) — admins may create a
-- batch with only a name + year, and attach centre later.  We can
-- tighten to NOT NULL in a future migration if business rules change.
CREATE TABLE IF NOT EXISTS www_master_batches (
  id            SERIAL PRIMARY KEY,
  batch_code    VARCHAR(30),
  name          VARCHAR(100) NOT NULL,
  year          VARCHAR(20),
  state_code    VARCHAR(10) REFERENCES www_states(state_code)   ON UPDATE CASCADE ON DELETE RESTRICT,
  centre_code   VARCHAR(20) REFERENCES www_centres(centre_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status        VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by    INT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  deleted_at    TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_www_master_batches_name_per_centre
  ON www_master_batches (centre_code, LOWER(name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_www_master_batches_centre     ON www_master_batches(centre_code);
CREATE INDEX IF NOT EXISTS idx_www_master_batches_state      ON www_master_batches(state_code);
CREATE INDEX IF NOT EXISTS idx_www_master_batches_status     ON www_master_batches(status);
CREATE INDEX IF NOT EXISTS idx_www_master_batches_deleted_at ON www_master_batches(deleted_at);
