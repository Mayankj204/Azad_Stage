-- 021: Internship module
-- Tables: organizations, internship_assignments, internship_reports (+ doc/image attachments)

-- Partner organizations (companies / NGOs / Govt bodies hosting FLP internships)
CREATE TABLE IF NOT EXISTS organizations (
  id              SERIAL PRIMARY KEY,
  name            VARCHAR(200) NOT NULL,
  address         TEXT,
  contact_number  VARCHAR(20),
  contact_person  VARCHAR(150),
  email           VARCHAR(150),
  org_type        VARCHAR(20) CHECK (org_type IN ('NGO','Private','Govt','Other')),
  remarks         TEXT,
  status          VARCHAR(20) DEFAULT 'Active',
  created_by      INT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

-- Case-insensitive unique on name (only for non-deleted rows)
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_name_unique
  ON organizations (LOWER(name))
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);


-- FLP -> Organization assignments (internship placements)
CREATE TABLE IF NOT EXISTS internship_assignments (
  id              SERIAL PRIMARY KEY,
  flp_id          INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
  organization_id INT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  state_code      VARCHAR(10),
  district_code   VARCHAR(20),
  centre_code     VARCHAR(20),
  batch_id        INT REFERENCES batches(id) ON DELETE SET NULL,
  start_date      DATE NOT NULL,
  end_date        DATE NOT NULL,
  status          VARCHAR(20) DEFAULT 'Active',
  remarks         TEXT,
  created_by      INT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ,
  CONSTRAINT chk_internship_dates CHECK (start_date <= end_date)
);

CREATE INDEX IF NOT EXISTS idx_int_assignments_flp         ON internship_assignments(flp_id);
CREATE INDEX IF NOT EXISTS idx_int_assignments_org         ON internship_assignments(organization_id);
CREATE INDEX IF NOT EXISTS idx_int_assignments_dates       ON internship_assignments(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_int_assignments_status      ON internship_assignments(status);
CREATE INDEX IF NOT EXISTS idx_int_assignments_deleted_at  ON internship_assignments(deleted_at);


-- Reports submitted by FLP against an assignment (can be multiple per assignment)
CREATE TABLE IF NOT EXISTS internship_reports (
  id              SERIAL PRIMARY KEY,
  assignment_id   INT NOT NULL REFERENCES internship_assignments(id) ON DELETE CASCADE,
  topic_id        INT REFERENCES training_topics(id) ON DELETE SET NULL,
  description     TEXT,
  key_learnings   TEXT,
  challenges      TEXT,
  created_by      INT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_int_reports_assignment ON internship_reports(assignment_id);


-- Attachments for reports (documents + images in one table, distinguished by file_kind)
CREATE TABLE IF NOT EXISTS internship_report_files (
  id              SERIAL PRIMARY KEY,
  report_id       INT NOT NULL REFERENCES internship_reports(id) ON DELETE CASCADE,
  file_kind       VARCHAR(10) NOT NULL CHECK (file_kind IN ('doc','image')),
  file_name       VARCHAR(300),
  file_path       VARCHAR(600) NOT NULL,
  file_size       BIGINT,
  mime_type       VARCHAR(100),
  uploaded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_int_report_files_report ON internship_report_files(report_id);
