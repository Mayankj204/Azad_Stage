-- =============================================
-- Azad Foundation MIS - Indexes
-- =============================================

-- Foreign key indexes (PostgreSQL does not auto-create these)
CREATE INDEX idx_districts_state_id ON districts(state_id);
CREATE INDEX idx_cities_district_id ON cities(district_id);
CREATE INDEX idx_centres_state_id ON centres(state_id);
CREATE INDEX idx_batches_centre_id ON batches(centre_id);
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_status ON users(status) WHERE deleted_at IS NULL;

CREATE INDEX idx_flps_centre_id ON flps(centre_id);
CREATE INDEX idx_flps_batch_id ON flps(batch_id);
CREATE INDEX idx_flps_status ON flps(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_flps_name ON flps(name);

CREATE INDEX idx_flp_family_flp_id ON flp_family_members(flp_id);
CREATE INDEX idx_flp_docs_flp_id ON flp_documents(flp_id);
CREATE INDEX idx_flp_log_flp_id ON flp_activity_log(flp_id);
CREATE INDEX idx_flp_log_created ON flp_activity_log(created_at);

CREATE INDEX idx_trainings_centre_id ON trainings(centre_id);
CREATE INDEX idx_trainings_phase ON trainings(phase);
CREATE INDEX idx_trainings_dates ON trainings(start_date, end_date);

CREATE INDEX idx_surveys_flp_id ON surveys(flp_id);
CREATE INDEX idx_surveys_status ON surveys(status);
CREATE INDEX idx_surveys_date ON surveys(date);

CREATE INDEX idx_www_stage ON www_pipeline(stage);
CREATE INDEX idx_www_survey_id ON www_pipeline(survey_id);
CREATE INDEX idx_www_surveyed_by ON www_pipeline(surveyed_by_flp_id);

CREATE INDEX idx_assessments_flp_id ON assessments(flp_id);
CREATE INDEX idx_assessments_type ON assessments(type);
CREATE INDEX idx_assessments_pre_id ON assessments(pre_assessment_id);
CREATE INDEX idx_assessments_status ON assessments(status);
