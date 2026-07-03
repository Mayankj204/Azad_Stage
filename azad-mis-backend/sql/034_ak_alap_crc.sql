-- ALAP CRC (Centre Resource Centre) — monthly programme records run by an
-- ALAP leader. Each CRC has a target, a month, and four programme blocks:
-- Monthly Session with ALAP Adda (with one inline groups table), Library
-- Activity, Sports Session, Educational Capacity Building.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_alap_crc (
  id                SERIAL PRIMARY KEY,
  alap_id           INTEGER NOT NULL REFERENCES ak_alaps(id) ON DELETE CASCADE,
  crc_target        TEXT,
  month             VARCHAR(20),
  -- Monthly Session with ALAP Adda
  monthly_topic     TEXT,
  -- Library Activity
  library_topic     TEXT,
  library_details   TEXT,
  library_date      DATE,
  library_attendance INTEGER,
  -- Sports Session
  sports_details    TEXT,
  sports_date       DATE,
  sports_attendance INTEGER,
  -- Educational Capacity Building
  edu_details        TEXT,
  edu_days_conducted INTEGER,
  edu_attendance     INTEGER,
  status             VARCHAR(20) DEFAULT 'Active',
  deleted_at         TIMESTAMPTZ,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  created_by         VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ak_alap_crc_alap   ON ak_alap_crc(alap_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_alap_crc_month  ON ak_alap_crc(month)   WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS ak_alap_crc_groups (
  id          SERIAL PRIMARY KEY,
  crc_id      INTEGER NOT NULL REFERENCES ak_alap_crc(id) ON DELETE CASCADE,
  group_no    VARCHAR(20),
  group_name  VARCHAR(200),
  attendance  INTEGER,
  sort_order  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ak_alap_crc_groups_crc ON ak_alap_crc_groups(crc_id);
