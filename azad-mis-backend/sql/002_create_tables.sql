-- =============================================
-- Azad Foundation MIS - Table Definitions
-- =============================================

-- 1. States
CREATE TABLE states (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Districts
CREATE TABLE districts (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    state_id    INT NOT NULL REFERENCES states(id) ON DELETE RESTRICT,
    status      entity_status_enum NOT NULL DEFAULT 'Active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name, state_id)
);

-- 3. Cities
CREATE TABLE cities (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    district_id   INT NOT NULL REFERENCES districts(id) ON DELETE RESTRICT,
    bastis_count  INT NOT NULL DEFAULT 0,
    status        entity_status_enum NOT NULL DEFAULT 'Active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name, district_id)
);

-- 4. Centres
CREATE TABLE centres (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    state_id    INT NOT NULL REFERENCES states(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Batches
CREATE TABLE batches (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    year        VARCHAR(10) NOT NULL,
    centre_id   INT NOT NULL REFERENCES centres(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name, year, centre_id)
);

-- 6. Roles
CREATE TABLE roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Users
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id       INT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    geo_scope     VARCHAR(100),
    status        user_status_enum NOT NULL DEFAULT 'Active',
    last_login    TIMESTAMPTZ,
    deleted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. FLPs (Field Level Professionals)
CREATE TABLE flps (
    id                      SERIAL PRIMARY KEY,
    enrollment_number       VARCHAR(30) NOT NULL UNIQUE,
    photo_url               VARCHAR(500),
    centre_id               INT NOT NULL REFERENCES centres(id) ON DELETE RESTRICT,
    batch_id                INT REFERENCES batches(id) ON DELETE SET NULL,
    name                    VARCHAR(200) NOT NULL,
    status                  flp_status_enum NOT NULL DEFAULT 'Active',
    walkout_reason          TEXT,
    date_of_birth           DATE NOT NULL,
    age_at_enrollment       INT,
    address                 TEXT NOT NULL,
    email                   VARCHAR(255),
    mobile                  VARCHAR(15) NOT NULL,
    how_know_azad           how_know_azad_enum,
    mobilization_activity   mobilization_activity_enum,
    enrollment_through      enrollment_through_enum,
    caste_category          caste_category_enum NOT NULL,
    community_religion      community_religion_enum NOT NULL,
    marital_status          marital_status_enum NOT NULL,
    age_at_marriage         INT,
    number_of_children      INT NOT NULL DEFAULT 0,
    education               education_level_enum NOT NULL,
    still_studying          BOOLEAN NOT NULL DEFAULT FALSE,
    studying_what           VARCHAR(200),
    monthly_family_income   NUMERIC(12,2),
    family_members_count    INT,
    per_capita_income       NUMERIC(12,2),
    -- Bank Details (1:1)
    bank_name               VARCHAR(200),
    account_holder_name     VARCHAR(200),
    account_number          VARCHAR(30),
    bank_branch             VARCHAR(200),
    ifsc_code               VARCHAR(11),
    -- Previous Employment
    worked_before           BOOLEAN NOT NULL DEFAULT FALSE,
    prev_org_name           VARCHAR(300),
    prev_last_salary        NUMERIC(12,2),
    prev_work_nature        TEXT,
    prev_leave_date         DATE,
    prev_leave_reason       TEXT,
    flp_relation            VARCHAR(200),
    why_join_flp            TEXT[],
    challenges              VARCHAR(200),
    future_goal             VARCHAR(200),
    -- Credentials
    username                VARCHAR(100) UNIQUE,
    password_hash_flp       VARCHAR(255),
    --
    deleted_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. FLP Family Members
CREATE TABLE flp_family_members (
    id              SERIAL PRIMARY KEY,
    flp_id          INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    relation        family_relation_enum NOT NULL,
    age             INT,
    education       VARCHAR(50),
    occupation      VARCHAR(100),
    monthly_income  NUMERIC(12,2) DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. FLP Documents
CREATE TABLE flp_documents (
    id              SERIAL PRIMARY KEY,
    flp_id          INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    file_name       VARCHAR(300) NOT NULL,
    file_path       VARCHAR(500),
    document_type   document_type_enum NOT NULL,
    upload_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    uploaded_by     VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. FLP Activity Log
CREATE TABLE flp_activity_log (
    id              SERIAL PRIMARY KEY,
    flp_id          INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    action          VARCHAR(200) NOT NULL,
    ip_address      VARCHAR(45),
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Training Topics (Lookup)
CREATE TABLE training_topics (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Trainings
CREATE TABLE trainings (
    id              SERIAL PRIMARY KEY,
    centre_id       INT NOT NULL REFERENCES centres(id) ON DELETE RESTRICT,
    phase           training_phase_enum NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    title           VARCHAR(300),
    trainer_names   TEXT,
    venue           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Training-Topics Junction
CREATE TABLE training_topic_map (
    training_id INT NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
    topic_id    INT NOT NULL REFERENCES training_topics(id) ON DELETE CASCADE,
    PRIMARY KEY (training_id, topic_id)
);

-- 15. Training Participants Junction
CREATE TABLE training_participants (
    training_id INT NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
    flp_id      INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    attendance  attendance_status_enum NOT NULL DEFAULT 'Present',
    PRIMARY KEY (training_id, flp_id)
);

-- 16. Surveys
CREATE TABLE surveys (
    id                  SERIAL PRIMARY KEY,
    survey_id_code      VARCHAR(20) NOT NULL UNIQUE,
    flp_id              INT NOT NULL REFERENCES flps(id) ON DELETE RESTRICT,
    date                DATE NOT NULL,
    status              survey_status_enum NOT NULL DEFAULT 'Submitted',
    -- Section A: Metadata
    sec_a_state         VARCHAR(100),
    sec_a_surveyor      VARCHAR(200),
    sec_a_designation   VARCHAR(100),
    sec_a_quarter       VARCHAR(30),
    -- Section B: Location
    sec_b_basti         VARCHAR(200),
    sec_b_district      VARCHAR(200),
    sec_b_centre        VARCHAR(200),
    sec_b_area          VARCHAR(200),
    sec_b_address       TEXT,
    -- Section C: Respondent
    sec_c_respondent_name   VARCHAR(200),
    sec_c_contact           VARCHAR(20),
    sec_c_caste             VARCHAR(50),
    sec_c_community         VARCHAR(50),
    -- Section D: Household
    sec_d_total_family_members  INT,
    sec_d_monthly_income        NUMERIC(12,2),
    sec_d_per_capita            NUMERIC(12,2),
    sec_d_decision_maker        VARCHAR(100),
    -- Section G: Woman 18+ Details
    sec_g_woman_name        VARCHAR(200),
    sec_g_woman_age         INT,
    sec_g_woman_education   VARCHAR(100),
    sec_g_interested_www    BOOLEAN,
    sec_g_training_preference   training_preference_enum,
    sec_g_eligible          BOOLEAN,
    -- Auto-Captured
    gps_lat             NUMERIC(10,7),
    gps_lng             NUMERIC(10,7),
    gps_accuracy        NUMERIC(6,2),
    start_time          TIMESTAMPTZ,
    duration_minutes    INT,
    sync_time           TIMESTAMPTZ,
    --
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 17. WWW Pipeline
CREATE TABLE www_pipeline (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(200) NOT NULL,
    age                     INT,
    district                VARCHAR(200),
    survey_id               INT REFERENCES surveys(id) ON DELETE SET NULL,
    surveyed_by_flp_id      INT REFERENCES flps(id) ON DELETE SET NULL,
    training_preference     training_preference_enum,
    stage                   www_stage_enum NOT NULL DEFAULT 'Potential',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 18. Assessments
CREATE TABLE assessments (
    id                  SERIAL PRIMARY KEY,
    flp_id              INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    type                assessment_type_enum NOT NULL,
    assessed_by         INT REFERENCES users(id) ON DELETE SET NULL,
    assessment_date     DATE NOT NULL,
    status              assessment_status_enum NOT NULL DEFAULT 'Draft',
    pre_assessment_id   INT REFERENCES assessments(id) ON DELETE SET NULL,
    -- Section A: Demographics snapshot
    sec_a_name          VARCHAR(200),
    sec_a_mobile        VARCHAR(15),
    sec_a_address       TEXT,
    sec_a_age           INT,
    sec_a_caste         VARCHAR(50),
    sec_a_community     VARCHAR(50),
    sec_a_education     VARCHAR(50),
    sec_a_income        NUMERIC(12,2),
    sec_a_family_members INT,
    -- Section B: Q10-Q23
    q10     SMALLINT CHECK (q10 BETWEEN 1 AND 5),
    q11     SMALLINT CHECK (q11 BETWEEN 1 AND 5),
    q12     SMALLINT CHECK (q12 BETWEEN 1 AND 5),
    q13     SMALLINT CHECK (q13 BETWEEN 1 AND 5),
    q14     SMALLINT CHECK (q14 BETWEEN 1 AND 5),
    q15     TEXT[],
    q16     SMALLINT CHECK (q16 BETWEEN 1 AND 5),
    q17     SMALLINT CHECK (q17 BETWEEN 1 AND 5),
    q18     SMALLINT CHECK (q18 BETWEEN 1 AND 4),
    q19     SMALLINT CHECK (q19 BETWEEN 1 AND 4),
    q20     SMALLINT CHECK (q20 BETWEEN 1 AND 3),
    q21     SMALLINT CHECK (q21 BETWEEN 1 AND 4),
    q22     TEXT[],
    q23     SMALLINT CHECK (q23 BETWEEN 1 AND 3),
    -- Section C: Q24-Q26
    q24                 TEXT[],
    q25_self_made       BOOLEAN,
    q25_which_document  VARCHAR(200),
    q26_assisted_others BOOLEAN,
    q26_scheme_name     VARCHAR(300),
    -- Section D: Q27-Q30
    q27     SMALLINT CHECK (q27 BETWEEN 1 AND 4),
    q28     SMALLINT CHECK (q28 BETWEEN 1 AND 4),
    q29     SMALLINT CHECK (q29 BETWEEN 1 AND 4),
    q30     TEXT[],
    -- Computed
    total_score         NUMERIC(5,2),
    --
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
