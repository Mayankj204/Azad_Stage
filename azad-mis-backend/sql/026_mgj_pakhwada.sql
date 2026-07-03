-- 026: MGJ Pakhwada — sessions (INPUT / SPORTS) + per-member attendance.
--
-- Field set (per `Basic Information of Pakhwada.docx`):
--   1. Session Type     (Pakhwada INPUT | Pakhwada SPORTS)
--   2. Month            (Jan–Dec)
--   3. Quarter          (auto-filled — Apr-Mar FY: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
--   4. Session/Topic    (text)
--   5. Planned Date     (date)
--   6. Centre           (dropdown)
--   7. Group Number     (text)

CREATE TABLE IF NOT EXISTS mgj_pakhwada_sessions (
  id                 SERIAL PRIMARY KEY,
  session_type       VARCHAR(10) NOT NULL CHECK (session_type IN ('INPUT', 'SPORTS')),
  session_month      INT NOT NULL CHECK (session_month BETWEEN 1 AND 12),
  session_year       INT NOT NULL,
  quarter            VARCHAR(2) CHECK (quarter IN ('Q1', 'Q2', 'Q3', 'Q4')),
  session_topic      VARCHAR(300) NOT NULL,
  planned_date       DATE,
  centre_code        VARCHAR(20),
  group_number       VARCHAR(50),
  status             VARCHAR(20) DEFAULT 'Planned'        -- 'Planned' | 'Conducted'
                       CHECK (status IN ('Planned', 'Conducted')),
  home_visit_count   INT DEFAULT 0,
  attendance_status  VARCHAR(20) DEFAULT 'Pending'        -- 'Pending' | 'Draft' | 'Submitted'
                       CHECK (attendance_status IN ('Pending', 'Draft', 'Submitted')),
  created_by         INT,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  deleted_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mgj_pakh_month       ON mgj_pakhwada_sessions(session_year, session_month);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_centre      ON mgj_pakhwada_sessions(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_type        ON mgj_pakhwada_sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_status      ON mgj_pakhwada_sessions(status);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_date        ON mgj_pakhwada_sessions(planned_date);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_deleted_at  ON mgj_pakhwada_sessions(deleted_at);


CREATE TABLE IF NOT EXISTS mgj_pakhwada_attendance (
  id           SERIAL PRIMARY KEY,
  session_id   INT NOT NULL REFERENCES mgj_pakhwada_sessions(id) ON DELETE CASCADE,
  member_id    INT NOT NULL,                              -- FK to mgj_members.id (no hard FK to avoid coupling)
  status       VARCHAR(20) NOT NULL CHECK (status IN ('Present', 'Absent', 'Late')),
  marked_at    TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_pakh_attendance UNIQUE (session_id, member_id)
);

CREATE INDEX IF NOT EXISTS idx_mgj_pakh_att_session ON mgj_pakhwada_attendance(session_id);
CREATE INDEX IF NOT EXISTS idx_mgj_pakh_att_member  ON mgj_pakhwada_attendance(member_id);
