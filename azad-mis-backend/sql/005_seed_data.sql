-- =============================================
-- Azad Foundation MIS - Seed Data
-- =============================================

-- States
INSERT INTO states (id, name) VALUES
(1, 'Delhi'),
(2, 'West Bengal'),
(3, 'Rajasthan'),
(4, 'Tamil Nadu'),
(5, 'Madhya Pradesh');
SELECT setval('states_id_seq', 5);

-- Districts
INSERT INTO districts (id, name, state_id) VALUES
(1, 'South Delhi', 1),
(2, 'North Delhi', 1),
(3, 'East Delhi', 1),
(4, 'New Delhi', 1),
(5, 'North 24 Parganas', 2),
(6, 'South 24 Parganas', 2),
(7, 'Jaipur', 3),
(8, 'Chennai', 4),
(9, 'Indore', 5);
SELECT setval('districts_id_seq', 9);

-- Cities
INSERT INTO cities (id, name, district_id, bastis_count) VALUES
(1, 'Sangam Vihar', 1, 5),
(2, 'Tughlakabad', 1, 3),
(3, 'Ambedkar Nagar', 1, 4),
(4, 'Seelampur', 2, 3),
(5, 'Jafrabad', 2, 2),
(6, 'Trilokpuri', 3, 2),
(7, 'Kalyanpuri', 3, 2),
(8, 'New Barrackpore', 5, 4),
(9, 'Baranagar', 5, 3),
(10, 'Jhotwara', 7, 2),
(11, 'Sanganer', 7, 2),
(12, 'Vyasarpadi', 8, 3),
(13, 'Tondiarpet', 8, 2),
(14, 'Mhow', 9, 2);
SELECT setval('cities_id_seq', 14);

-- Centres
INSERT INTO centres (id, name, state_id) VALUES
(1, 'Delhi Centre', 1),
(2, 'Kolkata Centre', 2),
(3, 'Jaipur Centre', 3),
(4, 'Chennai Centre', 4),
(5, 'Indore Centre', 5);
SELECT setval('centres_id_seq', 5);

-- Batches
INSERT INTO batches (id, name, year, centre_id) VALUES
(1, 'Batch 6', '2023-24', 1),
(2, 'Batch 7', '2024-25', 1),
(3, 'Batch 7', '2024-25', 2),
(4, 'Batch 7', '2024-25', 3);
SELECT setval('batches_id_seq', 4);

-- Roles
INSERT INTO roles (id, name, description) VALUES
(1, 'Super Admin', 'Full system access including Master Data, Settings, all configuration parameters, user & role management, and all operational modules'),
(2, 'Admin', 'User management, all operational modules (FLP, Activity, Assessment). Cannot manage Master Data or critical configuration parameters'),
(3, 'Project Investigator (PI)', 'FLP data entry, document upload, training allocation, survey review. Linked to a specific Centre — can only see data for their own Centre'),
(4, 'FLP (Mobile User)', 'Mobile-only access. Can conduct community surveys via mobile app. Cannot access web portal'),
(5, 'Power User', 'View-only access to all dashboards, reports, FLP data, surveys, assessments across all centres. Strategic-level users — no data entry');
SELECT setval('roles_id_seq', 5);

-- Users (passwords hashed with bcrypt — plaintext: zaq@123)
INSERT INTO users (id, name, email, password_hash, role_id, geo_scope, status, last_login) VALUES
(1, 'Kedar Dash', 'kedar@azad.org', '$2b$12$LJ3m7cGzUxBCgPj1fR3Yde2J3Lk5oCvS.B6m7aHn8E.rXqHSWYd7e', 1, 'National (All Centres)', 'Active', '2026-02-14'),
(2, 'Nisha Sharma', 'nisha@azad.org', '$2b$12$LJ3m7cGzUxBCgPj1fR3Yde2J3Lk5oCvS.B6m7aHn8E.rXqHSWYd7e', 2, 'National (All Centres)', 'Active', '2026-02-13'),
(3, 'Ramesh Kumar', 'ramesh@azad.org', '$2b$12$LJ3m7cGzUxBCgPj1fR3Yde2J3Lk5oCvS.B6m7aHn8E.rXqHSWYd7e', 3, 'Delhi Centre', 'Active', '2026-02-12'),
(4, 'Sulpa Kumari', 'sulpa.flp@azad.org', '$2b$12$LJ3m7cGzUxBCgPj1fR3Yde2J3Lk5oCvS.B6m7aHn8E.rXqHSWYd7e', 4, 'Delhi Centre', 'Active', '2026-02-10'),
(5, 'Dr. Meera Nair', 'meera@azad.org', '$2b$12$LJ3m7cGzUxBCgPj1fR3Yde2J3Lk5oCvS.B6m7aHn8E.rXqHSWYd7e', 5, 'National (All Centres)', 'Active', '2026-02-11');
SELECT setval('users_id_seq', 5);

-- Training Topics
INSERT INTO training_topics (id, name) VALUES
(1, 'Gender & Patriarchy'),
(2, 'Gender Based Violence (GBV)'),
(3, 'Sexual & Reproductive Health Rights (SRHR)'),
(4, 'NTL & Women with Work'),
(5, 'Mobilization Strategies'),
(6, 'Social Security Schemes & Citizenship Documents'),
(7, 'Governance & Constitution'),
(8, 'GBV & Laws'),
(9, 'Communication'),
(10, 'Digital & Financial Literacy'),
(11, 'Self, Leadership & Power'),
(12, 'Understanding Community Work');
SELECT setval('training_topics_id_seq', 12);

-- FLPs (23 named FLPs from prototype)
INSERT INTO flps (id, enrollment_number, centre_id, batch_id, name, status, date_of_birth, age_at_enrollment, address, email, mobile, caste_category, community_religion, marital_status, number_of_children, education, monthly_family_income, family_members_count, per_capita_income, bank_name, account_holder_name, account_number, bank_branch, ifsc_code, worked_before, flp_relation, why_join_flp, challenges, future_goal, username) VALUES
-- Delhi - Batch 6
(1, 'FLP/DL/SD/2023-24/01', 1, 1, 'Sulpa Kumari', 'Active', '2000-03-15', 23, 'H.No 45, Sangam Vihar, New Delhi', 'sulpa.kumari@email.com', '9876543210', 'SC', 'Hindu', 'Unmarried', 0, '12th', 17000, 6, 2833, 'State Bank of India', 'Sulpa Kumari', 'XXXX XXXX 4521', 'Sangam Vihar', 'SBIN0012345', false, 'Self-motivated', ARRAY['Women empowerment','Financial independence','Community service'], 'Travel distance', 'Social worker', 'flp.sulpa.kumari@azad'),
(2, 'FLP/DL/SD/2023-24/02', 1, 1, 'Pooja', 'Active', '2001-07-22', 22, 'Tughlakabad, New Delhi', 'pooja@email.com', '9876543211', 'OBC', 'Hindu', 'Unmarried', 0, '10th', 15000, 5, 3000, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Financial independence','Learning new skills'], 'Family resistance', 'Driver', 'flp.pooja@azad'),
(3, 'FLP/DL/SD/2023-24/03', 1, 1, 'Pooja Kumari', 'Active', '1999-11-05', 24, 'Ambedkar Nagar, New Delhi', 'pooja.k@email.com', '9876543212', 'SC', 'Hindu', 'Married', 1, '8th', 12000, 4, 3000, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Women empowerment','Personal development'], 'Child care', 'Social worker', 'flp.pooja.kumari@azad'),
(4, 'FLP/DL/SD/2023-24/04', 1, 1, 'Rekha Devi', 'Active', '1998-04-10', 25, 'Sangam Vihar, New Delhi', NULL, '9876543213', 'OBC', 'Hindu', 'Married', 2, '5th', 14000, 5, 2800, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Financial independence'], 'Travel distance', 'Entrepreneur', NULL),
(5, 'FLP/DL/SD/2023-24/05', 1, 1, 'Sunita Yadav', 'Active', '2000-09-18', 23, 'Tughlakabad, New Delhi', NULL, '9876543214', 'OBC', 'Hindu', 'Unmarried', 0, '12th', 16000, 5, 3200, NULL, NULL, NULL, NULL, NULL, false, 'Father', ARRAY['Learning new skills','Career growth'], 'Financial constraints', 'Teacher', NULL),
(6, 'FLP/DL/SD/2023-24/06', 1, 1, 'Neha Gupta', 'Active', '2001-01-25', 22, 'Seelampur, New Delhi', NULL, '9876543215', 'General', 'Hindu', 'Unmarried', 0, '12th', 20000, 4, 5000, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Women empowerment'], 'Family resistance', 'Government job', NULL),
(7, 'FLP/DL/SD/2023-24/07', 1, 1, 'Anjali Devi', 'Active', '1997-06-12', 26, 'Sangam Vihar, New Delhi', NULL, '9876543216', 'SC', 'Hindu', 'Married', 1, '10th', 11000, 6, 1833, NULL, NULL, NULL, NULL, NULL, true, 'Self', ARRAY['Financial independence','Community service'], 'Child care', 'Social worker', NULL),
(8, 'FLP/DL/SD/2023-24/08', 1, 1, 'Renu Kumari', 'Active', '2000-12-30', 23, 'Ambedkar Nagar, New Delhi', NULL, '9876543217', 'SC', 'Hindu', 'Unmarried', 0, '10th', 13000, 5, 2600, NULL, NULL, NULL, NULL, NULL, false, 'Brother', ARRAY['Career growth'], 'Travel distance', 'Driver', NULL),
(9, 'FLP/DL/SD/2023-24/09', 1, 1, 'Manju Devi', 'Active', '1999-03-08', 24, 'Trilokpuri, New Delhi', NULL, '9876543218', 'OBC', 'Hindu', 'Married', 2, '8th', 10000, 7, 1428, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Women empowerment','Financial independence'], 'Health issues', 'Social worker', NULL),
(10, 'FLP/DL/SD/2023-24/10', 1, 1, 'Savita Kumari', 'Active', '2001-08-14', 22, 'Kalyanpuri, New Delhi', NULL, '9876543219', 'SC', 'Hindu', 'Unmarried', 0, '12th', 18000, 5, 3600, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Learning new skills'], 'Financial constraints', 'Entrepreneur', NULL),
(11, 'FLP/DL/SD/2023-24/11', 1, 1, 'Poonam Devi', 'Active', '1998-11-20', 25, 'Jafrabad, New Delhi', NULL, '9876543220', 'OBC', 'Muslim', 'Married', 1, '5th', 9000, 6, 1500, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Financial independence'], 'Family resistance', 'Social worker', NULL),
(12, 'FLP/DL/SD/2023-24/12', 1, 1, 'Suman Kumari', 'Active', '2000-05-05', 23, 'Sangam Vihar, New Delhi', NULL, '9876543221', 'SC', 'Hindu', 'Unmarried', 0, '10th', 14000, 4, 3500, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment','Career growth'], 'Travel distance', 'Teacher', NULL),
(13, 'FLP/DL/SD/2023-24/13', 1, 1, 'Kiran Devi', 'Active', '1999-07-15', 24, 'Tughlakabad, New Delhi', NULL, '9876543222', 'OBC', 'Hindu', 'Married', 1, '8th', 11000, 5, 2200, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Financial independence'], 'Child care', 'Social worker', NULL),
(14, 'FLP/DL/SD/2023-24/14', 1, 1, 'Asha Kumari', 'Walkout', '2001-02-28', 22, 'Seelampur, New Delhi', NULL, '9876543223', 'General', 'Hindu', 'Unmarried', 0, '12th', 22000, 4, 5500, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Learning new skills'], 'Family resistance', 'Government job', NULL),
(15, 'FLP/DL/SD/2023-24/15', 1, 1, 'Babita Devi', 'Active', '2000-10-10', 23, 'Ambedkar Nagar, New Delhi', NULL, '9876543224', 'SC', 'Hindu', 'Unmarried', 0, '10th', 12000, 5, 2400, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Community service'], 'Travel distance', 'Social worker', NULL),
-- Delhi - Batch 7
(16, 'FLP/DL/SD/2024-25/01', 1, 2, 'Sapna Kumari', 'Active', '2002-04-18', 22, 'Sangam Vihar, New Delhi', NULL, '9876543225', 'SC', 'Hindu', 'Unmarried', 0, '12th', 15000, 5, 3000, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment'], 'Travel distance', 'Driver', NULL),
(17, 'FLP/DL/SD/2024-25/02', 1, 2, 'Geeta Rani', 'Active', '2001-09-22', 23, 'Tughlakabad, New Delhi', NULL, '9876543226', 'OBC', 'Hindu', 'Unmarried', 0, '10th', 13000, 4, 3250, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Financial independence'], 'Family resistance', 'Social worker', NULL),
(18, 'FLP/DL/SD/2024-25/03', 1, 2, 'Pinky Devi', 'Active', '2002-01-05', 22, 'Seelampur, New Delhi', NULL, '9876543227', 'SC', 'Hindu', 'Unmarried', 0, '8th', 10000, 6, 1666, NULL, NULL, NULL, NULL, NULL, false, 'Father', ARRAY['Learning new skills'], 'Financial constraints', 'Entrepreneur', NULL),
-- Kolkata
(19, 'FLP/KO/NB/2024-25/01', 2, 3, 'Priya Das', 'Active', '2000-06-20', 24, 'New Barrackpore, Kolkata', NULL, '9876543228', 'General', 'Hindu', 'Unmarried', 0, '12th', 14000, 4, 3500, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment','Community service'], 'Travel distance', 'Social worker', NULL),
(20, 'FLP/KO/NB/2024-25/02', 2, 3, 'Anita Roy', 'Walkout', '1999-12-15', 25, 'Baranagar, Kolkata', NULL, '9876543229', 'General', 'Hindu', 'Married', 1, '10th', 12000, 5, 2400, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Financial independence'], 'Family resistance', 'Teacher', NULL),
(21, 'FLP/KO/NB/2023-24/03', 2, 3, 'Rima Mondal', 'Active', '2001-03-10', 22, 'New Barrackpore, Kolkata', NULL, '9876543230', 'OBC', 'Hindu', 'Unmarried', 0, '12th', 11000, 5, 2200, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Learning new skills','Career growth'], 'Travel distance', 'Driver', NULL),
-- Jaipur
(22, 'FLP/JP/JC/2024-25/01', 3, 4, 'Kavita Sharma', 'Active', '2000-08-25', 23, 'Jhotwara, Jaipur', NULL, '9876543231', 'OBC', 'Hindu', 'Unmarried', 0, '12th', 16000, 5, 3200, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment','Financial independence'], 'Travel distance', 'Social worker', NULL),
(23, 'FLP/JP/JC/2023-24/02', 3, 4, 'Sonu Kanwar', 'Active', '1999-05-12', 24, 'Sanganer, Jaipur', NULL, '9876543232', 'General', 'Hindu', 'Married', 1, '10th', 13000, 6, 2166, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Financial independence'], 'Child care', 'Entrepreneur', NULL),
(24, 'FLP/JP/JC/2023-24/03', 3, 4, 'Geeta Meena', 'Active', '2001-11-30', 22, 'Jhotwara, Jaipur', NULL, '9876543233', 'ST', 'Hindu', 'Unmarried', 0, '8th', 9000, 7, 1285, NULL, NULL, NULL, NULL, NULL, false, 'Father', ARRAY['Community service'], 'Financial constraints', 'Social worker', NULL),
-- Chennai
(25, 'FLP/CH/CC/2024-25/01', 4, NULL, 'Lakshmi S', 'Active', '2000-02-14', 24, 'Vyasarpadi, Chennai', NULL, '9876543234', 'SC', 'Hindu', 'Unmarried', 0, '12th', 15000, 4, 3750, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment','Learning new skills'], 'Travel distance', 'Teacher', NULL),
(26, 'FLP/CH/CC/2023-24/02', 4, NULL, 'Selvi M', 'Active', '1998-09-08', 25, 'Tondiarpet, Chennai', NULL, '9876543235', 'OBC', 'Hindu', 'Married', 2, '10th', 12000, 6, 2000, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Financial independence'], 'Family resistance', 'Social worker', NULL),
(27, 'FLP/CH/CC/2023-24/03', 4, NULL, 'Devi Priya R', 'Active', '2001-04-20', 22, 'Vyasarpadi, Chennai', NULL, '9876543236', 'SC', 'Hindu', 'Unmarried', 0, '12th', 14000, 5, 2800, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Career growth'], 'Travel distance', 'Driver', NULL),
-- Indore
(28, 'FLP/IN/IC/2024-25/01', 5, NULL, 'Meena Patel', 'Active', '2000-07-07', 23, 'Mhow, Indore', NULL, '9876543237', 'OBC', 'Hindu', 'Unmarried', 0, '12th', 11000, 4, 2750, NULL, NULL, NULL, NULL, NULL, false, 'Self', ARRAY['Women empowerment'], 'Travel distance', 'Social worker', NULL),
(29, 'FLP/IN/IC/2023-24/02', 5, NULL, 'Sunita Malviya', 'Active', '1999-10-25', 24, 'Mhow, Indore', NULL, '9876543238', 'OBC', 'Hindu', 'Married', 1, '10th', 10000, 5, 2000, NULL, NULL, NULL, NULL, NULL, false, 'Husband', ARRAY['Financial independence'], 'Child care', 'Entrepreneur', NULL),
(30, 'FLP/IN/IC/2023-24/03', 5, NULL, 'Rani Yadav', 'Active', '2001-06-18', 22, 'Mhow, Indore', NULL, '9876543239', 'OBC', 'Hindu', 'Unmarried', 0, '8th', 8000, 6, 1333, NULL, NULL, NULL, NULL, NULL, false, 'Mother', ARRAY['Community service','Learning new skills'], 'Financial constraints', 'Social worker', NULL);
SELECT setval('flps_id_seq', 30);

-- Family Members for Sulpa Kumari (FLP ID 1)
INSERT INTO flp_family_members (flp_id, name, relation, age, education, occupation, monthly_income) VALUES
(1, 'Kailash Chand', 'Father', 45, '5th', 'Shop keeper', 5000),
(1, 'Neetu Devi', 'Mother', 38, 'Uneducated', 'House wife', 0),
(1, 'Shiva', 'Brother', 23, '6th', 'Unemployed', 0),
(1, 'Shivam', 'Brother', 20, '7th', 'Helper', 12000),
(1, 'Vanshika', 'Sister', 13, '9th', 'Student', 0);

-- Documents for Sulpa Kumari
INSERT INTO flp_documents (flp_id, file_name, document_type, upload_date, uploaded_by) VALUES
(1, 'aadhaar_card.pdf', 'Aadhaar Card', '2025-06-15', 'PI - Admin'),
(1, 'photo.jpg', 'Photograph', '2025-06-15', 'PI - Admin');

-- Activity Log for Sulpa Kumari
INSERT INTO flp_activity_log (flp_id, action, ip_address, description, created_at) VALUES
(1, 'Profile Created', '192.168.1.100', 'FLP profile created by PI Admin', '2025-06-15 10:30:00+05:30'),
(1, 'Bank Details Added', '192.168.1.100', 'Bank information updated', '2025-06-15 10:35:00+05:30'),
(1, 'Documents Uploaded', '192.168.1.100', 'Aadhaar Card and Photograph uploaded', '2025-06-15 10:40:00+05:30'),
(1, 'Credentials Generated', '192.168.1.100', 'Mobile app credentials dispatched via Email & SMS', '2025-06-16 09:00:00+05:30'),
(1, 'Training Assigned', '192.168.1.101', 'Assigned to Phase I training - Batch 6', '2025-07-01 14:20:00+05:30');

-- Trainings
INSERT INTO trainings (id, centre_id, phase, start_date, end_date, title, trainer_names, venue) VALUES
(1, 1, 'Phase I', '2023-07-07', '2023-07-09', 'Gender & Patriarchy, GBV - Batch 6', 'Dr. Anita Sharma, Priya Verma', 'Azad Foundation Training Centre, Sangam Vihar, Delhi'),
(2, 1, 'Phase I', '2023-07-10', '2023-07-11', 'SRHR - Batch 6', 'Dr. Anita Sharma', 'Azad Foundation Training Centre, Sangam Vihar, Delhi'),
(3, 1, 'Phase II', '2023-09-18', '2023-09-21', 'Social Security, Constitution, GBV & Laws - Batch 6', 'Priya Verma, Ramesh Kumar', 'Azad Foundation Training Centre, Delhi'),
(4, 1, 'Phase III', '2023-12-07', '2023-12-17', 'Communication, Digital Literacy, Leadership - Batch 6', 'Dr. Anita Sharma, Priya Verma', 'Azad Foundation Training Centre, Delhi'),
(5, 2, 'Phase I', '2024-08-15', '2024-08-18', 'Gender & Patriarchy, SRHR, Mobilization', 'Priya Sen, Ritu Das', 'Kolkata Centre'),
(6, 3, 'Phase I', '2025-02-05', '2025-02-08', 'Gender & Patriarchy, GBV, NTL', 'Kavita Joshi', 'Jaipur Centre');
SELECT setval('trainings_id_seq', 6);

-- Training Topic Mappings
INSERT INTO training_topic_map (training_id, topic_id) VALUES
(1, 1), (1, 2),          -- Training 1: Gender & Patriarchy, GBV
(2, 3),                   -- Training 2: SRHR
(3, 6), (3, 7), (3, 8),  -- Training 3: Social Security, Constitution, GBV & Laws
(4, 9), (4, 10), (4, 11),-- Training 4: Communication, Digital Literacy, Leadership
(5, 1), (5, 3), (5, 5),  -- Training 5: Gender, SRHR, Mobilization
(6, 1), (6, 2), (6, 4);  -- Training 6: Gender, GBV, NTL

-- Training Participants (Training 1 - 15 participants from Delhi Batch 6)
INSERT INTO training_participants (training_id, flp_id, attendance) VALUES
(1, 1, 'Present'), (1, 2, 'Present'), (1, 3, 'Present'), (1, 4, 'Present'),
(1, 5, 'Present'), (1, 6, 'Absent'), (1, 7, 'Present'), (1, 8, 'Present'),
(1, 9, 'Present'), (1, 10, 'Present'), (1, 11, 'Present'), (1, 12, 'Present'),
(1, 13, 'Present'), (1, 14, 'Absent'), (1, 15, 'Present');

-- Surveys
INSERT INTO surveys (id, survey_id_code, flp_id, date, status,
  sec_a_state, sec_a_surveyor, sec_a_designation, sec_a_quarter,
  sec_b_basti, sec_b_district, sec_b_centre, sec_b_area, sec_b_address,
  sec_c_respondent_name, sec_c_contact, sec_c_caste, sec_c_community,
  sec_d_total_family_members, sec_d_monthly_income, sec_d_per_capita, sec_d_decision_maker,
  sec_g_woman_name, sec_g_woman_age, sec_g_woman_education, sec_g_interested_www, sec_g_training_preference, sec_g_eligible,
  gps_lat, gps_lng, gps_accuracy, start_time, duration_minutes, sync_time) VALUES
(1, 'SRV-DL-00001', 1, '2023-06-15', 'Approved',
  'Delhi', 'Sulpa Kumari', 'FLP', 'Q1 (Apr-Jun)',
  'Sangam Vihar', 'South Delhi', 'Delhi Centre', 'J-Block', 'H.No 112, J-Block, Sangam Vihar',
  'Geeta Devi', '98XXXXXXXX', 'OBC', 'Hindu',
  6, 18000, 3000, 'Male Head',
  'Radha Devi', 28, '8th Pass', true, '2-Wheeler', true,
  28.5095, 77.2410, 4.2, '2023-06-15 10:15:00+05:30', 22, '2023-06-15 14:30:00+05:30'),
(2, 'SRV-DL-00002', 1, '2023-06-16', 'Approved',
  'Delhi', 'Sulpa Kumari', 'FLP', 'Q1 (Apr-Jun)',
  'Sangam Vihar', 'South Delhi', 'Delhi Centre', 'K-Block', 'H.No 56, K-Block, Sangam Vihar',
  'Kamla Devi', '98XXXXXXXX', 'SC', 'Hindu',
  5, 15000, 3000, 'Female Head',
  'Asha Devi', 32, '10th Pass', true, '4-Wheeler', true,
  28.5100, 77.2420, 3.8, '2023-06-16 11:00:00+05:30', 18, '2023-06-16 15:00:00+05:30'),
(3, 'SRV-DL-00003', 2, '2023-06-18', 'Submitted',
  'Delhi', 'Pooja', 'FLP', 'Q1 (Apr-Jun)',
  'Tughlakabad', 'South Delhi', 'Delhi Centre', 'A-Block', 'H.No 34, A-Block, Tughlakabad',
  'Sita Rani', '97XXXXXXXX', 'OBC', 'Hindu',
  4, 12000, 3000, 'Male Head',
  'Meena Devi', 25, '8th Pass', true, '2-Wheeler', true,
  28.5200, 77.2500, 5.1, '2023-06-18 09:30:00+05:30', 25, '2023-06-18 13:00:00+05:30'),
(4, 'SRV-KO-00001', 19, '2024-09-10', 'Approved',
  'West Bengal', 'Priya Das', 'FLP', 'Q2 (Jul-Sep)',
  'New Barrackpore', 'North 24 Parganas', 'Kolkata Centre', 'Ward 5', 'H.No 22, Ward 5, New Barrackpore',
  'Asha Mondal', '96XXXXXXXX', 'General', 'Hindu',
  5, 16000, 3200, 'Male Head',
  'Sunita Mondal', 24, '10th Pass', true, '2-Wheeler', true,
  22.5800, 88.3700, 4.5, '2024-09-10 10:00:00+05:30', 20, '2024-09-10 14:00:00+05:30'),
(5, 'SRV-KO-00002', 19, '2024-09-11', 'Rejected',
  'West Bengal', 'Priya Das', 'FLP', 'Q2 (Jul-Sep)',
  'New Barrackpore', 'North 24 Parganas', 'Kolkata Centre', 'Ward 8', 'H.No 45, Ward 8, New Barrackpore',
  'Bina Sarkar', '95XXXXXXXX', 'SC', 'Hindu',
  7, 10000, 1428, 'Male Head',
  NULL, NULL, NULL, false, NULL, false,
  22.5810, 88.3710, 6.0, '2024-09-11 11:00:00+05:30', 15, '2024-09-11 15:00:00+05:30');
SELECT setval('surveys_id_seq', 5);

-- WWW Pipeline
INSERT INTO www_pipeline (name, age, district, survey_id, surveyed_by_flp_id, training_preference, stage) VALUES
('Radha Devi', 28, 'South Delhi', 1, 1, '2-Wheeler', 'Shortlisted'),
('Meena Kumari', 35, 'South Delhi', NULL, 2, '4-Wheeler', 'Contacted'),
('Asha Mondal', 22, 'North 24 Parganas', 4, 19, '2-Wheeler', 'Potential'),
('Lakshmi R', 30, 'Chennai', NULL, 25, '2-Wheeler', 'Enrolled');

-- Assessments (Pre-Training for all 15 FLPs - 3 per location)
-- Delhi
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q26_assisted_others,
  q27, q28, q29, q30, total_score) VALUES
(1, 1, 'Pre-Training', 2, '2023-06-15', 'Completed',
  'Sulpa Kumari', '9876543210', 'H.No 45, Sangam Vihar, New Delhi', 23, 'SC', 'Hindu', '12th', 17000, 6,
  2, 1, 2, 3, 1, ARRAY['Teacher','Doctor','Nurse','Tailor','Computer Operator'], 1, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape','Asking for dowry'], 3,
  ARRAY['Aadhaar Card','Voter ID','Ration Card','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect'], 38.00),
(2, 2, 'Pre-Training', 2, '2023-06-15', 'Completed',
  'Pooja', '9876543211', 'Tughlakabad, New Delhi', 22, 'OBC', 'Hindu', '10th', 15000, 5,
  2, 2, 2, 2, 2, ARRAY['Teacher','Doctor','Nurse','Tailor'], 2, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment'], 42.00),
(3, 3, 'Pre-Training', 2, '2023-06-16', 'Completed',
  'Pooja Kumari', '9876543212', 'Ambedkar Nagar, New Delhi', 24, 'SC', 'Hindu', '8th', 12000, 4,
  1, 1, 1, 2, 1, ARRAY['Teacher','Doctor','Nurse'], 1, 1, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse'], 3,
  ARRAY['Aadhaar Card','Ration Card'], false, false,
  1, 1, 2, ARRAY['Integrity','Courage'], 35.00);

-- Kolkata
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q26_assisted_others,
  q27, q28, q29, q30, total_score) VALUES
(4, 19, 'Pre-Training', 3, '2023-07-20', 'Completed',
  'Priya Das', '9876543228', 'New Barrackpore, Kolkata', 24, 'General', 'Hindu', '12th', 14000, 4,
  2, 1, 2, 3, 1, ARRAY['Teacher','Doctor','Nurse','Computer Operator'], 1, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment'], 37.00),
(5, 20, 'Pre-Training', 3, '2023-07-20', 'Completed',
  'Anita Roy', '9876543229', 'Baranagar, Kolkata', 25, 'General', 'Hindu', '10th', 12000, 5,
  2, 2, 2, 3, 2, ARRAY['Teacher','Doctor','Nurse','Tailor'], 2, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape','Asking for dowry'], 3,
  ARRAY['Aadhaar Card','Voter ID','Ration Card','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect'], 40.00),
(6, 21, 'Pre-Training', 3, '2023-07-21', 'Completed',
  'Rima Mondal', '9876543230', 'New Barrackpore, Kolkata', 22, 'OBC', 'Hindu', '12th', 11000, 5,
  1, 1, 1, 2, 1, ARRAY['Teacher','Doctor','Nurse'], 1, 1, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse'], 3,
  ARRAY['Aadhaar Card','Ration Card'], false, false,
  1, 1, 2, ARRAY['Integrity','Courage'], 34.00);

-- Jaipur
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q26_assisted_others,
  q27, q28, q29, q30, total_score) VALUES
(7, 22, 'Pre-Training', 2, '2023-08-05', 'Completed',
  'Kavita Sharma', '9876543231', 'Jhotwara, Jaipur', 23, 'OBC', 'Hindu', '12th', 16000, 5,
  2, 2, 2, 3, 2, ARRAY['Teacher','Doctor','Nurse','Tailor','Computer Operator'], 2, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape','Asking for dowry'], 3,
  ARRAY['Aadhaar Card','Voter ID','Ration Card','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect'], 41.00),
(8, 23, 'Pre-Training', 2, '2023-08-05', 'Completed',
  'Sonu Kanwar', '9876543232', 'Sanganer, Jaipur', 24, 'General', 'Hindu', '10th', 13000, 6,
  1, 1, 2, 2, 1, ARRAY['Teacher','Doctor','Nurse'], 1, 1, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID'], false, false,
  1, 1, 2, ARRAY['Integrity','Courage'], 36.00),
(9, 24, 'Pre-Training', 2, '2023-08-06', 'Completed',
  'Geeta Meena', '9876543233', 'Jhotwara, Jaipur', 22, 'ST', 'Hindu', '8th', 9000, 7,
  2, 1, 2, 3, 1, ARRAY['Teacher','Doctor','Nurse','Tailor'], 1, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID','Ration Card'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment'], 39.00);

-- Chennai
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q26_assisted_others,
  q27, q28, q29, q30, total_score) VALUES
(10, 25, 'Pre-Training', 2, '2023-08-15', 'Completed',
  'Lakshmi S', '9876543234', 'Vyasarpadi, Chennai', 24, 'SC', 'Hindu', '12th', 15000, 4,
  2, 2, 2, 3, 2, ARRAY['Teacher','Doctor','Nurse','Tailor','Computer Operator','Driver'], 2, 2, 2, 2, 1, 2, ARRAY['Early marriage','Physical Abuse','Rape','Asking for dowry','Stalking and harassment'], 2,
  ARRAY['Aadhaar Card','Voter ID','Ration Card','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect'], 43.00),
(11, 26, 'Pre-Training', 2, '2023-08-15', 'Completed',
  'Selvi M', '9876543235', 'Tondiarpet, Chennai', 25, 'OBC', 'Hindu', '10th', 12000, 6,
  1, 1, 1, 2, 1, ARRAY['Teacher','Doctor','Nurse'], 1, 1, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse'], 3,
  ARRAY['Aadhaar Card','Ration Card'], false, false,
  1, 1, 2, ARRAY['Integrity','Courage'], 31.00),
(12, 27, 'Pre-Training', 2, '2023-08-16', 'Completed',
  'Devi Priya R', '9876543236', 'Vyasarpadi, Chennai', 22, 'SC', 'Hindu', '12th', 14000, 5,
  2, 1, 2, 3, 1, ARRAY['Teacher','Doctor','Nurse','Tailor'], 1, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID','Bank Account'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment'], 37.00);

-- Indore
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q26_assisted_others,
  q27, q28, q29, q30, total_score) VALUES
(13, 28, 'Pre-Training', 2, '2023-08-25', 'Completed',
  'Meena Patel', '9876543237', 'Mhow, Indore', 23, 'OBC', 'Hindu', '12th', 11000, 4,
  2, 2, 2, 3, 2, ARRAY['Teacher','Doctor','Nurse','Tailor','Computer Operator','Driver'], 2, 2, 2, 2, 1, 2, ARRAY['Early marriage','Physical Abuse','Rape','Asking for dowry','Stalking and harassment'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account'], false, false,
  1, 3, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect','Creativity'], 44.00),
(14, 29, 'Pre-Training', 2, '2023-08-25', 'Completed',
  'Sunita Malviya', '9876543238', 'Mhow, Indore', 24, 'OBC', 'Hindu', '10th', 10000, 5,
  1, 1, 1, 2, 1, ARRAY['Teacher','Doctor','Nurse'], 1, 1, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse'], 3,
  ARRAY['Aadhaar Card','Ration Card'], false, false,
  1, 1, 2, ARRAY['Integrity','Courage'], 33.00),
(15, 30, 'Pre-Training', 2, '2023-08-26', 'Completed',
  'Rani Yadav', '9876543239', 'Mhow, Indore', 22, 'OBC', 'Hindu', '8th', 8000, 6,
  2, 1, 2, 3, 1, ARRAY['Teacher','Doctor','Nurse','Tailor'], 1, 2, 1, 2, 1, 1, ARRAY['Early marriage','Physical Abuse','Rape'], 3,
  ARRAY['Aadhaar Card','Voter ID','Ration Card'], false, false,
  1, 2, 2, ARRAY['Integrity','Courage','Commitment'], 38.00);

-- Post-Training Assessments (5 completed — 1 per location)
INSERT INTO assessments (id, flp_id, type, assessed_by, assessment_date, status, pre_assessment_id,
  sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community, sec_a_education, sec_a_income, sec_a_family_members,
  q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
  q24, q25_self_made, q25_which_document, q26_assisted_others, q26_scheme_name,
  q27, q28, q29, q30, total_score) VALUES
-- Sulpa Kumari Post
(16, 1, 'Post-Training', 2, '2024-07-20', 'Completed', 1,
  'Sulpa Kumari', '9876543210', 'H.No 45, Sangam Vihar, New Delhi', 24, 'SC', 'Hindu', '12th', 17000, 6,
  5, 5, 4, 5, 4, ARRAY['Teacher','Lawyer','Doctor','Worker','Driver','Carpenter','Mason','Politician','Painter','Nurse','Tailor','Computer Operator'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Mobility restrictions','Physical Abuse','Asking girl to do housework','Dropping out for siblings','Rape','Stalking and harassment','Warning woman to stay within limits','Taunting for no male child','Asking for dowry'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account','Driving License'], true, 'PAN Card, Driving License', true, 'Aadhaar, Ration Card for 3 community members',
  4, 3, 2, ARRAY['Integrity','Courage','Being able to delegate','Commitment','Creativity','Give and get respect','Self Care'], 82.00),
-- Pooja Post
(17, 2, 'Post-Training', 2, '2024-07-22', 'Completed', 2,
  'Pooja', '9876543211', 'Tughlakabad, New Delhi', 23, 'OBC', 'Hindu', '10th', 15000, 5,
  5, 5, 5, 5, 5, ARRAY['Teacher','Lawyer','Doctor','Worker','Driver','Nurse','Tailor','Computer Operator','Mechanic'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Physical Abuse','Rape','Stalking and harassment','Asking for dowry','Giving leftovers to women'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Bank Account','Driving License'], true, 'PAN Card', true, 'Voter ID for 2 community members',
  4, 3, 2, ARRAY['Integrity','Courage','Commitment','Creativity','Give and get respect','Self Care'], 85.00),
-- Priya Das Post
(18, 19, 'Post-Training', 3, '2024-08-25', 'Completed', 4,
  'Priya Das', '9876543228', 'New Barrackpore, Kolkata', 25, 'General', 'Hindu', '12th', 14000, 4,
  5, 5, 4, 5, 5, ARRAY['Teacher','Lawyer','Doctor','Driver','Nurse','Computer Operator','Mechanic'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Mobility restrictions','Physical Abuse','Rape','Stalking and harassment','Asking for dowry'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account'], true, 'PAN Card', true, 'Aadhaar for 2 members',
  4, 3, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect','Creativity'], 80.00),
-- Kavita Sharma Post
(19, 22, 'Post-Training', 2, '2024-09-10', 'Completed', 7,
  'Kavita Sharma', '9876543231', 'Jhotwara, Jaipur', 24, 'OBC', 'Hindu', '12th', 16000, 5,
  5, 5, 5, 5, 4, ARRAY['Teacher','Lawyer','Doctor','Driver','Nurse','Tailor','Computer Operator'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Physical Abuse','Rape','Stalking and harassment','Asking for dowry','Taunting for no male child'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account','Driving License'], true, 'PAN Card, Driving License', true, 'Ration Card for 1 member',
  4, 3, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect','Creativity','Self Care'], 84.00),
-- Lakshmi S Post
(20, 25, 'Post-Training', 2, '2024-09-20', 'Completed', 10,
  'Lakshmi S', '9876543234', 'Vyasarpadi, Chennai', 25, 'SC', 'Hindu', '12th', 15000, 4,
  5, 5, 4, 5, 5, ARRAY['Teacher','Lawyer','Doctor','Driver','Worker','Nurse','Computer Operator'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Mobility restrictions','Physical Abuse','Rape','Stalking and harassment','Asking for dowry','Warning woman to stay within limits'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account','Driving License'], true, 'Driving License', true, 'Aadhaar for 2 members',
  4, 3, 2, ARRAY['Integrity','Courage','Commitment','Give and get respect','Creativity','Self Care'], 83.00),
-- Meena Patel Post
(21, 28, 'Post-Training', 2, '2024-09-30', 'Completed', 13,
  'Meena Patel', '9876543237', 'Mhow, Indore', 24, 'OBC', 'Hindu', '12th', 11000, 4,
  5, 5, 5, 5, 5, ARRAY['Teacher','Lawyer','Doctor','Driver','Worker','Nurse','Tailor','Computer Operator','Mechanic','Politician'], 4, 5, 2, 2, 3, 2, ARRAY['Early marriage','Girls forced to leave education','Mobility restrictions','Physical Abuse','Rape','Stalking and harassment','Asking for dowry','Warning woman to stay within limits','Taunting for no male child','Giving leftovers to women'], 2,
  ARRAY['Aadhaar Card','Voter ID','PAN Card','Ration Card','Bank Account','Driving License','Birth Certificate'], true, 'PAN Card, Driving License', true, 'Aadhaar, Ration Card for 4 members',
  4, 3, 4, ARRAY['Integrity','Courage','Being able to delegate','Commitment','Creativity','Give and get respect','Self Care','Accomplish work on own'], 88.00);
SELECT setval('assessments_id_seq', 21);
