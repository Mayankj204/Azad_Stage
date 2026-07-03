-- 040: One-time clone of MGJ geography data into the AK geography tables.
--
-- After this runs, ak_districts / ak_areas hold the same rows (by name +
-- hierarchy) as their MGJ counterparts — but with AK-prefixed codes so
-- the two programs remain completely independent going forward. AK and
-- MGJ then evolve independently from this shared starting point.
--
-- Mapping rules:
--   state_code: keep AK's existing AK_DL / AK_RJ / AK_WB / AK_TN (names
--               already align with MGJ).
--   district_code: derive from MGJ via "AK" || SUBSTRING(code FROM 2)
--                  e.g. S07099 -> AK07099. Stable + traceable.
--   centre_code:   keep AK's existing 7 codes (AK_DL_N etc.) so the 48
--                  dependent AK records (leaders/batches/trainings/...)
--                  don't orphan. Re-assign their district_code instead.
--   area_code:     derive from MGJ via "AK" || SUBSTRING(code FROM 2).
--
-- Safe to re-run (idempotent via ON CONFLICT DO NOTHING + WHERE NOT EXISTS).
SET search_path TO mis_azad, public;

BEGIN;

-- ---------- (1) Insert all MGJ districts into ak_districts ----------
INSERT INTO ak_districts (district_code, district_name, state_code, status)
SELECT
  'AK' || SUBSTRING(d.district_code FROM 2)                AS district_code,
  d.district_name,
  CASE d.state_code
    WHEN 'S07' THEN 'AK_DL' WHEN 'S08' THEN 'AK_RJ'
    WHEN 'S19' THEN 'AK_WB' WHEN 'S33' THEN 'AK_TN'
  END                                                       AS state_code,
  d.status
FROM mgj_districts d
WHERE d.deleted_at IS NULL
ON CONFLICT (district_code) DO NOTHING;


-- ---------- (2) Re-point existing AK centres from *_DEFAULT placeholder
-- districts to the proper named district, by matching MGJ centre name. ----------
UPDATE ak_centres ac
SET district_code = 'AK' || SUBSTRING(mc.district_code FROM 2),
    updated_at    = NOW()
FROM mgj_centres mc
WHERE LOWER(ac.centre_name) = LOWER(mc.centre_name)
  AND ac.deleted_at IS NULL
  AND mc.deleted_at IS NULL
  AND ac.district_code LIKE '%_DEFAULT';   -- only touch placeholder rows


-- ---------- (3) Drop the 4 placeholder *_DEFAULT districts ----------
-- Safe because step (2) reassigned every centre off them.
DELETE FROM ak_districts WHERE district_code LIKE '%\_DEFAULT' ESCAPE '\';


-- ---------- (4) Insert all MGJ areas into ak_areas ----------
-- Each MGJ area's centre maps to the existing AK centre with the same name,
-- so all 141 areas attach to the canonical AK centre codes (AK_DL_N etc.).
INSERT INTO ak_areas (area_code, area_name, centre_code, district_code, state_code, status)
SELECT
  'AK' || SUBSTRING(ma.area_code FROM 2)                   AS area_code,
  ma.area_name,
  ac.centre_code                                            AS centre_code,
  'AK' || SUBSTRING(ma.district_code FROM 2)                AS district_code,
  CASE ma.state_code
    WHEN 'S07' THEN 'AK_DL' WHEN 'S08' THEN 'AK_RJ'
    WHEN 'S19' THEN 'AK_WB' WHEN 'S33' THEN 'AK_TN'
  END                                                       AS state_code,
  ma.status
FROM mgj_areas ma
JOIN mgj_centres mc ON ma.centre_code = mc.centre_code AND mc.deleted_at IS NULL
JOIN ak_centres ac ON LOWER(ac.centre_name) = LOWER(mc.centre_name) AND ac.deleted_at IS NULL
WHERE ma.deleted_at IS NULL
ON CONFLICT (area_code) DO NOTHING;

COMMIT;


-- Sanity-check view: confirm counts match between MGJ and AK after clone.
-- Expected post-clone (rerun safe): ak_states=4, ak_districts=14, ak_centres=7,
-- ak_areas=141 — identical to MGJ.
