-- 059_mobiliser_sangini_roles.sql
--
-- Adds two new field roles to the `roles` table for the web-Assessment
-- workflow rolled out 2026-06-05:
--   id=8  Mobiliser → MGJ programme only, conducts MGJ assessments
--   id=9  Sangini   → AK programme only, conducts AK assessments
--
-- Both roles are *strictly* geography-scoped (assigned State + District +
-- Centre via the existing geo_scope free-text on users) and *strictly*
-- program-locked (Mobiliser ⇒ MGJ, Sangini ⇒ AK). The web UI hides every
-- module from these users except the Assessment submenu of their assigned
-- programme.
--
-- Frontend / backend wiring lives in:
--   • app.js  roleIdMap / ROLE_NAME_TO_KEY / ROLE_PERMISSIONS
--   • app.js  toggleUserCentreField (cascade source per role)
--   • app.js  _applyRoleScopeFloor  (frontend filter floor)
--   • routes/users.py + routes/auth.py  (id+name plumbing — no schema change)
--
-- Pin schema so it does not depend on caller's search_path.
SET search_path TO mis_azad, public;

INSERT INTO roles (id, name, description)
VALUES
  (8, 'Mobiliser', 'MGJ Mobiliser — web-only Assessment conductor for an assigned MGJ Centre'),
  (9, 'Sangini',   'AK Sangini — web-only Assessment conductor for an assigned AK Centre')
ON CONFLICT (id) DO NOTHING;

-- Bump the SERIAL sequence so future inserts via the API don't collide
-- with the hardcoded ids 8 and 9.
SELECT setval(pg_get_serial_sequence('roles', 'id'),
              GREATEST((SELECT MAX(id) FROM roles), 9), true);
