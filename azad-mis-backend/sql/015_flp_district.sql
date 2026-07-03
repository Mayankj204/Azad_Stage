-- Migration 015: Add district_id to FLPs table
-- Allows tracking which district an FLP operates in

ALTER TABLE flps ADD COLUMN IF NOT EXISTS district_id INT REFERENCES districts(id);
CREATE INDEX IF NOT EXISTS idx_flps_district_id ON flps(district_id);
