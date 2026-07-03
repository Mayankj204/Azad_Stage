-- 050: MGJ Assessment module — mirrors AK assessment table structure
-- (018_azad_kishori.sql + 028_ak_assessment_form.sql combined) but FK'd
-- to mgj_members and operating over the MGJ geo tables.
--
-- The MGJ Assessment workflow is a 3-stage lifecycle:
--   Baseline  → required first
--   Midline   → only available once Baseline is Submitted
--   Endline   → only available once Midline is Submitted (or Baseline if Midline skipped per programme)
--
-- Responses are stored as a single JSONB blob keyed by question number,
-- matching the AK pattern. Schema-evolution is painless that way — the
-- question bank can grow without DDL.
--
-- Pin schema so it does not depend on caller's search_path.
SET search_path TO mis_azad, public;

-- Main assessment record. One row per (member, assessment_type, attempt).
-- A member can have at most one Draft per type at a time; the start
-- endpoint reuses any existing Draft instead of creating a duplicate.
CREATE TABLE IF NOT EXISTS mgj_assessments (
  id              SERIAL PRIMARY KEY,
  member_id       INT NOT NULL REFERENCES mgj_members(id) ON DELETE CASCADE,
  -- Allowed values: 'Baseline', 'Midline', 'Endline' (validated app-side
  -- so we don't need a CHECK that requires a future migration to extend).
  assessment_type VARCHAR(50) NOT NULL,
  state_code      VARCHAR(10),
  centre_code     VARCHAR(20),
  -- Status mirrors AK: 'Draft' while in-progress, 'Submitted' once finalised.
  status          VARCHAR(20)   DEFAULT 'Draft',
  assessment_date DATE,
  responses       JSONB         DEFAULT '{}'::jsonb,
  last_tab        VARCHAR(50),
  started_at      TIMESTAMPTZ   DEFAULT NOW(),
  submitted_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ   DEFAULT NOW(),
  updated_at      TIMESTAMPTZ   DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_assessments_member  ON mgj_assessments(member_id);
CREATE INDEX IF NOT EXISTS idx_mgj_assessments_status  ON mgj_assessments(status);
CREATE INDEX IF NOT EXISTS idx_mgj_assessments_type    ON mgj_assessments(assessment_type);
CREATE INDEX IF NOT EXISTS idx_mgj_assessments_centre  ON mgj_assessments(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_assessments_state   ON mgj_assessments(state_code);

-- Family-member rows captured during the Family tab of the assessment.
-- Same shape as AK's table; up to 10 positions per assessment.
CREATE TABLE IF NOT EXISTS mgj_assessment_family_members (
  id              SERIAL PRIMARY KEY,
  assessment_id   INT NOT NULL REFERENCES mgj_assessments(id) ON DELETE CASCADE,
  position        INT NOT NULL CHECK (position BETWEEN 1 AND 10),
  name            VARCHAR(200),
  relation        VARCHAR(50),
  marital_status  VARCHAR(50),
  age_at_marriage INT,
  education       VARCHAR(50),
  occupation      VARCHAR(100),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (assessment_id, position)
);
CREATE INDEX IF NOT EXISTS idx_mgj_asmt_family_assessment ON mgj_assessment_family_members(assessment_id);
