-- =============================================================
-- 068_www_trainees_full.sql
--
-- Phase 2 of the WWW Add Trainee build-out (2026-06-11).  Migration
-- 066 created www_trainees + 3 child tables covering only the Basic
-- Profile tab.  This migration extends the schema to cover all 10
-- tabs in the Add Trainee form:
--
--   2  Family                         -> www_trainee_family_members
--   3  Previous Employment            -> 4 cols on www_trainees
--   4  Financial Status               -> ~10 cols on www_trainees
--   5  Housing & Asset Info           -> ~9 cols + 2 child tables
--                                       (assets, internet uses)
--   6  Disability Info                -> 4 cols on www_trainees
--   7  Organization Association       -> 6 cols on www_trainees
--   8  GBV                            -> 5 cols + 3 child tables
--                                       (situations, support kinds,
--                                        encouraged_by)
--   9  Reference                      -> 2 child tables (references,
--                                                        documents)
--   10 Commitment                     -> 6 cols on www_trainees
--
-- All column adds use IF NOT EXISTS so the migration is idempotent
-- and safe to re-apply.  Child tables use CREATE TABLE IF NOT EXISTS.
-- Every FK to www_trainees has ON DELETE CASCADE so soft-deleting a
-- trainee (deleted_at) + the existing wipe-and-replace child pattern
-- both behave correctly.
-- =============================================================

SET search_path TO mis_azad, public;

BEGIN;

-- ==================================================================
-- Tab 3  Previous Employment
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS worked_before        VARCHAR(8);    -- Yes / No
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS prev_work_type       VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS prev_work_other      TEXT;
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS prev_monthly_income  TEXT;

-- ==================================================================
-- Tab 4  Financial Status
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS has_bank             VARCHAR(8);   -- Yes / No
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS bank_account_type    VARCHAR(32);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS bank_name            VARCHAR(120);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS bank_acct            VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS has_savings          VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS savings_where        VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS has_debt             VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS debt_amount          VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS loan_source          VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS loan_repay           TEXT;

-- ==================================================================
-- Tab 5  Housing & Asset Info
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS house_ownership      VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS house_own_detail     VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS property_name_holder VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS property_paper_keeper VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS house_type           VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS has_mobile           VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS is_smart_phone       VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS phone_user           VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS phone_usage          VARCHAR(64);

-- ==================================================================
-- Tab 6  Disability Info
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS disability_in_house  VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS disability_relation  VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS disability_type      VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS has_disability_cert  VARCHAR(8);

-- ==================================================================
-- Tab 7  Organization Association
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_in_azad     VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_name        VARCHAR(120);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_relation    VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_org         VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_designation VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS relative_years       NUMERIC(5,1);

-- ==================================================================
-- Tab 8  GBV (single-value cols; multi-checkboxes are child tables)
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS violence_place       VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS violence_by          VARCHAR(120);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS violence_when        VARCHAR(64);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS want_support         VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS support_other        VARCHAR(255);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS housework_hours      VARCHAR(64);

-- ==================================================================
-- Tab 10  Commitment
-- ==================================================================
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_aware         VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_ready         VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_amount        VARCHAR(8);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_paid_status   VARCHAR(32);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_paid_amount   VARCHAR(32);
ALTER TABLE www_trainees ADD COLUMN IF NOT EXISTS commit_partial_amt   VARCHAR(64);

-- ==================================================================
-- Tab 2  www_trainee_family_members  (one row per family member)
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_family_members (
    id                  SERIAL PRIMARY KEY,
    trainee_id          INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    seq                 INTEGER NOT NULL,
    member_name         VARCHAR(120),
    relation            VARCHAR(64),
    mobile_no           VARCHAR(20),
    age                 INTEGER,
    education           VARCHAR(120),
    occupation          VARCHAR(120),
    monthly_income      NUMERIC(12,2),
    monthly_contribution NUMERIC(12,2)
);
CREATE INDEX IF NOT EXISTS idx_www_family_trainee ON www_trainee_family_members(trainee_id);

-- ==================================================================
-- Tab 5  www_trainee_assets  (multi-check Asset checkboxes)
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_assets (
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    asset       VARCHAR(64) NOT NULL,
    PRIMARY KEY (trainee_id, asset)
);

-- ==================================================================
-- Tab 5  www_trainee_net_uses  (multi-check "what is internet used for")
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_net_uses (
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    net_use     VARCHAR(64) NOT NULL,
    PRIMARY KEY (trainee_id, net_use)
);

-- ==================================================================
-- Tab 8  www_trainee_gbv_situations  (multi-check situations, with
--        auto-derived violence-type category)
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_gbv_situations (
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    situation   VARCHAR(255) NOT NULL,
    violence_category VARCHAR(32),
    PRIMARY KEY (trainee_id, situation)
);

-- ==================================================================
-- Tab 8  www_trainee_gbv_support_kinds  (multi-check "kind of support
--        Azad provided")
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_gbv_support_kinds (
    trainee_id   INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    support_kind VARCHAR(120) NOT NULL,
    PRIMARY KEY (trainee_id, support_kind)
);

-- ==================================================================
-- Tab 8  www_trainee_encouraged_by  (multi-check "who encouraged you")
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_encouraged_by (
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    encourager  VARCHAR(64) NOT NULL,
    PRIMARY KEY (trainee_id, encourager)
);

-- ==================================================================
-- Tab 9  www_trainee_references  (repeating reference rows)
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_references (
    id          SERIAL PRIMARY KEY,
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    ref_name    VARCHAR(120),
    relation    VARCHAR(64),
    contact_no  VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_www_refs_trainee ON www_trainee_references(trainee_id);

-- ==================================================================
-- Tab 9  www_trainee_documents  (uploaded document metadata; binary
--        file storage will be added in Phase 3 if needed)
-- ==================================================================
CREATE TABLE IF NOT EXISTS www_trainee_documents (
    id          SERIAL PRIMARY KEY,
    trainee_id  INTEGER NOT NULL REFERENCES www_trainees(id) ON DELETE CASCADE,
    file_name   VARCHAR(255),
    doc_type    VARCHAR(64),
    file_path   TEXT,
    uploaded_by VARCHAR(120),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_www_docs_trainee ON www_trainee_documents(trainee_id);

COMMIT;

-- Sanity probe (informational; row counts to confirm structure)
SELECT
    (SELECT COUNT(*) FROM information_schema.columns
       WHERE table_schema = 'mis_azad' AND table_name = 'www_trainees') AS www_trainees_col_count,
    (SELECT COUNT(*) FROM information_schema.tables
       WHERE table_schema = 'mis_azad' AND table_name LIKE 'www_trainee_%') AS www_trainee_child_tables;
