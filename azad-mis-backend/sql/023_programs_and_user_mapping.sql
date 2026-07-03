-- 023: Create `programs` master and `user_program_mapping` junction.
-- The backend (routes/programs.py) already references both tables; without them
-- POST /api/programs/assign fires a 500 that the user sees, obscured, as
-- "Error creating user: …" even though the user row was actually created.
-- This migration is idempotent and safe to re-run.

CREATE TABLE IF NOT EXISTS programs (
  code         VARCHAR(10)  PRIMARY KEY,
  name         VARCHAR(200) NOT NULL,
  description  TEXT,
  icon         VARCHAR(50),
  color        VARCHAR(20),
  status       VARCHAR(20)  DEFAULT 'Active',
  sort_order   INT          DEFAULT 0,
  created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- Seed the 4 programs the frontend already knows about.
INSERT INTO programs (code, name, description, icon, color, status, sort_order) VALUES
  ('FLP', 'Feminist Leadership Program', 'FLP — full program',                         'fa-users',  '#732269', 'Active', 10),
  ('WWW', 'Women with Wheels',           'WWW — livelihood/driver enrollment program', 'fa-car',    '#3498db', 'Active', 20),
  ('AK',  'Azad Kishori',                'AK — adolescent girls program',              'fa-child',  '#27ae60', 'Active', 30),
  ('MGJ', 'Men with Gender Justice',     'MGJ — boys / young men program',             'fa-male',   '#e67e22', 'Active', 40)
ON CONFLICT (code) DO UPDATE SET
  name        = EXCLUDED.name,
  description = COALESCE(programs.description, EXCLUDED.description),
  icon        = EXCLUDED.icon,
  color       = EXCLUDED.color,
  status      = EXCLUDED.status,
  sort_order  = EXCLUDED.sort_order;

CREATE TABLE IF NOT EXISTS user_program_mapping (
  user_id       INT          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  program_code  VARCHAR(10)  NOT NULL REFERENCES programs(code) ON UPDATE CASCADE ON DELETE CASCADE,
  assigned_at   TIMESTAMPTZ  DEFAULT NOW(),
  PRIMARY KEY (user_id, program_code)
);

CREATE INDEX IF NOT EXISTS idx_upm_user    ON user_program_mapping(user_id);
CREATE INDEX IF NOT EXISTS idx_upm_program ON user_program_mapping(program_code);
