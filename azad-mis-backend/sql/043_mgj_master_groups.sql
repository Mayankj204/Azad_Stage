-- MGJ Master Groups
-- ============================================================================
-- Groups are created on the basis of Area (with Centre as the parent of Area).
-- Modeled on mgj_master_batches but adds an area_code column. One area can
-- have multiple groups; one centre can have multiple groups (across multiple
-- areas). State and Centre are derivable from Area but stored here for the
-- same convenience reason mgj_master_batches stores them.
--
-- No FK constraints to mgj_centres / mgj_areas — mgj_master_batches doesn't
-- have them either; soft-delete + name uniqueness within an area is enough.
-- ============================================================================

CREATE TABLE IF NOT EXISTS mgj_master_groups (
  id            SERIAL PRIMARY KEY,
  group_code    VARCHAR(30),
  name          VARCHAR(100) NOT NULL,
  state_code    VARCHAR(10),
  centre_code   VARCHAR(20),
  area_code     VARCHAR(30),
  status        VARCHAR(20) DEFAULT 'Active',
  created_by    INTEGER,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  deleted_at    TIMESTAMPTZ,
  CONSTRAINT mgj_master_groups_status_check CHECK (status IN ('Active','Inactive'))
);

-- Index pattern mirrors mgj_master_batches for consistent query plans.
CREATE INDEX IF NOT EXISTS idx_mgj_master_groups_state      ON mgj_master_groups (state_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_groups_centre     ON mgj_master_groups (centre_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_groups_area       ON mgj_master_groups (area_code);
CREATE INDEX IF NOT EXISTS idx_mgj_master_groups_status     ON mgj_master_groups (status);
CREATE INDEX IF NOT EXISTS idx_mgj_master_groups_deleted_at ON mgj_master_groups (deleted_at);

-- One area can have multiple groups, but two groups in the SAME area can't
-- share a name (case-insensitive). Excludes soft-deleted rows so a name
-- becomes reusable after a delete.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mgj_master_groups_name_per_area
  ON mgj_master_groups (area_code, LOWER(name))
  WHERE deleted_at IS NULL;
