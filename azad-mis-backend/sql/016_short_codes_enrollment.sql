-- Migration 016: Add short_code to states, districts, cities; education_other to flps
-- Date: 2026-03-06

-- Add short_code columns
ALTER TABLE states ADD COLUMN IF NOT EXISTS short_code VARCHAR(10);
ALTER TABLE districts ADD COLUMN IF NOT EXISTS short_code VARCHAR(10);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS short_code VARCHAR(10);

-- Add education_other to flps
ALTER TABLE flps ADD COLUMN IF NOT EXISTS education_other VARCHAR(200);

-- Seed initial short codes for existing states
UPDATE states SET short_code = 'DL' WHERE name = 'Delhi' AND short_code IS NULL;
UPDATE states SET short_code = 'WB' WHERE name = 'West Bengal' AND short_code IS NULL;
UPDATE states SET short_code = 'RJ' WHERE name = 'Rajasthan' AND short_code IS NULL;
UPDATE states SET short_code = 'TN' WHERE name = 'Tamil Nadu' AND short_code IS NULL;

-- Seed initial short codes for existing districts
UPDATE districts SET short_code = 'SD' WHERE name = 'South Delhi' AND short_code IS NULL;
UPDATE districts SET short_code = 'ND' WHERE name = 'North Delhi' AND short_code IS NULL;
UPDATE districts SET short_code = 'ED' WHERE name = 'East Delhi' AND short_code IS NULL;
UPDATE districts SET short_code = 'NWD' WHERE name = 'New Delhi' AND short_code IS NULL;
UPDATE districts SET short_code = 'N24' WHERE name = 'North 24 Parganas' AND short_code IS NULL;
UPDATE districts SET short_code = 'S24' WHERE name = 'South 24 Parganas' AND short_code IS NULL;
UPDATE districts SET short_code = 'JP' WHERE name = 'Jaipur' AND short_code IS NULL;
UPDATE districts SET short_code = 'CH' WHERE name = 'Chennai' AND short_code IS NULL;
