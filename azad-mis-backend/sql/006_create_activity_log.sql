-- 006_create_activity_log.sql
-- System-wide activity log table

CREATE TABLE IF NOT EXISTS system_activity_log (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id) ON DELETE SET NULL,
    user_name       VARCHAR(200),
    role_name       VARCHAR(100),
    action          VARCHAR(200) NOT NULL,
    resource_type   VARCHAR(100),
    resource_id     INT,
    ip_address      VARCHAR(45),
    city            VARCHAR(100),
    description     TEXT,
    source          VARCHAR(20) DEFAULT 'web',  -- 'web' or 'mobile'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_log_user ON system_activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_system_log_created ON system_activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_log_action ON system_activity_log(action);


-- Seed demo log entries
INSERT INTO system_activity_log (user_id, user_name, role_name, action, resource_type, resource_id, ip_address, city, description, source, created_at) VALUES
(1, 'Kedar Dash',    'Super Admin',          'Login',               NULL,         NULL, '103.25.41.12',  'Delhi',    'User logged in successfully',                           'web',    NOW() - INTERVAL '6 hours'),
(2, 'Nisha Sharma',  'Admin',                'Login',               NULL,         NULL, '49.37.192.88',  'Delhi',    'User logged in successfully',                           'web',    NOW() - INTERVAL '5 hours 50 minutes'),
(3, 'Ramesh Kumar',  'Project Investigator', 'Login',               NULL,         NULL, '106.210.45.3',  'Delhi',    'User logged in successfully',                           'web',    NOW() - INTERVAL '5 hours 40 minutes'),
(4, 'Sulpa Kumari',  'FLP (Mobile)',         'Login',               NULL,         NULL, '122.161.78.55', 'Delhi',    'User logged in via mobile app',                         'mobile', NOW() - INTERVAL '5 hours 30 minutes'),
(1, 'Kedar Dash',    'Super Admin',          'Create FLP',          'FLP',        12,   '103.25.41.12',  'Delhi',    'Created new FLP: Priya Devi (EN-DEL-012)',              'web',    NOW() - INTERVAL '5 hours 20 minutes'),
(3, 'Ramesh Kumar',  'Project Investigator', 'Edit FLP',            'FLP',        5,    '106.210.45.3',  'Delhi',    'Updated bank details for FLP: Anita Sharma (EN-DEL-005)', 'web',  NOW() - INTERVAL '5 hours'),
(4, 'Sulpa Kumari',  'FLP (Mobile)',         'Submit Survey',       'Survey',     8,    '122.161.78.55', 'Delhi',    'Submitted community survey SRV-DEL-008',                'mobile', NOW() - INTERVAL '4 hours 45 minutes'),
(2, 'Nisha Sharma',  'Admin',                'Approve Survey',      'Survey',     8,    '49.37.192.88',  'Delhi',    'Approved survey SRV-DEL-008 submitted by Sulpa Kumari', 'web',    NOW() - INTERVAL '4 hours 30 minutes'),
(1, 'Kedar Dash',    'Super Admin',          'Create Training',     'Training',   7,    '103.25.41.12',  'Delhi',    'Created training: Gender Sensitization Workshop Phase I', 'web',   NOW() - INTERVAL '4 hours'),
(3, 'Ramesh Kumar',  'Project Investigator', 'Assign Participants', 'Training',   7,    '106.210.45.3',  'Delhi',    'Assigned 8 FLPs to training #7',                        'web',    NOW() - INTERVAL '3 hours 45 minutes'),
(5, 'Dr. Meera Nair','Power User',           'Login',               NULL,         NULL, '14.139.85.200', 'Chennai',  'User logged in successfully',                           'web',    NOW() - INTERVAL '3 hours 30 minutes'),
(5, 'Dr. Meera Nair','Power User',           'View Report',         'Report',     NULL, '14.139.85.200', 'Chennai',  'Viewed FLP performance dashboard report',               'web',    NOW() - INTERVAL '3 hours 20 minutes'),
(5, 'Dr. Meera Nair','Power User',           'Export Report',       'Report',     NULL, '14.139.85.200', 'Chennai',  'Exported FLP summary report as Excel',                  'web',    NOW() - INTERVAL '3 hours 10 minutes'),
(4, 'Sulpa Kumari',  'FLP (Mobile)',         'Submit Survey',       'Survey',     9,    '122.161.50.22', 'Delhi',    'Submitted community survey SRV-DEL-009',                'mobile', NOW() - INTERVAL '3 hours'),
(3, 'Ramesh Kumar',  'Project Investigator', 'Create Assessment',   'Assessment', 22,   '106.210.45.3',  'Delhi',    'Created pre-training assessment for FLP: Kavita Devi',  'web',    NOW() - INTERVAL '2 hours 45 minutes'),
(2, 'Nisha Sharma',  'Admin',                'Edit User',           'User',       3,    '49.37.192.88',  'Delhi',    'Updated role for user: Ramesh Kumar',                   'web',    NOW() - INTERVAL '2 hours 30 minutes'),
(1, 'Kedar Dash',    'Super Admin',          'Create Centre',       'Centre',     6,    '103.25.41.12',  'Delhi',    'Created new centre: Lucknow Centre',                    'web',    NOW() - INTERVAL '2 hours'),
(1, 'Kedar Dash',    'Super Admin',          'Create Batch',        'Batch',      5,    '103.25.41.12',  'Delhi',    'Created batch: Batch 2025-B under Lucknow Centre',      'web',    NOW() - INTERVAL '1 hour 45 minutes'),
(4, 'Sulpa Kumari',  'FLP (Mobile)',         'Submit Survey',       'Survey',     10,   '103.86.14.90',  'Kolkata',  'Submitted community survey SRV-KOL-010',                'mobile', NOW() - INTERVAL '1 hour 30 minutes'),
(2, 'Nisha Sharma',  'Admin',                'Reset Password',      'User',       4,    '49.37.192.88',  'Delhi',    'Reset password for user: Sulpa Kumari',                 'web',    NOW() - INTERVAL '1 hour'),
(3, 'Ramesh Kumar',  'Project Investigator', 'Edit FLP',            'FLP',        8,    '106.210.45.3',  'Delhi',    'Updated employment details for FLP: Meena Singh (EN-DEL-008)', 'web', NOW() - INTERVAL '45 minutes'),
(1, 'Kedar Dash',    'Super Admin',          'View Report',         'Report',     NULL, '103.25.41.12',  'Delhi',    'Viewed assessment comparison report',                   'web',    NOW() - INTERVAL '30 minutes'),
(4, 'Sulpa Kumari',  'FLP (Mobile)',         'Submit Survey',       'Survey',     11,   '122.161.78.55', 'Delhi',    'Submitted community survey SRV-DEL-011',                'mobile', NOW() - INTERVAL '15 minutes'),
(2, 'Nisha Sharma',  'Admin',                'Login',               NULL,         NULL, '59.144.112.6',  'Jaipur',   'User logged in successfully',                           'web',    NOW() - INTERVAL '10 minutes'),
(2, 'Nisha Sharma',  'Admin',                'Approve Survey',      'Survey',     9,    '59.144.112.6',  'Jaipur',   'Approved survey SRV-DEL-009 submitted by Sulpa Kumari', 'web',    NOW() - INTERVAL '5 minutes');
