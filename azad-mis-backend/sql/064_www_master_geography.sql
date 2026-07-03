-- 064: WWW-only Master geography — fully independent of FLP / MGJ / AK.
--
-- This file lays the foundation for the WWW (Women with Wheels) module's
-- backend.  WWW gets its own table family with NO cross-references to
-- new_states / new_districts / new_centres   (FLP),
-- mgj_states / mgj_districts / mgj_centres  (MGJ), or
-- ak_states  / ak_districts  / ak_centres   (AK).
--
-- Hierarchy: State -> District -> Centre.  Areas + master batches will be
-- added in a follow-up migration after the basic geo is approved.
--
-- Shape mirrors the MGJ master tables (027_mgj_master.sql) exactly so the
-- CRUD route patterns can be cloned with minimal changes:
--   * code/name/status + audit (created_by, created_at, updated_at)
--   * soft-delete via deleted_at
--   * unique-per-parent name indexes scoped to non-deleted rows
--   * FK ON UPDATE CASCADE so admins can rename a parent code in-place
--   * FK ON DELETE RESTRICT so accidental hard-deletes can't orphan children
--
-- IMPORTANT: pin the schema so tables are created in mis_azad regardless
-- of the caller's default search_path. The backend connects with
-- search_path "mis_azad, public", so the tables MUST exist in mis_azad.
SET search_path TO mis_azad, public;

-- ---------- States ----------
CREATE TABLE IF NOT EXISTS www_states (
  state_code   VARCHAR(10) PRIMARY KEY,
  state_name   VARCHAR(150) NOT NULL,
  status       VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by   INT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  deleted_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_www_states_name_active
  ON www_states (LOWER(state_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_www_states_status     ON www_states(status);
CREATE INDEX IF NOT EXISTS idx_www_states_deleted_at ON www_states(deleted_at);


-- ---------- Districts ----------
CREATE TABLE IF NOT EXISTS www_districts (
  district_code  VARCHAR(20) PRIMARY KEY,
  district_name  VARCHAR(150) NOT NULL,
  state_code     VARCHAR(10) NOT NULL REFERENCES www_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_www_districts_name_per_state
  ON www_districts (state_code, LOWER(district_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_www_districts_state      ON www_districts(state_code);
CREATE INDEX IF NOT EXISTS idx_www_districts_status     ON www_districts(status);
CREATE INDEX IF NOT EXISTS idx_www_districts_deleted_at ON www_districts(deleted_at);


-- ---------- Centres ----------
CREATE TABLE IF NOT EXISTS www_centres (
  centre_code    VARCHAR(20) PRIMARY KEY,
  centre_name    VARCHAR(150) NOT NULL,
  district_code  VARCHAR(20) NOT NULL REFERENCES www_districts(district_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  state_code     VARCHAR(10) NOT NULL REFERENCES www_states(state_code)       ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_www_centres_name_per_district
  ON www_centres (district_code, LOWER(centre_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_www_centres_district   ON www_centres(district_code);
CREATE INDEX IF NOT EXISTS idx_www_centres_state      ON www_centres(state_code);
CREATE INDEX IF NOT EXISTS idx_www_centres_status     ON www_centres(status);
CREATE INDEX IF NOT EXISTS idx_www_centres_deleted_at ON www_centres(deleted_at);
