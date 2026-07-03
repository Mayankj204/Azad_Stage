-- 2026-05-30: MGJ Leader Action Log
--
-- Cross-leader catalogue of discrete activities / actions / trainings that
-- a leader has participated in or led. Distinct from the existing
-- `mgj_leader_logs` table, which holds per-leader per-quarter JSONB form
-- responses — that's the "Leader Log" feature. This new table is the
-- "Leader Action Log": list-facing, one row per action, with leader-level
-- detail snapshotted on the row so the list page can render without a
-- JOIN cascade.
--
-- Reporting cadence per user spec: "updated twice a year" → reporting_period
-- captures the half ('H1 YYYY' / 'H2 YYYY'). action_date captures the
-- actual day the activity took place.
--
-- action_type vocabulary covers the activity classes the user mentioned
-- (Refresher Training, Leader Training, Social Action) plus open-ended
-- "Other" so coordinators can record anything not already in the list.
--
-- Idempotent (IF NOT EXISTS) so re-running the migration on a partially
-- applied DB is safe.

CREATE TABLE IF NOT EXISTS mgj_leader_actions (
  id                  SERIAL PRIMARY KEY,
  leader_id           INT NOT NULL REFERENCES mgj_leaders(id),
  -- Denormed leader/member/centre info captured at write time so the
  -- list endpoint can paginate cheaply without joining mgj_leaders →
  -- mgj_members → mgj_centres → mgj_states for every row.
  leader_name         VARCHAR(200),
  enrollment_number   VARCHAR(80),
  state_code          VARCHAR(10),
  centre_code         VARCHAR(20),
  -- Activity metadata
  action_type         VARCHAR(60) NOT NULL,   -- 'Refresher Training' | 'Leader Training'
                                              -- | 'Social Action' | 'Community Outreach'
                                              -- | 'Campaign' | 'Other'
  action_type_other   VARCHAR(200),           -- free-text when action_type='Other'
  action_title        VARCHAR(300) NOT NULL,
  action_date         DATE,
  reporting_period    VARCHAR(20),            -- 'H1 2026' / 'H2 2026' / 'Jan-Jun 2026' / etc.
  location            VARCHAR(200),
  participants_count  INT,
  -- Narrative
  description         TEXT,
  outcomes            TEXT,
  remarks             TEXT,
  -- Optional attachments stored as JSONB array of {name,url,size,mime}.
  attachments_meta    JSONB DEFAULT '[]'::jsonb,
  -- Audit + soft-delete
  created_by          INT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  deleted_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_leader  ON mgj_leader_actions (leader_id);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_state   ON mgj_leader_actions (state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_centre  ON mgj_leader_actions (centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_type    ON mgj_leader_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_period  ON mgj_leader_actions (reporting_period);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_date    ON mgj_leader_actions (action_date);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_actions_deleted ON mgj_leader_actions (deleted_at);
