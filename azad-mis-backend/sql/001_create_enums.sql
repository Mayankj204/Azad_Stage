-- =============================================
-- Azad Foundation MIS - PostgreSQL ENUM Types
-- =============================================

CREATE TYPE flp_status_enum AS ENUM ('Active', 'Walkout');
CREATE TYPE how_know_azad_enum AS ENUM ('Community Meeting', 'Canopy', 'Mike Prachar', 'FLP Visit', 'Other');
CREATE TYPE mobilization_activity_enum AS ENUM ('Survey', 'Home Visit', 'Community Meeting', 'Canopy', 'Mike Prachar');
CREATE TYPE enrollment_through_enum AS ENUM ('Direct Walk-in', 'Referral', 'Community Event');
CREATE TYPE caste_category_enum AS ENUM ('General', 'OBC', 'SC', 'ST', 'Other');
CREATE TYPE community_religion_enum AS ENUM ('Hindu', 'Muslim', 'Christian', 'Sikh', 'Buddhist', 'Jain', 'Other');
CREATE TYPE marital_status_enum AS ENUM ('Unmarried', 'Married', 'Divorced', 'Widowed', 'Separated');
CREATE TYPE education_level_enum AS ENUM ('Uneducated', 'Below 5th', '5th', '8th', '10th', '12th', 'Graduate', 'Post Graduate');
CREATE TYPE family_relation_enum AS ENUM ('Father', 'Mother', 'Spouse', 'Brother', 'Sister', 'Child', 'Other');
CREATE TYPE family_occupation_enum AS ENUM ('Employed', 'Self-employed', 'House wife', 'Student', 'Unemployed', 'Retired');
CREATE TYPE document_type_enum AS ENUM ('Aadhaar Card', 'Bank Passbook', 'Education Certificate', 'Photograph', 'PAN Card', 'Marksheets', 'Other');
CREATE TYPE training_phase_enum AS ENUM ('Phase I', 'Phase II', 'Phase III', 'Phase IV');
CREATE TYPE survey_status_enum AS ENUM ('Submitted', 'Approved', 'Rejected');
CREATE TYPE www_stage_enum AS ENUM ('Potential', 'Shortlisted', 'Contacted', 'Enrolled', 'Rejected');
CREATE TYPE training_preference_enum AS ENUM ('2-Wheeler', '4-Wheeler');
CREATE TYPE assessment_type_enum AS ENUM ('Pre-Training', 'Post-Training');
CREATE TYPE assessment_status_enum AS ENUM ('Completed', 'Draft');
CREATE TYPE attendance_status_enum AS ENUM ('Present', 'Absent');
CREATE TYPE user_status_enum AS ENUM ('Active', 'Inactive');
CREATE TYPE entity_status_enum AS ENUM ('Active', 'Inactive');
