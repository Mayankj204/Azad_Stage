-- AAG AGM (Annual General Meeting records under the AK Alumni group).
-- Single flat table — one row per meeting.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_alumni_agm (
  id            SERIAL PRIMARY KEY,
  year          VARCHAR(20) NOT NULL,
  topic         TEXT NOT NULL,
  agm_date      DATE NOT NULL,
  participants  INTEGER NOT NULL,
  status        VARCHAR(20) DEFAULT 'Active',
  deleted_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  created_by    VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ak_alumni_agm_year ON ak_alumni_agm(year)     WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_alumni_agm_date ON ak_alumni_agm(agm_date) WHERE deleted_at IS NULL;
