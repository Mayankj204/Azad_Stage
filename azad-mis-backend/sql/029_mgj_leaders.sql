-- 029: MGJ Leader role + Leader Log (per-quarter activity log).
-- A Leader is an MGJ member who has been promoted to leader role.
-- The "Leader Log" form captures their quarterly activity self-report —
-- 5 Yes/No "Spoke against violence …" questions + a 25-item Care Work
-- self-assessment (questions sourced from "Basic Information of leaders log.docx").
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS mgj_leaders (
  id          SERIAL PRIMARY KEY,
  member_id   INT NOT NULL REFERENCES mgj_members(id) ON DELETE CASCADE,
  status      VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active','Inactive')),
  created_by  INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  deleted_at  TIMESTAMPTZ
);
-- One active leader entry per member at a time
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_leaders_member_active
  ON mgj_leaders(member_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mgj_leaders_status     ON mgj_leaders(status);
CREATE INDEX IF NOT EXISTS idx_mgj_leaders_deleted_at ON mgj_leaders(deleted_at);

-- Per-leader, per-quarter activity log (the "+ Leader Log" form).
-- Question responses are stored as a JSONB blob keyed by question_number
-- so the schema can evolve without a migration.
CREATE TABLE IF NOT EXISTS mgj_leader_logs (
  id          SERIAL PRIMARY KEY,
  leader_id   INT NOT NULL REFERENCES mgj_leaders(id) ON DELETE CASCADE,
  log_year    INT NOT NULL,
  log_quarter VARCHAR(10),
  log_date    DATE,
  responses   JSONB DEFAULT '{}'::jsonb,
  created_by  INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_logs_leader     ON mgj_leader_logs(leader_id);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_logs_year       ON mgj_leader_logs(log_year);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_logs_deleted_at ON mgj_leader_logs(deleted_at);
