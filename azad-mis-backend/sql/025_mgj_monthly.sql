-- 025: MGJ Overall Activities — monthly KPI rows + topic chips + campaigns

CREATE TABLE IF NOT EXISTS mgj_monthly_activities (
  id                              SERIAL PRIMARY KEY,
  month                           DATE NOT NULL,             -- 1st of month
  centre_code                     VARCHAR(20),
  batch_id                        INT,

  -- 1.1 Pakhwada
  pakhwada_planned                INT DEFAULT 0,
  pakhwada_conducted              INT DEFAULT 0,
  pakhwada_participants           INT DEFAULT 0,
  pakhwada_direct                 INT DEFAULT 0,
  pakhwada_one_to_one             INT DEFAULT 0,
  -- 1.2 Sports
  sports_sessions                 INT DEFAULT 0,
  sports_participants             INT DEFAULT 0,
  -- 1.3 Parent Engagement
  hh_visits                       INT DEFAULT 0,
  parent_meeting_total            INT DEFAULT 0,
  parent_meeting_male             INT DEFAULT 0,
  parent_meeting_female           INT DEFAULT 0,
  male_only_meetings              INT DEFAULT 0,
  -- 1.4 Assignments
  assignments_completed           INT DEFAULT 0,
  assignment_groups               INT DEFAULT 0,
  -- 2. Campaign outreach counters (separate from per-campaign rows)
  canopy_activities               INT DEFAULT 0,
  mike_prachar                    INT DEFAULT 0,
  -- 3. WWW + GBV
  www_enabled_women               INT DEFAULT 0,
  www_enrollments                 INT DEFAULT 0,
  gbv_reached                     INT DEFAULT 0,
  gbv_remarks                     TEXT,
  -- 4. Leaders' Log
  leader_community_actions        INT DEFAULT 0,
  leader_vaccinations             INT DEFAULT 0,
  leader_www_forms                INT DEFAULT 0,
  leader_unpaid_care_boys         INT DEFAULT 0,
  leader_phase_training           INT DEFAULT 0,
  leader_refresher_training       INT DEFAULT 0,
  synergy_meetings                INT DEFAULT 0,
  synergy_participants            INT DEFAULT 0,
  leader_monthly_meetings         INT DEFAULT 0,
  leader_monthly_participants     INT DEFAULT 0,
  -- 5. Annual / Periodic
  alumni_meet_participants        INT DEFAULT 0,
  baseline_count                  INT DEFAULT 0,
  midline_y1                      INT DEFAULT 0,
  midline_y2                      INT DEFAULT 0,
  endline_count                   INT DEFAULT 0,

  status                          VARCHAR(20) DEFAULT 'Draft',     -- 'Draft' | 'Submitted'
  created_by                      INT,
  created_at                      TIMESTAMPTZ DEFAULT NOW(),
  updated_at                      TIMESTAMPTZ DEFAULT NOW(),
  deleted_at                      TIMESTAMPTZ
);

-- One active row per (month, centre, batch). Partial index so soft-deletes don't block re-create.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_monthly_activity_active
  ON mgj_monthly_activities (month, centre_code, batch_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_mgj_monthly_act_month       ON mgj_monthly_activities(month);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_act_centre      ON mgj_monthly_activities(centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_act_batch       ON mgj_monthly_activities(batch_id);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_act_status      ON mgj_monthly_activities(status);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_act_deleted_at  ON mgj_monthly_activities(deleted_at);


-- Topic / theme chips (multiple per entry, kind discriminates which section)
CREATE TABLE IF NOT EXISTS mgj_monthly_topics (
  id           SERIAL PRIMARY KEY,
  entry_id     INT NOT NULL REFERENCES mgj_monthly_activities(id) ON DELETE CASCADE,
  kind         VARCHAR(20) NOT NULL CHECK (kind IN ('pakhwada','sports','assignment')),
  topic_name   VARCHAR(300) NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_topics_entry ON mgj_monthly_topics(entry_id);


-- Campaigns recorded against this monthly entry (multiple per entry)
CREATE TABLE IF NOT EXISTS mgj_monthly_campaigns (
  id              SERIAL PRIMARY KEY,
  entry_id        INT NOT NULL REFERENCES mgj_monthly_activities(id) ON DELETE CASCADE,
  campaign_name   VARCHAR(300) NOT NULL,
  campaign_type   VARCHAR(50),
  participants    INT DEFAULT 0,
  remarks         TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mgj_monthly_campaigns_entry ON mgj_monthly_campaigns(entry_id);
