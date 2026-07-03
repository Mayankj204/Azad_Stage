-- 020: MGJ (Men with Gender Justice) Module Table
-- Creates the mgj_members table required by routes/mgj.py.
-- Run against mis_azad schema.

CREATE TABLE IF NOT EXISTS mgj_members (
  id SERIAL PRIMARY KEY,
  enrollment_number VARCHAR(80) UNIQUE,
  photo_url VARCHAR(500),

  -- Basic Profile
  name VARCHAR(200) NOT NULL,
  surname VARCHAR(200),
  date_of_birth DATE,
  age_at_enrollment INT,
  mobile VARCHAR(15),
  email VARCHAR(200),
  address TEXT,
  permanent_address TEXT,

  state_code VARCHAR(10),
  district_code VARCHAR(20),
  centre_code VARCHAR(20),
  area_code VARCHAR(30),
  group_number VARCHAR(50),
  batch_id INT,

  caste_category VARCHAR(100),
  community_religion VARCHAR(100),
  gender VARCHAR(50),
  social_media_account VARCHAR(20),
  social_media_details VARCHAR(300),
  marital_status VARCHAR(30),
  age_at_marriage INT,
  number_of_children INT,

  -- Family Details
  family_members_count INT,
  earning_members INT,
  monthly_family_income NUMERIC(12, 2),
  per_capita_income NUMERIC(12, 2),
  women_below_18 INT,
  men_below_18 INT,
  women_above_18 INT,
  men_above_18 INT,
  women_in_azad VARCHAR(10),
  women_in_azad_relation VARCHAR(200),
  men_in_azad VARCHAR(10),
  men_in_azad_relation VARCHAR(200),

  -- Education
  education VARCHAR(100),
  education_other VARCHAR(200),
  still_studying VARCHAR(10),
  studying_what VARCHAR(200),

  -- Work
  career_status VARCHAR(100),
  work_nature VARCHAR(500),
  work_place VARCHAR(200),
  monthly_income NUMERIC(12, 2),
  future_goal VARCHAR(500),
  occupation VARCHAR(200),

  -- Extra
  how_know_azad VARCHAR(500),
  why_join_mgj TEXT,
  challenges TEXT,

  status VARCHAR(20) DEFAULT 'Active',
  created_by INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_members_state_code ON mgj_members(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_members_centre_code ON mgj_members(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_members_district_code ON mgj_members(district_code);
CREATE INDEX IF NOT EXISTS idx_mgj_members_status ON mgj_members(status);
CREATE INDEX IF NOT EXISTS idx_mgj_members_deleted_at ON mgj_members(deleted_at);
CREATE INDEX IF NOT EXISTS idx_mgj_members_name ON mgj_members(name);
