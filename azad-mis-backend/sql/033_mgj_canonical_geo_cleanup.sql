-- 033: One-time data cleanup — collapse mgj_centres + mgj_areas to canonical
-- Azad ground-truth (3 Delhi centres + Jaipur + 2 Kolkata + Chennai = 7).
-- Repoints every area onto its canonical centre and dedups by area_name.
-- Leaves mgj_states / mgj_districts unchanged. FLP (new_*) tables untouched.

BEGIN;
SET search_path TO mis_azad, public;

-- 0. Mapping table — every duplicate centre_code maps to the canonical one.
CREATE TEMP TABLE _canon_map (src VARCHAR(20) PRIMARY KEY, canon VARCHAR(20)) ON COMMIT DROP;
INSERT INTO _canon_map (src, canon) VALUES
  -- East Delhi family (canonical = S07093B3, district East Delhi, 15 FLPs)
  ('S07093B3','S07093B3'),
  ('S07092B4','S07093B3'),
  ('S07100B5','S07093B3'),
  ('S07099B7','S07093B3'),  -- the "East" typo row
  -- North Delhi family (canonical = S07091B2, district North Delhi, 4 FLPs)
  ('S07091B2','S07091B2'),
  ('S07090B8','S07091B2'),
  -- South Delhi family (canonical = S07098B1, district South Delhi, 47 FLPs)
  ('S07098B1','S07098B1'),
  ('S07096B9','S07098B1'),
  ('S07097B10','S07098B1'),
  -- Jaipur (only one row)
  ('S08110B1','S08110B1'),
  -- North Kolkata family (canonical = S19348B2, 7 FLPs)
  ('S19348B2','S19348B2'),
  ('S19347B4','S19348B2'),
  -- South Kolkata family (canonical = S19346B3, 12 FLPs)
  ('S19346B3','S19346B3'),
  ('S19348B1','S19346B3'),
  -- Chennai (only one row)
  ('S33632B1','S33632B1');

-- 1. Wipe the existing rebuilt-from-FLP MGJ data
DELETE FROM mgj_areas;
DELETE FROM mgj_centres;

-- 2. Seed 7 canonical centres straight from new_centres
INSERT INTO mgj_centres (centre_code, centre_name, district_code, state_code, status, created_at, updated_at)
SELECT centre_code, centre_name, district_code, state_code, 'Active', NOW(), NOW()
FROM new_centres
WHERE centre_code IN (SELECT canon FROM _canon_map);

-- 3. Repoint every FLP area onto its canonical centre, then dedupe by
--    (canonical_centre, area_name). The ORDER BY tiebreaker prefers area rows
--    whose centre_code is already canonical, so existing MGJ records that
--    reference area_codes like S07093B3GP18 keep their target row.
INSERT INTO mgj_areas (area_code, area_name, centre_code, district_code, state_code, status, created_at, updated_at)
SELECT DISTINCT ON (m.canon, LOWER(a.area_name))
       a.area_code,
       a.area_name,
       m.canon AS centre_code,
       (SELECT district_code FROM new_centres WHERE centre_code = m.canon) AS district_code,
       a.state_code,
       'Active', NOW(), NOW()
FROM new_areas a
JOIN _canon_map m ON a.centre_code = m.src
ORDER BY m.canon,
         LOWER(a.area_name),
         CASE WHEN a.centre_code = m.canon THEN 0 ELSE 1 END,
         a.area_code;

-- 4. Sanity counts
SELECT 'mgj_centres' AS tbl, COUNT(*) AS cnt FROM mgj_centres
UNION ALL SELECT 'mgj_areas', COUNT(*) FROM mgj_areas
UNION ALL SELECT 'mgj_districts', COUNT(*) FROM mgj_districts
UNION ALL SELECT 'mgj_states', COUNT(*) FROM mgj_states;

-- 5. No-orphans check across MGJ dependents
SELECT 'orphan_members' AS chk, COUNT(*) AS cnt FROM mgj_members m
  WHERE m.deleted_at IS NULL AND (
    (m.centre_code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM mgj_centres c WHERE c.centre_code = m.centre_code))
    OR (m.area_code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM mgj_areas a WHERE a.area_code = m.area_code))
  )
UNION ALL SELECT 'orphan_alumni', COUNT(*) FROM mgj_alumni m
  WHERE m.deleted_at IS NULL AND (
    (m.centre_code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM mgj_centres c WHERE c.centre_code = m.centre_code))
    OR (m.area_code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM mgj_areas a WHERE a.area_code = m.area_code))
  )
UNION ALL SELECT 'orphan_batches', COUNT(*) FROM mgj_master_batches m
  WHERE m.deleted_at IS NULL AND
    m.centre_code IS NOT NULL AND
    NOT EXISTS (SELECT 1 FROM mgj_centres c WHERE c.centre_code = m.centre_code);

COMMIT;
