-- 030: MGJ Leader Training, Refresher Trainings, Social Action Projects.
-- All tables fully isolated from FLP — they reference only mgj_* masters.
SET search_path TO mis_azad, public;

-- ----- Topic master (used by the Add-Training topic-picker) -----
CREATE TABLE IF NOT EXISTS mgj_leader_topics (
  id          SERIAL PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  status      VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active','Inactive')),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  deleted_at  TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_leader_topics_name
  ON mgj_leader_topics (LOWER(name)) WHERE deleted_at IS NULL;

-- Seed a few common topics so the UI has data to pick from on first run.
INSERT INTO mgj_leader_topics (name) VALUES
  ('Gender & Sex'),
  ('Patriarchy'),
  ('Power & Privilege'),
  ('Masculinity'),
  ('Violence & UCW'),
  ('Reproductive Rights'),
  ('Communication & Listening Skills'),
  ('Leadership Building')
ON CONFLICT DO NOTHING;

-- ----- Main Training (one per state/batch/phase/year combination) -----
CREATE TABLE IF NOT EXISTS mgj_leader_trainings (
  id          SERIAL PRIMARY KEY,
  state_code  VARCHAR(10),
  batch_id    INT,
  phase       VARCHAR(20) NOT NULL CHECK (phase IN ('Phase I','Phase II')),
  year        VARCHAR(20),
  created_by  INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_trainings_state ON mgj_leader_trainings(state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_trainings_batch ON mgj_leader_trainings(batch_id);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_trainings_phase ON mgj_leader_trainings(phase);
CREATE INDEX IF NOT EXISTS idx_mgj_leader_trainings_deleted ON mgj_leader_trainings(deleted_at);

-- ----- Topics linked to a Training (m:n) -----
CREATE TABLE IF NOT EXISTS mgj_leader_training_topics (
  id           SERIAL PRIMARY KEY,
  training_id  INT NOT NULL REFERENCES mgj_leader_trainings(id) ON DELETE CASCADE,
  topic_id     INT NOT NULL REFERENCES mgj_leader_topics(id) ON DELETE CASCADE,
  topic_date   DATE,
  position     INT DEFAULT 0,
  UNIQUE (training_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_mgj_lt_topics_training ON mgj_leader_training_topics(training_id);

-- ----- Participants (leaders) assigned to a Training -----
CREATE TABLE IF NOT EXISTS mgj_leader_training_participants (
  id           SERIAL PRIMARY KEY,
  training_id  INT NOT NULL REFERENCES mgj_leader_trainings(id) ON DELETE CASCADE,
  leader_id    INT NOT NULL REFERENCES mgj_leaders(id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (training_id, leader_id)
);
CREATE INDEX IF NOT EXISTS idx_mgj_lt_part_training ON mgj_leader_training_participants(training_id);

-- ----- Per-topic per-leader attendance -----
CREATE TABLE IF NOT EXISTS mgj_leader_training_attendance (
  id              SERIAL PRIMARY KEY,
  training_id     INT NOT NULL REFERENCES mgj_leader_trainings(id) ON DELETE CASCADE,
  topic_id        INT NOT NULL REFERENCES mgj_leader_topics(id) ON DELETE CASCADE,
  leader_id       INT NOT NULL REFERENCES mgj_leaders(id) ON DELETE CASCADE,
  status          VARCHAR(20) DEFAULT 'Absent' CHECK (status IN ('Present','Absent')),
  attendance_date DATE,
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (training_id, topic_id, leader_id)
);

-- ----- Refresher trainings (per Training, per quarter) -----
CREATE TABLE IF NOT EXISTS mgj_leader_refreshers (
  id              SERIAL PRIMARY KEY,
  training_id     INT NOT NULL REFERENCES mgj_leader_trainings(id) ON DELETE CASCADE,
  quarter         VARCHAR(20),
  title           VARCHAR(500) NOT NULL,
  refresher_date  DATE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mgj_lt_refreshers_training ON mgj_leader_refreshers(training_id);

-- ----- Refresher per-leader attendance -----
CREATE TABLE IF NOT EXISTS mgj_leader_refresher_attendance (
  id            SERIAL PRIMARY KEY,
  refresher_id  INT NOT NULL REFERENCES mgj_leader_refreshers(id) ON DELETE CASCADE,
  leader_id     INT NOT NULL REFERENCES mgj_leaders(id) ON DELETE CASCADE,
  status        VARCHAR(20) DEFAULT 'Absent' CHECK (status IN ('Present','Absent')),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (refresher_id, leader_id)
);

-- ----- Social Action Projects (per Training, per quarter) -----
CREATE TABLE IF NOT EXISTS mgj_leader_social_actions (
  id           SERIAL PRIMARY KEY,
  training_id  INT NOT NULL REFERENCES mgj_leader_trainings(id) ON DELETE CASCADE,
  quarter      VARCHAR(20),
  description  TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  deleted_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mgj_lt_sa_training ON mgj_leader_social_actions(training_id);
