-- =============================================
-- 014: Multiple Eligible Women Support
-- Adds eligible_women_count to surveys,
-- creates survey_eligible_women repeating group table.
-- Old single-entry eligible_woman_* columns kept for backward compat.
-- =============================================

ALTER TABLE surveys ADD COLUMN IF NOT EXISTS eligible_women_count INT DEFAULT 0;

CREATE TABLE IF NOT EXISTS survey_eligible_women (
    id              SERIAL PRIMARY KEY,
    survey_id       INT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    member_index    INT NOT NULL DEFAULT 0,
    name            VARCHAR(200),
    wants           TEXT,
    obstacles       TEXT,
    opportunities   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_survey_eligible_women_survey_id ON survey_eligible_women(survey_id);
