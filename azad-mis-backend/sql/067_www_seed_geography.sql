-- 067: Seed the WWW geography tables so the Add Trainee and Enrollment
-- List dropdowns have data to show.
--
-- Phase 3 of the WWW backend created www_states / www_districts /
-- www_centres / www_areas / www_master_batches with full structure but
-- zero rows.  This migration adds the standard 4-state set the rest of
-- the WWW UI mocks reference (Delhi / Rajasthan / Tamil Nadu / West
-- Bengal) plus enough districts, centres, areas and batches that
-- the cascading dropdowns produce visible options at every step.
--
-- All inserts are idempotent so re-running the file is safe:
--   * fixed-code rows use ON CONFLICT (...) DO NOTHING on the PK
--   * batches (SERIAL id) use INSERT ... SELECT ... WHERE NOT EXISTS
--
-- Naming conventions:
--   state_code     short 2-3 char code (DEL / RAJ / TN / WB)
--   district_code  "{state_code}-{abbr}" (e.g. DEL-N, RAJ-JAI)
--   centre_code    "{district_abbr}-C{n}" (e.g. ND-C1)
--   area_code      "{centre_code}-A{n}" (e.g. ND-C1-A1)

SET search_path TO mis_azad, public;


-- ============================================================
-- States
-- ============================================================
INSERT INTO www_states (state_code, state_name) VALUES
  ('DEL', 'Delhi'),
  ('RAJ', 'Rajasthan'),
  ('TN',  'Tamil Nadu'),
  ('WB',  'West Bengal')
ON CONFLICT (state_code) DO NOTHING;


-- ============================================================
-- Districts (parent: state_code)
-- ============================================================
INSERT INTO www_districts (district_code, district_name, state_code) VALUES
  ('DEL-N',   'North Delhi',    'DEL'),
  ('DEL-S',   'South Delhi',    'DEL'),
  ('DEL-E',   'East Delhi',     'DEL'),
  ('DEL-W',   'West Delhi',     'DEL'),
  ('RAJ-JAI', 'Jaipur',         'RAJ'),
  ('RAJ-JOD', 'Jodhpur',        'RAJ'),
  ('TN-CHN',  'Chennai',        'TN'),
  ('TN-COI',  'Coimbatore',     'TN'),
  ('WB-KOL',  'Kolkata',        'WB'),
  ('WB-HOW',  'Howrah',         'WB')
ON CONFLICT (district_code) DO NOTHING;


-- ============================================================
-- Centres (parent: district_code + state_code denormalized)
-- ============================================================
INSERT INTO www_centres (centre_code, centre_name, district_code, state_code) VALUES
  ('ND-C1', 'North Delhi Centre',  'DEL-N',   'DEL'),
  ('SD-C1', 'South Delhi Centre',  'DEL-S',   'DEL'),
  ('ED-C1', 'East Delhi Centre',   'DEL-E',   'DEL'),
  ('WD-C1', 'West Delhi Centre',   'DEL-W',   'DEL'),
  ('JP-C1', 'Jaipur Centre',       'RAJ-JAI', 'RAJ'),
  ('JD-C1', 'Jodhpur Centre',      'RAJ-JOD', 'RAJ'),
  ('CH-C1', 'Chennai Centre',      'TN-CHN',  'TN'),
  ('CB-C1', 'Coimbatore Centre',   'TN-COI',  'TN'),
  ('KK-C1', 'Kolkata Centre',      'WB-KOL',  'WB'),
  ('HW-C1', 'Howrah Centre',       'WB-HOW',  'WB')
ON CONFLICT (centre_code) DO NOTHING;


-- ============================================================
-- Areas (parent: centre_code; district_code + state_code denormalized)
-- ============================================================
INSERT INTO www_areas (area_code, area_name, centre_code, district_code, state_code) VALUES
  ('ND-C1-A1', 'Karol Bagh',    'ND-C1', 'DEL-N',   'DEL'),
  ('ND-C1-A2', 'Civil Lines',   'ND-C1', 'DEL-N',   'DEL'),
  ('SD-C1-A1', 'Saket',         'SD-C1', 'DEL-S',   'DEL'),
  ('SD-C1-A2', 'Lajpat Nagar',  'SD-C1', 'DEL-S',   'DEL'),
  ('JP-C1-A1', 'Malviya Nagar', 'JP-C1', 'RAJ-JAI', 'RAJ'),
  ('CH-C1-A1', 'T Nagar',       'CH-C1', 'TN-CHN',  'TN'),
  ('KK-C1-A1', 'Salt Lake',     'KK-C1', 'WB-KOL',  'WB')
ON CONFLICT (area_code) DO NOTHING;


-- ============================================================
-- Master batches (SERIAL id, so INSERT-SELECT with WHERE NOT EXISTS)
-- ============================================================
INSERT INTO www_master_batches (name, year, state_code, centre_code)
SELECT * FROM (VALUES
  ('Batch 1', '2025-26', 'DEL', 'ND-C1'),
  ('Batch 2', '2025-26', 'DEL', 'ND-C1'),
  ('Batch 1', '2025-26', 'DEL', 'SD-C1'),
  ('Batch 1', '2025-26', 'RAJ', 'JP-C1'),
  ('Batch 1', '2025-26', 'TN',  'CH-C1'),
  ('Batch 1', '2025-26', 'WB',  'KK-C1')
) AS v(name, year, state_code, centre_code)
WHERE NOT EXISTS (
  SELECT 1 FROM www_master_batches b
  WHERE b.centre_code = v.centre_code
    AND LOWER(b.name) = LOWER(v.name)
    AND b.deleted_at IS NULL
);
