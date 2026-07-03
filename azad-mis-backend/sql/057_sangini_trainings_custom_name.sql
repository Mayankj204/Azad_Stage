-- 057_sangini_trainings_custom_name.sql
-- 2026-06-04: Sangini → Activities → Capacity Training UI swap.
-- The free-text "Name of Training" input is being replaced by a
-- dropdown (Feminist Way of Mentoring / Community Mobilization /
-- Perspective Building on Adolescents / Other). When the user picks
-- "Other", they type a custom training name in a sibling Specify
-- input that appears to the right of the dropdown.
--
-- training_name           — now stores either one of the 3 canonical
--                           options or the literal string 'Other'.
-- custom_training_name    — NEW. Populated only when training_name =
--                           'Other'. Capped at 100 chars + trimmed on
--                           the frontend; backend rejects empty.
--
-- Nullable so existing rows (which used training_name as free-text)
-- continue to render without code changes. The View renderer treats
-- legacy rows where training_name is neither a canonical option nor
-- 'Other' as their own labels.

SET search_path TO mis_azad;

ALTER TABLE sangini_trainings
  ADD COLUMN IF NOT EXISTS custom_training_name VARCHAR(100);
