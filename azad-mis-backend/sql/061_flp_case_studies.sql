-- 2026-06-05: FLP Case Studies — mirrors mgj_case_studies (sql/052)
-- and ak_case_studies (sql/060). FK points at `flps` (the FLP member
-- table). FLP geo uses new_geography (new_states/new_districts/
-- new_centres) so district_code is snapshotted alongside state_code
-- (no Area dimension in FLP).
--
-- One row per case study. Narrative fields as their own columns;
-- attachments_meta is a JSONB array of {name, url, size, mime}.
-- Soft-delete via deleted_at.
--
-- Idempotent (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS flp_case_studies (
  id                  SERIAL PRIMARY KEY,
  flp_id              INT REFERENCES flps(id),
  -- Snapshotted denorm so View / List doesn't have to join on every read.
  -- Kept in sync at write time from the picked flps row.
  member_name         VARCHAR(200),
  enrollment_number   VARCHAR(80),
  state_code          VARCHAR(10),
  district_code       VARCHAR(20),
  centre_code         VARCHAR(20),
  -- Story metadata
  title               VARCHAR(300) NOT NULL,
  category            VARCHAR(80),
  category_other      VARCHAR(200),
  story_date          DATE,
  period              VARCHAR(120),
  -- Narrative fields (SOP-styled storytelling — see page-flpAddStory)
  story               TEXT,
  challenges          TEXT,
  actions             TEXT,
  impact              TEXT,
  quote               TEXT,
  -- Current status / progress
  status              VARCHAR(40) DEFAULT 'Ongoing',
  status_date         DATE,
  status_notes        TEXT,
  -- Internal
  remarks             TEXT,
  photo_url           VARCHAR(500),
  attachments_meta    JSONB DEFAULT '[]'::jsonb,
  -- Audit + soft-delete
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_flp_case_studies_flp      ON flp_case_studies (flp_id);
CREATE INDEX IF NOT EXISTS idx_flp_case_studies_centre   ON flp_case_studies (centre_code);
CREATE INDEX IF NOT EXISTS idx_flp_case_studies_district ON flp_case_studies (district_code);
CREATE INDEX IF NOT EXISTS idx_flp_case_studies_state    ON flp_case_studies (state_code);
CREATE INDEX IF NOT EXISTS idx_flp_case_studies_status   ON flp_case_studies (status);
CREATE INDEX IF NOT EXISTS idx_flp_case_studies_deleted  ON flp_case_studies (deleted_at);
