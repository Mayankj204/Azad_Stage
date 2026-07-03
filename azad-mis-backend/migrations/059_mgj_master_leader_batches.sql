-- 2026-06-09: Leader Batch Management — MGJ-only master.
--
-- A separate batch system specifically for Leader's Profile and
-- Leader's Training. Mirrors mgj_master_batches schema 1:1 so the
-- Master CRUD UI can be reused with minimal divergence.
--
-- Two new FK columns added to existing tables so leaders + trainings
-- can be assigned to a Leader Batch independently of the regular
-- mgj_master_batches FK (which stays untouched for backward compat).
--
-- Nullable everywhere — existing rows stay valid; new assignments
-- accumulate as users adopt the Leader Batch master.

SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS mgj_master_leader_batches (
  id          SERIAL PRIMARY KEY,
  batch_code  VARCHAR(30),
  name        VARCHAR(100) NOT NULL,
  year        VARCHAR(20),
  state_code  VARCHAR(10),
  centre_code VARCHAR(20),
  status      VARCHAR(20) DEFAULT 'Active'
              CHECK (status IN ('Active', 'Inactive')),
  created_by  INTEGER,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  deleted_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_master_leader_batches_state
  ON mgj_master_leader_batches (state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_leader_batches_centre
  ON mgj_master_leader_batches (centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_leader_batches_status
  ON mgj_master_leader_batches (status);
CREATE INDEX IF NOT EXISTS idx_mgj_master_leader_batches_deleted_at
  ON mgj_master_leader_batches (deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_master_leader_batches_name_per_centre
  ON mgj_master_leader_batches (centre_code, lower(name))
  WHERE deleted_at IS NULL;

ALTER TABLE mgj_leaders
  ADD COLUMN IF NOT EXISTS leader_batch_id INTEGER
  REFERENCES mgj_master_leader_batches(id) ON DELETE SET NULL;

ALTER TABLE mgj_leader_trainings
  ADD COLUMN IF NOT EXISTS leader_batch_id INTEGER
  REFERENCES mgj_master_leader_batches(id) ON DELETE SET NULL;
