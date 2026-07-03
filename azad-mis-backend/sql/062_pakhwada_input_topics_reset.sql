-- 2026-06-05: Reset Pakhwada Input topics master per user-supplied
-- 28-item curriculum. Three operations in one transaction:
--
--   1. ALTER TABLE add display_order column (idempotent)
--   2. Soft-delete EVERY existing Pakhwada Input topic (preserves
--      historical FK refs from mgj_leader_training_topics)
--   3. INSERT the 28 new topics with display_order 1..28
--
-- The backend ORDER BY (routes/mgj_leader_training.py) now honours
-- COALESCE(display_order, 9999), so the dropdown + Topic Management
-- show the user's curriculum sequence rather than alphabetical.
--
-- Affects: mis_azad.mgj_leader_topics only. Safe to re-run.

BEGIN;

-- 1. Add display_order column (no-op if it already exists)
ALTER TABLE mgj_leader_topics ADD COLUMN IF NOT EXISTS display_order INTEGER;

-- 2. Soft-delete existing Pakhwada Input topics. Keep the rows in
--    place so historical mgj_leader_training_topics records that
--    reference them stay intact.
UPDATE mgj_leader_topics
   SET deleted_at = NOW()
 WHERE training_type = 'Pakhwada Input'
   AND deleted_at IS NULL;

-- 3. Insert the 28 new curriculum topics in user-supplied sequence.
INSERT INTO mgj_leader_topics (name, status, training_type, display_order) VALUES
('Program Introduction and Orientation', 'Active', 'Pakhwada Input', 1),
('Importance of Collective Organization for Justice', 'Active', 'Pakhwada Input', 2),
('Let''s Understand about Constitution and Know Our Rights and Duties', 'Active', 'Pakhwada Input', 3),
('Understanding of Equality and Equity, and importance of Equality & Equity, Discrimination in the Family, Community, and Government?', 'Active', 'Pakhwada Input', 4),
('Understanding of Gender', 'Active', 'Pakhwada Input', 5),
('Beyond Boxes - Let''s Understand What Gender Roles Are, and How Does Their Socialization Happen?', 'Active', 'Pakhwada Input', 6),
('Understanding of Care work and Unpaid Domestic and Care Work', 'Active', 'Pakhwada Input', 7),
('Demonstration of Unpaid care work - Sajhedari mela', 'Active', 'Pakhwada Input', 8),
('Let''s Understand What Non-Traditional Professions (NTP) Are and The Role of Boys and Men in Creating Women''s Access to NTP', 'Active', 'Pakhwada Input', 9),
('Understanding Systems of Power – Exploring Power and Privileges and Restrictions on Men and Boys, and Women and Girls', 'Active', 'Pakhwada Input', 10),
('Understanding the Intersections of Power', 'Active', 'Pakhwada Input', 11),
('Unpacking Masculinities - Exploring Masculinities and its Impact on Men and Boys', 'Active', 'Pakhwada Input', 12),
('Understanding Gender-Based Violence', 'Active', 'Pakhwada Input', 13),
('Violence and Masculinities', 'Active', 'Pakhwada Input', 14),
('Gender''s Connection to and Impact on Slurs, Proverbs, and Culture', 'Active', 'Pakhwada Input', 15),
('Bystanders - The Role of Boys and Men in Preventing Gender-Based Violence', 'Active', 'Pakhwada Input', 16),
('Let''s Talk Sexuality - Understanding Sexuality and Our Bodies', 'Active', 'Pakhwada Input', 17),
('Beyond binaries and Sexual diversities', 'Active', 'Pakhwada Input', 18),
('Masculinity and Sexuality, Consent, Ideal relationship', 'Active', 'Pakhwada Input', 19),
('Understanding of Self and others', 'Active', 'Pakhwada Input', 20),
('Emotion management', 'Active', 'Pakhwada Input', 21),
('Life Skills - Communication, Empathy', 'Active', 'Pakhwada Input', 22),
('Problem Solving and Decision making', 'Active', 'Pakhwada Input', 23),
('Redressal mechanism and its Impact on Men/boys and women/girls', 'Active', 'Pakhwada Input', 24),
('Reframing masculinities - Exploring alternative / Positive Masculinities', 'Active', 'Pakhwada Input', 25),
('Understanding backlashes / Manosphere and develop Strategies to deal - Digital, media', 'Active', 'Pakhwada Input', 26),
('Breaking the Mould - Exploring Stereotypes', 'Active', 'Pakhwada Input', 27),
('Impact on Men/Boys & Girls/Women & Why men should engage in Care work', 'Active', 'Pakhwada Input', 28);

COMMIT;
