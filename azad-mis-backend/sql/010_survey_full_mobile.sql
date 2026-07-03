-- =============================================
-- 010: Full mobile survey support
-- Adds missing columns to surveys table and creates survey_women table
-- =============================================

-- Additional household-level columns from mobile app
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_b_area_other VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_c_caste_other VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_c_community_other VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_earning_members INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_decision_maker_other VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_decision_maker_name VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_occupation VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_native_place VARCHAR(200);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_male_family INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_prefer_boy INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_boys_group INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_female_family INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_prefer_girl INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_age_girl INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS sec_d_women18_count INT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS comment TEXT;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS mobile_local_id VARCHAR(100);

-- Survey women details table (one per 18+ woman in household)
CREATE TABLE IF NOT EXISTS survey_women (
    id SERIAL PRIMARY KEY,
    survey_id INT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    woman_index INT NOT NULL DEFAULT 0,
    name VARCHAR(200),
    contact_no VARCHAR(20),
    age INT,
    marital INT,
    education INT,
    education_other VARCHAR(200),
    living INT,
    living_other VARCHAR(200),
    working INT,
    work_doing VARCHAR(200),
    monthly_income NUMERIC(12,2),
    docs JSONB,
    docs_other VARCHAR(200),
    joining_www INT,
    challenge TEXT,
    training INT,
    eligible INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_survey_women_survey_id ON survey_women(survey_id);
