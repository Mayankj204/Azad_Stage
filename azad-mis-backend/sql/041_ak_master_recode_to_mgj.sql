-- 041: Re-code AK geography to use IDENTICAL codes as MGJ.
--
-- Replaces migrations 039/040's AK_*-prefixed scheme. After this runs,
-- ak_states / ak_districts / ak_centres / ak_areas hold the same codes
-- and names as their MGJ counterparts (S07 / S07091 / S07091B2 /
-- S07091B2A1 / etc.) but the tables remain physically independent — no
-- shared FK between the two families.
--
-- Existing AK records (ak_leaders, ak_alaps, ak_addas, ak_batches,
-- ak_trainings, ak_alap_trainings, ak_alumni, ak_assessments) hold text
-- references to the OLD AK_* codes; we rewire each via name-matching to
-- the new MGJ-equivalent codes BEFORE wiping the geo tables, so nothing
-- orphans.
--
-- Safe to re-run: external UPDATEs match only the old AK_* values, so
-- a second run is a no-op on those tables, and the wipe+clone produces
-- the same final state.
SET search_path TO mis_azad, public;

BEGIN;

-- ---------- (1) Snapshot old-AK → new-MGJ centre code mapping ----------
-- Match by lower-cased centre name. Done BEFORE the wipe so we still
-- have the old AK centres to read from.
CREATE TEMP TABLE _ak_centre_remap AS
SELECT ac.centre_code AS old_code, mc.centre_code AS new_code
FROM ak_centres ac
JOIN mgj_centres mc ON LOWER(ac.centre_name) = LOWER(mc.centre_name)
WHERE ac.deleted_at IS NULL AND mc.deleted_at IS NULL;


-- ---------- (2) Rewire external AK records: state_code AK_* → S* ----------
-- AK_DL → S07, AK_RJ → S08, AK_WB → S19, AK_TN → S33.
-- Driven via DO+EXECUTE loop so the four-table list stays maintainable.
DO $$
DECLARE tbl text;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'ak_addas','ak_alap_trainings','ak_alaps','ak_alumni',
    'ak_assessments','ak_batches','ak_leaders','ak_trainings'
  ])
  LOOP
    EXECUTE format(
      'UPDATE %I SET state_code = CASE state_code '
      ' WHEN ''AK_DL'' THEN ''S07'' '
      ' WHEN ''AK_RJ'' THEN ''S08'' '
      ' WHEN ''AK_WB'' THEN ''S19'' '
      ' WHEN ''AK_TN'' THEN ''S33'' END '
      'WHERE state_code IN (''AK_DL'',''AK_RJ'',''AK_WB'',''AK_TN'')',
      tbl
    );
  END LOOP;
END $$;


-- ---------- (3) Rewire external AK records: centre_code via the remap ----------
DO $$
DECLARE tbl text;
BEGIN
  FOR tbl IN SELECT unnest(ARRAY[
    'ak_addas','ak_alaps','ak_alumni','ak_assessments',
    'ak_batches','ak_leaders','ak_trainings'
  ])
  LOOP
    EXECUTE format(
      'UPDATE %I a SET centre_code = m.new_code '
      'FROM _ak_centre_remap m WHERE a.centre_code = m.old_code',
      tbl
    );
  END LOOP;
END $$;


-- ---------- (4) Wipe the AK geo tables in FK dependency order ----------
DELETE FROM ak_areas;
DELETE FROM ak_centres;
DELETE FROM ak_districts;
DELETE FROM ak_states;


-- ---------- (5) Clone MGJ geography verbatim into AK ----------
INSERT INTO ak_states (state_code, state_name, status, created_at, updated_at, deleted_at)
SELECT state_code, state_name, status, created_at, updated_at, deleted_at
FROM mgj_states;

INSERT INTO ak_districts (district_code, district_name, state_code, status, created_at, updated_at, deleted_at)
SELECT district_code, district_name, state_code, status, created_at, updated_at, deleted_at
FROM mgj_districts;

INSERT INTO ak_centres (centre_code, centre_name, district_code, state_code, status, created_at, updated_at, deleted_at)
SELECT centre_code, centre_name, district_code, state_code, status, created_at, updated_at, deleted_at
FROM mgj_centres;

INSERT INTO ak_areas (area_code, area_name, centre_code, district_code, state_code, status, created_at, updated_at, deleted_at)
SELECT area_code, area_name, centre_code, district_code, state_code, status, created_at, updated_at, deleted_at
FROM mgj_areas;

COMMIT;
