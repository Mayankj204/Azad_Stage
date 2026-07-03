-- 018: Azad Kishori (AK) Module Tables
-- Run against mis_azad schema

-- AK Batches (separate from FLP batches)
CREATE TABLE IF NOT EXISTS ak_batches (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  year VARCHAR(20) NOT NULL,
  state_code VARCHAR(10),
  centre_code VARCHAR(20),
  status VARCHAR(20) DEFAULT 'Active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(name, year, state_code, centre_code)
);

-- AK Leaders (profile)
CREATE TABLE IF NOT EXISTS ak_leaders (
  id SERIAL PRIMARY KEY,
  enrollment_number VARCHAR(50) UNIQUE,
  photo_url VARCHAR(500),
  state_code VARCHAR(10),
  centre_code VARCHAR(20),
  batch_id INT REFERENCES ak_batches(id),
  name VARCHAR(200) NOT NULL,
  address TEXT,
  contact_number VARCHAR(15),
  year_of_joining INT,
  dob DATE,
  age INT,
  current_education VARCHAR(50),
  stream_chosen VARCHAR(100),
  stream_other VARCHAR(200),
  category VARCHAR(50),
  category_other VARCHAR(200),
  religion VARCHAR(50),
  religion_other VARCHAR(200),
  gender VARCHAR(50),
  mother_name VARCHAR(200),
  mother_occupation VARCHAR(200),
  father_name VARCHAR(200),
  father_occupation VARCHAR(200),
  family_monthly_income NUMERIC,
  family_members INT,
  per_capita_income NUMERIC,
  status VARCHAR(20) DEFAULT 'Active',
  walkout_date DATE,
  walkout_reason TEXT,
  created_by INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

-- AK Trainings
CREATE TABLE IF NOT EXISTS ak_trainings (
  id SERIAL PRIMARY KEY,
  state_code VARCHAR(10),
  centre_code VARCHAR(20),
  batch_id INT REFERENCES ak_batches(id),
  category VARCHAR(50),
  category_other VARCHAR(200),
  training_date DATE,
  topic_name VARCHAR(500) NOT NULL,
  trainer_name VARCHAR(200),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

-- AK Training Participants
CREATE TABLE IF NOT EXISTS ak_training_participants (
  id SERIAL PRIMARY KEY,
  training_id INT REFERENCES ak_trainings(id) ON DELETE CASCADE,
  leader_id INT REFERENCES ak_leaders(id),
  attendance VARCHAR(20) DEFAULT 'Present',
  UNIQUE(training_id, leader_id)
);

-- AK Training Images
CREATE TABLE IF NOT EXISTS ak_training_images (
  id SERIAL PRIMARY KEY,
  training_id INT REFERENCES ak_trainings(id) ON DELETE CASCADE,
  file_name VARCHAR(500),
  file_path VARCHAR(1000),
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- AK Assessments
CREATE TABLE IF NOT EXISTS ak_assessments (
  id SERIAL PRIMARY KEY,
  leader_id INT REFERENCES ak_leaders(id),
  assessment_type VARCHAR(50),
  state_code VARCHAR(10),
  centre_code VARCHAR(20),
  status VARCHAR(20) DEFAULT 'Draft',
  assessment_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
