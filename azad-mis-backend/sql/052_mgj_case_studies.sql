-- 2026-05-30: MGJ Case Studies — first persistent table for the
-- "Case Studies" tab built on top of the SOP-styled storytelling form.
--
-- One row per case study. Narrative fields live in their own columns
-- (instead of a JSONB blob) so the View page can render them
-- individually + filters / future search can hit them with ILIKE.
--
-- attachments_meta is a JSONB array of {name, url, size, mime} objects
-- captured at upload time by /api/mgj/case-studies/{id}/attachment.
-- Keeping it on-row avoids a junction table while still letting us
-- render the attachment chips on the View page.
--
-- Soft-delete via deleted_at — mirrors the rest of the MGJ module.
--
-- Idempotent (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS mgj_case_studies (
  id                  SERIAL PRIMARY KEY,
  member_id           INT REFERENCES mgj_members(id),
  -- Snapshotted denorm so View / List doesn't have to join on every read.
  -- Kept in sync at write time from the picked member row.
  member_name         VARCHAR(200),
  enrollment_number   VARCHAR(80),
  state_code          VARCHAR(10),
  centre_code         VARCHAR(20),
  area_name           VARCHAR(120),
  -- Story metadata
  title               VARCHAR(300) NOT NULL,
  category            VARCHAR(80),
  category_other      VARCHAR(200),
  story_date          DATE,
  period              VARCHAR(120),
  -- Narrative fields (SOP-styled storytelling — see page-mgjAddStory)
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

CREATE INDEX IF NOT EXISTS idx_mgj_case_studies_member  ON mgj_case_studies (member_id);
CREATE INDEX IF NOT EXISTS idx_mgj_case_studies_centre  ON mgj_case_studies (centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_case_studies_state   ON mgj_case_studies (state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_case_studies_status  ON mgj_case_studies (status);
CREATE INDEX IF NOT EXISTS idx_mgj_case_studies_deleted ON mgj_case_studies (deleted_at);
