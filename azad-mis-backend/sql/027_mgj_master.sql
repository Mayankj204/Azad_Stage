-- 027: MGJ-only Master setup — fully isolated from FLP geography/batch tables.
--
-- Tables created here intentionally do NOT reference new_states / new_districts /
-- new_centres / new_areas / batches. The MGJ module's Master CRUD reads & writes
-- only its own data so the two programs can evolve their geography and batches
-- independently.

-- IMPORTANT: pin the schema so tables are created in mis_azad regardless of the
-- caller's default search_path. The backend connects with search_path
-- "mis_azad, public", so the tables MUST exist in mis_azad.
SET search_path TO mis_azad, public;

-- ---------- States ----------
CREATE TABLE IF NOT EXISTS mgj_states (
  state_code   VARCHAR(10) PRIMARY KEY,
  state_name   VARCHAR(150) NOT NULL,
  status       VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by   INT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  deleted_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_states_name_active
  ON mgj_states (LOWER(state_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_states_status     ON mgj_states(status);
CREATE INDEX IF NOT EXISTS idx_mgj_states_deleted_at ON mgj_states(deleted_at);


-- ---------- Districts ----------
CREATE TABLE IF NOT EXISTS mgj_districts (
  district_code  VARCHAR(20) PRIMARY KEY,
  district_name  VARCHAR(150) NOT NULL,
  state_code     VARCHAR(10) NOT NULL REFERENCES mgj_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_districts_name_per_state
  ON mgj_districts (state_code, LOWER(district_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_districts_state      ON mgj_districts(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_districts_status     ON mgj_districts(status);
CREATE INDEX IF NOT EXISTS idx_mgj_districts_deleted_at ON mgj_districts(deleted_at);


-- ---------- Centres ----------
CREATE TABLE IF NOT EXISTS mgj_centres (
  centre_code    VARCHAR(20) PRIMARY KEY,
  centre_name    VARCHAR(150) NOT NULL,
  district_code  VARCHAR(20) NOT NULL REFERENCES mgj_districts(district_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  state_code     VARCHAR(10) NOT NULL REFERENCES mgj_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_centres_name_per_district
  ON mgj_centres (district_code, LOWER(centre_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_centres_district   ON mgj_centres(district_code);
CREATE INDEX IF NOT EXISTS idx_mgj_centres_state      ON mgj_centres(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_centres_status     ON mgj_centres(status);
CREATE INDEX IF NOT EXISTS idx_mgj_centres_deleted_at ON mgj_centres(deleted_at);


-- ---------- Areas ----------
CREATE TABLE IF NOT EXISTS mgj_areas (
  area_code      VARCHAR(30) PRIMARY KEY,
  area_name      VARCHAR(150) NOT NULL,
  centre_code    VARCHAR(20) NOT NULL REFERENCES mgj_centres(centre_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  district_code  VARCHAR(20) NOT NULL REFERENCES mgj_districts(district_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  state_code     VARCHAR(10) NOT NULL REFERENCES mgj_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_areas_name_per_centre
  ON mgj_areas (centre_code, LOWER(area_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_areas_centre     ON mgj_areas(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_areas_district   ON mgj_areas(district_code);
CREATE INDEX IF NOT EXISTS idx_mgj_areas_state      ON mgj_areas(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_areas_status     ON mgj_areas(status);
CREATE INDEX IF NOT EXISTS idx_mgj_areas_deleted_at ON mgj_areas(deleted_at);


-- ---------- Batches ----------
CREATE TABLE IF NOT EXISTS mgj_master_batches (
  id            SERIAL PRIMARY KEY,
  batch_code    VARCHAR(30),
  name          VARCHAR(100) NOT NULL,
  year          VARCHAR(20),
  state_code    VARCHAR(10) REFERENCES mgj_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  centre_code   VARCHAR(20) REFERENCES mgj_centres(centre_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status        VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by    INT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  deleted_at    TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_master_batches_name_per_centre
  ON mgj_master_batches (centre_code, LOWER(name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_master_batches_centre     ON mgj_master_batches(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_batches_state      ON mgj_master_batches(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_batches_status     ON mgj_master_batches(status);
CREATE INDEX IF NOT EXISTS idx_mgj_master_batches_deleted_at ON mgj_master_batches(deleted_at);
