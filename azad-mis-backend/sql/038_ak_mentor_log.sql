-- ALAP Mentor Log — one record per mentoring session per ALAP leader.
-- Captures session metadata + 8 Leadership-Trait ratings (1-5 each) +
-- a free-text comment and a Yes/No feedback flag.
SET search_path TO mis_azad, public;

CREATE TABLE IF NOT EXISTS ak_mentor_log (
  id                     SERIAL PRIMARY KEY,
  mentor_name            VARCHAR(200) NOT NULL,
  alap_id                INTEGER NOT NULL REFERENCES ak_alaps(id) ON DELETE CASCADE,
  log_date               DATE,
  details_of_discussion  TEXT,
  -- Leadership Traits — each a 1-5 single-select rating.
  trait_openness         INTEGER,
  trait_confrontation    INTEGER,
  trait_trust            INTEGER,
  trait_authenticity     INTEGER,
  trait_proaction        INTEGER,
  trait_autonomy         INTEGER,
  trait_collaboration    INTEGER,
  trait_experimentation  INTEGER,
  -- Comment & Feedback
  comment                TEXT,
  feedback_received      VARCHAR(10),  -- 'Yes' / 'No'
  status                 VARCHAR(20) DEFAULT 'Active',
  deleted_at             TIMESTAMPTZ,
  created_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_at             TIMESTAMPTZ DEFAULT NOW(),
  created_by             VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ak_mentor_log_alap   ON ak_mentor_log(alap_id)     WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_mentor_log_mentor ON ak_mentor_log(mentor_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ak_mentor_log_date   ON ak_mentor_log(log_date)    WHERE deleted_at IS NULL;
