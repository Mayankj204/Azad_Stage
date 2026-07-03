-- =============================================
-- 011: Dashboard KPI & Role Restructuring
-- Adds username column to users, new State Coordinator role,
-- and 4 new user accounts
-- =============================================

-- 1. Add username column to users table (for login by username)
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE;

-- Set usernames for existing users
UPDATE users SET username = 'admin' WHERE id = 1;
UPDATE users SET username = 'nisha' WHERE id = 2;
UPDATE users SET username = 'ramesh' WHERE id = 3;
UPDATE users SET username = 'sulpa' WHERE id = 4;
UPDATE users SET username = 'meera' WHERE id = 5;

-- 2. Insert new "State Coordinator" role
INSERT INTO roles (id, name, description) VALUES
(6, 'State Coordinator', 'Manages state operations. Allocates quarterly targets to centres for surveys and other activities. Can view all centre data within assigned state.')
ON CONFLICT (id) DO NOTHING;
SELECT setval('roles_id_seq', GREATEST((SELECT MAX(id) FROM roles), 6));

-- 3. Create new user accounts
-- admin1 (Admin role, password: zaq@123)
INSERT INTO users (id, name, email, username, password_hash, role_id, geo_scope, status) VALUES
(6, 'Admin User', 'admin1@azad.org', 'admin1', '$2b$12$LonyBIA9x/i7AlAeFdgse.SHhv4TZ1S/45RHoQitvlAB3Rj..vkNy', 2, 'National (All Centres)', 'Active')
ON CONFLICT (id) DO NOTHING;

-- admin-delhi (State Coordinator role, password: qwerty@123)
INSERT INTO users (id, name, email, username, password_hash, role_id, geo_scope, status) VALUES
(7, 'Delhi State Coordinator', 'admin-delhi@azad.org', 'admin-delhi', '$2b$12$cxlcE.BXHuSaSla5sGq0Le0ervg1yiN4TJ2NkzaJ2EncJH9LuiTiK', 6, 'Delhi', 'Active')
ON CONFLICT (id) DO NOTHING;

-- admin-south-delhi (PI/Centre Incharge role, password: qwerty@123)
INSERT INTO users (id, name, email, username, password_hash, role_id, geo_scope, status) VALUES
(8, 'South Delhi Centre Incharge', 'admin-south-delhi@azad.org', 'admin-south-delhi', '$2b$12$cxlcE.BXHuSaSla5sGq0Le0ervg1yiN4TJ2NkzaJ2EncJH9LuiTiK', 3, 'Delhi Centre', 'Active')
ON CONFLICT (id) DO NOTHING;

-- flp1 (FLP Mobile User role, password: zaq@123)
INSERT INTO users (id, name, email, username, password_hash, role_id, geo_scope, status) VALUES
(9, 'FLP User', 'flp1@azad.org', 'flp1', '$2b$12$LonyBIA9x/i7AlAeFdgse.SHhv4TZ1S/45RHoQitvlAB3Rj..vkNy', 4, 'Delhi Centre', 'Active')
ON CONFLICT (id) DO NOTHING;

SELECT setval('users_id_seq', GREATEST((SELECT MAX(id) FROM users), 9));
