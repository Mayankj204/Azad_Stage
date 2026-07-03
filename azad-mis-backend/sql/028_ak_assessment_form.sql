-- 028: Extend ak_assessments to store baseline / midline / endline responses,
-- and add a child table for family-member rows (Family tab).
-- Pin schema so it does not depend on caller's search_path.
SET search_path TO mis_azad, public;

-- Per-tab response blob (q_number -> answer). The 8 tabs are:
--   General Info / Family / Marriage & Aspirations / Sexual & Reproductive Health /
--   Gender Norms / Mobility / Self Efficacy / Digital Literacy
-- Storing as a single JSONB keeps schema-evolution painless when the question
-- bank changes. Family-member rows live in their own normalised table.
ALTER TABLE ak_assessments
  ADD COLUMN IF NOT EXISTS responses    JSONB         DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ   DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_tab     VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_ak_assessments_leader  ON ak_assessments(leader_id);
CREATE INDEX IF NOT EXISTS idx_ak_assessments_status  ON ak_assessments(status);
CREATE INDEX IF NOT EXISTS idx_ak_assessments_type    ON ak_assessments(assessment_type);

-- Family Details tab -- up to 5 family members per assessment.
CREATE TABLE IF NOT EXISTS ak_assessment_family_members (
  id              SERIAL PRIMARY KEY,
  assessment_id   INT NOT NULL REFERENCES ak_assessments(id) ON DELETE CASCADE,
  position        INT NOT NULL CHECK (position BETWEEN 1 AND 10),  -- room to grow beyond 5
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
CREATE INDEX IF NOT EXISTS idx_ak_asmt_family_assessment ON ak_assessment_family_members(assessment_id);
