-- 039: AK-only Master geography — fully independent of MGJ + FLP.
--
-- Mirrors the MGJ 4-tier hierarchy (State → District → Centre → Area)
-- but in its own table family with NO cross-references to mgj_states /
-- mgj_districts / mgj_centres / mgj_areas / new_states / new_districts /
-- new_centres / new_areas.
--
-- Strategy:
--   1. Upgrade existing ak_states  (currently bare-bones) with full set of
--      timestamps + soft-delete column.
--   2. Create ak_districts (new).
--   3. Upgrade existing ak_centres with district_code FK + timestamps +
--      soft-delete column.
--   4. Backfill: create a "<State> (Default)" district per existing state
--      so the 7 existing centres can satisfy NOT-NULL district_code without
--      a separate manual reassignment step. Admins can rename / split
--      these later from the management UI.
--   5. Create ak_areas (new).
SET search_path TO mis_azad, public;

-- ---------- (1) States: add metadata columns ----------
ALTER TABLE ak_states
  ADD COLUMN IF NOT EXISTS created_by INT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ak_states_name_active
  ON ak_states (LOWER(state_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_states_status     ON ak_states(status);
CREATE INDEX IF NOT EXISTS idx_ak_states_deleted_at ON ak_states(deleted_at);


-- ---------- (2) Districts: new table ----------
CREATE TABLE IF NOT EXISTS ak_districts (
  district_code  VARCHAR(20) PRIMARY KEY,
  district_name  VARCHAR(150) NOT NULL,
  state_code     VARCHAR(10) NOT NULL REFERENCES ak_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ak_districts_name_per_state
  ON ak_districts (state_code, LOWER(district_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_districts_state      ON ak_districts(state_code);
CREATE INDEX IF NOT EXISTS idx_ak_districts_status     ON ak_districts(status);
CREATE INDEX IF NOT EXISTS idx_ak_districts_deleted_at ON ak_districts(deleted_at);


-- ---------- (3) Centres: add district_code + metadata ----------
ALTER TABLE ak_centres
  ADD COLUMN IF NOT EXISTS district_code VARCHAR(20),
  ADD COLUMN IF NOT EXISTS created_by    INT,
  ADD COLUMN IF NOT EXISTS created_at    TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS deleted_at    TIMESTAMPTZ;


-- ---------- (4) Backfill default districts so existing centres satisfy
--                NOT-NULL when we tighten district_code below. ----------
INSERT INTO ak_districts (district_code, district_name, state_code, status)
SELECT s.state_code || '_DEFAULT',
       COALESCE(s.state_name, s.state_code) || ' (Default)',
       s.state_code,
       'Active'
FROM ak_states s
WHERE NOT EXISTS (
  SELECT 1 FROM ak_districts d WHERE d.state_code = s.state_code
);

UPDATE ak_centres
   SET district_code = state_code || '_DEFAULT'
 WHERE district_code IS NULL
   AND state_code IS NOT NULL;


-- Tighten constraints on ak_centres now that backfill is done.
-- Use a DO block so re-runs are idempotent: ALTER ... SET NOT NULL fails
-- if the column is already NOT NULL.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mis_azad' AND table_name='ak_centres'
      AND column_name='district_code' AND is_nullable='YES'
  ) THEN
    ALTER TABLE ak_centres ALTER COLUMN district_code SET NOT NULL;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ak_centres_district_code_fkey'
  ) THEN
    ALTER TABLE ak_centres
      ADD CONSTRAINT ak_centres_district_code_fkey
      FOREIGN KEY (district_code) REFERENCES ak_districts(district_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ak_centres_name_per_district
  ON ak_centres (district_code, LOWER(centre_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_centres_district   ON ak_centres(district_code);
CREATE INDEX IF NOT EXISTS idx_ak_centres_state      ON ak_centres(state_code);
CREATE INDEX IF NOT EXISTS idx_ak_centres_status     ON ak_centres(status);
CREATE INDEX IF NOT EXISTS idx_ak_centres_deleted_at ON ak_centres(deleted_at);


-- ---------- (5) Areas: new table ----------
CREATE TABLE IF NOT EXISTS ak_areas (
  area_code      VARCHAR(30) PRIMARY KEY,
  area_name      VARCHAR(150) NOT NULL,
  centre_code    VARCHAR(20) NOT NULL REFERENCES ak_centres(centre_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  district_code  VARCHAR(20) NOT NULL REFERENCES ak_districts(district_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  state_code     VARCHAR(10) NOT NULL REFERENCES ak_states(state_code) ON UPDATE CASCADE ON DELETE RESTRICT,
  status         VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
  created_by     INT,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  deleted_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ak_areas_name_per_centre
  ON ak_areas (centre_code, LOWER(area_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_areas_centre     ON ak_areas(centre_code);
CREATE INDEX IF NOT EXISTS idx_ak_areas_district   ON ak_areas(district_code);
CREATE INDEX IF NOT EXISTS idx_ak_areas_state      ON ak_areas(state_code);
CREATE INDEX IF NOT EXISTS idx_ak_areas_status     ON ak_areas(status);
CREATE INDEX IF NOT EXISTS idx_ak_areas_deleted_at ON ak_areas(deleted_at);
