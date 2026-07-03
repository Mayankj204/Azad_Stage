-- 032: MGJ Alumni — separate from leaders/members. Captures Basic Info,
-- Milestone (alumni meet / campaign / session) and Stories of Change.
-- Geo references mgj_states / mgj_centres / mgj_areas via *_code.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS mgj_alumni (
  id SERIAL PRIMARY KEY,

  -- ===== Basic Information =====
  name                       VARCHAR(255) NOT NULL,
  batch                      VARCHAR(100),
  age                        INT,
  state_code                 VARCHAR(10),
  centre_code                VARCHAR(20),
  area_code                  VARCHAR(20),
  address                    TEXT,
  mobile_no                  VARCHAR(15),
  education_level            VARCHAR(50),     -- Uneducated / Highschool / Intermediate / Graduate / Postgraduate / Other
  education_level_other      VARCHAR(255),    -- only when education_level = 'Other'
  family_members_count       INT,
  women_family_members_count INT,
  working_status             VARCHAR(50) NOT NULL,   -- Student / Employed / Self-employed / Unemployed / Other
  working_status_other       VARCHAR(255),    -- only when working_status = 'Other'

  -- ===== Milestone =====
  attended_alumni_meet       VARCHAR(10),     -- 'Yes' / 'No'
  alumni_meet_date           DATE,
  campaign_name              TEXT,
  campaign_date              DATE,
  session_name               TEXT,
  session_date               DATE,

  -- ===== Stories of Change =====
  stories_recorded_date      DATE,
  q1_action_against_violence VARCHAR(10),     -- 'Yes' / 'No'
  q2_joined_community        VARCHAR(10),
  q3_realize_woman           VARCHAR(10),
  q4_think_about_it          TEXT,            -- conditional on q3 = 'Yes'
  q5_shift_self              VARCHAR(10),
  q6_what_shift              TEXT,            -- conditional on q5 = 'Yes'
  q7_affected_personal       VARCHAR(10),
  q8_who_affected            TEXT,            -- conditional on q7 = 'Yes'
  q9_how_affected            TEXT,            -- conditional on q7 = 'Yes'

  -- ===== Audit =====
  created_by   INT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  deleted_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_alumni_state  ON mgj_alumni(state_code) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_alumni_area   ON mgj_alumni(area_code)  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_alumni_centre ON mgj_alumni(centre_code) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_alumni_batch  ON mgj_alumni(batch)      WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_alumni_name   ON mgj_alumni(LOWER(name)) WHERE deleted_at IS NULL;
