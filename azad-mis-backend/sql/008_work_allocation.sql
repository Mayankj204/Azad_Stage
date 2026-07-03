-- 008_work_allocation.sql
-- Work Allocation & Centre-Level Target Tracking

-- Target categories enum
CREATE TYPE target_category_enum AS ENUM (
  'coverage', 'www_program', 'outreach', 'citizenship_docs',
  'social_security', 'gbv', 'community_action'
);

-- Quarterly targets per centre
CREATE TABLE centre_targets (
  id SERIAL PRIMARY KEY,
  centre_id INTEGER NOT NULL REFERENCES centres(id),
  financial_year VARCHAR(10) NOT NULL,
  quarter VARCHAR(2) NOT NULL,
  category target_category_enum NOT NULL,
  metric_key VARCHAR(50) NOT NULL,
  target_value INTEGER NOT NULL DEFAULT 0,
  created_by INTEGER REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(centre_id, financial_year, quarter, metric_key)
);

CREATE INDEX idx_centre_targets_lookup
  ON centre_targets(centre_id, financial_year, quarter);
