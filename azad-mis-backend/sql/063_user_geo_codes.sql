-- 2026-06-05: Phase 2 backend role-scope enforcement — foundation.
--
-- Adds state_code / district_code / centre_code columns to the users
-- table and backfills them from the existing free-text geo_scope so the
-- new routes/_role_scope.py helper can pin geo params at the data-
-- endpoint layer (closes the DevTools / curl bypass for SL / DL / PI /
-- Mobiliser / Sangini roles).
--
-- All operations are idempotent and wrapped in a single transaction —
-- safe to re-run when new restricted users are created and need their
-- codes populated. The four UPDATEs are gated on WHERE state_code IS
-- NULL so already-resolved users are not touched.
--
-- NOT TOUCHED: any other table. Cascade-dropdown endpoints continue to
-- return master data unchanged for every role.

BEGIN;

-- 1. Add columns (nullable, idempotent).
ALTER TABLE users ADD COLUMN IF NOT EXISTS state_code    VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS district_code VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS centre_code   VARCHAR(20);

-- 2a. Mobiliser / Sangini — geo_scope already contains the explicit
--     bracketed codes ("Centre, District [STATE|DISTRICT|CENTRE]") so
--     regex extraction is exact and deterministic.
UPDATE users u
   SET state_code    = (regexp_match(u.geo_scope, '\[([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\s*$'))[1],
       district_code = (regexp_match(u.geo_scope, '\[([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\s*$'))[2],
       centre_code   = (regexp_match(u.geo_scope, '\[([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\s*$'))[3]
  FROM roles r
 WHERE u.role_id = r.id
   AND LOWER(r.name) IN ('mobiliser', 'sangini')
   AND u.geo_scope ~ '\[[^|]+\|[^|]+\|[^\]]+\]\s*$'
   AND u.state_code IS NULL
   AND u.deleted_at IS NULL;

-- 2b. State Lead — geo_scope is typically just the state name (sometimes
--     "X Centre" — strip the suffix). LIKE-match against new_states.
UPDATE users u
   SET state_code = ns.state_code
  FROM roles r, new_states ns
 WHERE u.role_id = r.id
   AND LOWER(r.name) = 'state lead'
   AND LOWER(TRIM(REGEXP_REPLACE(COALESCE(u.geo_scope,''), ' Centre$', ''))) = LOWER(ns.state_name)
   AND u.state_code IS NULL
   AND u.deleted_at IS NULL;

-- 2c. District Lead and PI — first comma-separated part is typically the
--     centre name, the second the district. Try exact centre match in
--     new_centres first. PI gets all 3 codes; DL clears centre_code so
--     they can drill into any centre within their district.
WITH centre_match AS (
  SELECT u.id,
         LOWER(r.name) AS role_lc,
         nc.state_code,
         nc.district_code,
         nc.centre_code
    FROM users u
    JOIN roles r ON r.id = u.role_id
    JOIN new_centres nc ON LOWER(nc.centre_name) = LOWER(TRIM(SPLIT_PART(u.geo_scope, ',', 1)))
   WHERE LOWER(r.name) IN ('district lead', 'project incharge (pi)', 'pi')
     AND u.state_code IS NULL
     AND u.deleted_at IS NULL
)
UPDATE users u
   SET state_code    = cm.state_code,
       district_code = cm.district_code,
       centre_code   = CASE WHEN cm.role_lc = 'district lead' THEN NULL ELSE cm.centre_code END
  FROM centre_match cm
 WHERE u.id = cm.id;

-- 2d. District Lead fallback — when centre name didn't match (e.g. the
--     geo_scope only carries district names like "South Delhi, South
--     Delhi"), try matching against new_districts. Either of the two
--     comma-parts may be the district name.
WITH district_match AS (
  SELECT DISTINCT ON (u.id) u.id,
         nd.state_code,
         nd.district_code
    FROM users u
    JOIN roles r ON r.id = u.role_id
    JOIN new_districts nd ON LOWER(nd.district_name) IN (
        LOWER(TRIM(SPLIT_PART(u.geo_scope, ',', 1))),
        LOWER(TRIM(SPLIT_PART(u.geo_scope, ',', 2)))
    )
   WHERE LOWER(r.name) = 'district lead'
     AND u.state_code IS NULL
     AND u.deleted_at IS NULL
   ORDER BY u.id, nd.district_code
)
UPDATE users u
   SET state_code    = dm.state_code,
       district_code = dm.district_code
  FROM district_match dm
 WHERE u.id = dm.id;

-- 3. Surface unmatched users for admin attention. They keep working
--    normally on the frontend (no user-visible change); the helper
--    fail-opens for them so they won't be locked out — they just don't
--    get backend enforcement until their geo_scope is fixed.
DO $$
DECLARE
  unmatched_total INT;
BEGIN
  SELECT COUNT(*) INTO unmatched_total
    FROM users u
    JOIN roles r ON r.id = u.role_id
   WHERE LOWER(r.name) IN ('state lead','district lead','project incharge (pi)','pi','mobiliser','sangini')
     AND u.deleted_at IS NULL
     AND u.state_code IS NULL;
  RAISE NOTICE 'Restricted users without state_code after migration: %', unmatched_total;
END $$;

COMMIT;
