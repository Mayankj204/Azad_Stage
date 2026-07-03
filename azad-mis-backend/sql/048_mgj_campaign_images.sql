-- 2026-05-26
-- Add per-campaign image attachments to MGJ Overall Activities.
-- Mirrors the ak_training_images pattern. ON DELETE CASCADE means images
-- are removed automatically if the parent campaign row is deleted.
-- IMPORTANT: this assumes the campaigns PUT handler upserts by id
-- (not the old DELETE-and-reinsert pattern) — otherwise every edit would
-- cascade-delete every image. The companion change in routes/mgj_monthly.py
-- handles that.

BEGIN;

CREATE TABLE IF NOT EXISTS mgj_campaign_images (
    id            SERIAL PRIMARY KEY,
    campaign_id   INT NOT NULL REFERENCES mgj_monthly_campaigns(id) ON DELETE CASCADE,
    file_name     VARCHAR(300) NOT NULL,   -- original filename for display
    file_path     VARCHAR(500) NOT NULL,   -- public URL, e.g. /uploads/mgj_campaign_<id>_<uuid>.jpg
    file_size     INT,                     -- bytes
    mime_type     VARCHAR(80),
    uploaded_at   TIMESTAMPTZ DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ              -- NULL = live row
);

CREATE INDEX IF NOT EXISTS idx_mgj_campaign_images_campaign
    ON mgj_campaign_images(campaign_id)
    WHERE deleted_at IS NULL;

COMMIT;

-- Sanity check
SELECT column_name, data_type, is_nullable
  FROM information_schema.columns
 WHERE table_schema='mis_azad' AND table_name='mgj_campaign_images'
 ORDER BY ordinal_position;
