-- 007_mobile_enhancements.sql
-- Mobile app enhancements: GPS on surveys, language preference for FLPs

-- Add latitude/longitude convenience columns to surveys for mobile submissions.
-- NOTE: The surveys table already has gps_lat / gps_lng (NUMERIC(10,7)).
-- These new DOUBLE PRECISION columns provide the mobile-friendly aliases.
-- The mobile API populates BOTH pairs so either can be queried.
ALTER TABLE surveys
    ADD COLUMN IF NOT EXISTS latitude  DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

-- Language preference for the FLP mobile app (en = English, hi = Hindi, bn = Bengali)
ALTER TABLE flps
    ADD COLUMN IF NOT EXISTS language_preference VARCHAR(5) DEFAULT 'en';
