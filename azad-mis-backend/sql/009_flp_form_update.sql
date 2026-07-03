-- =============================================
-- 009: FLP Form Update - Match PDF Application Form
-- Adds new columns, tables, and enum values
-- =============================================

-- New columns on flps table
ALTER TABLE flps ADD COLUMN IF NOT EXISTS surname VARCHAR(200);
ALTER TABLE flps ADD COLUMN IF NOT EXISTS permanent_address TEXT;
ALTER TABLE flps ADD COLUMN IF NOT EXISTS living_with VARCHAR(100);
ALTER TABLE flps ADD COLUMN IF NOT EXISTS language_skills JSONB;
ALTER TABLE flps ADD COLUMN IF NOT EXISTS bank_account_type VARCHAR(50);
ALTER TABLE flps ADD COLUMN IF NOT EXISTS contribution_amount NUMERIC(12,2) DEFAULT 2000;

-- New column on family members
ALTER TABLE flp_family_members ADD COLUMN IF NOT EXISTS contribution_to_household VARCHAR(200);

-- Emergency contacts table
CREATE TABLE IF NOT EXISTS flp_emergency_contacts (
    id SERIAL PRIMARY KEY,
    flp_id INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    relation VARCHAR(100),
    address TEXT,
    mobile_number VARCHAR(15),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Contribution payments table
CREATE TABLE IF NOT EXISTS flp_contribution_payments (
    id SERIAL PRIMARY KEY,
    flp_id INT NOT NULL REFERENCES flps(id) ON DELETE CASCADE,
    amount NUMERIC(12,2) NOT NULL,
    payment_date DATE NOT NULL,
    received_by VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enum updates (using DO block to avoid errors if value already exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Through Friend' AND enumtypid = 'how_know_azad_enum'::regtype) THEN
        ALTER TYPE how_know_azad_enum ADD VALUE 'Through Friend';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Through NGO' AND enumtypid = 'how_know_azad_enum'::regtype) THEN
        ALTER TYPE how_know_azad_enum ADD VALUE 'Through NGO';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Saw Driver' AND enumtypid = 'how_know_azad_enum'::regtype) THEN
        ALTER TYPE how_know_azad_enum ADD VALUE 'Saw Driver';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Saw Advertisement' AND enumtypid = 'how_know_azad_enum'::regtype) THEN
        ALTER TYPE how_know_azad_enum ADD VALUE 'Saw Advertisement';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Living Separately' AND enumtypid = 'marital_status_enum'::regtype) THEN
        ALTER TYPE marital_status_enum ADD VALUE 'Living Separately';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Widow' AND enumtypid = 'marital_status_enum'::regtype) THEN
        ALTER TYPE marital_status_enum ADD VALUE 'Widow';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Single' AND enumtypid = 'marital_status_enum'::regtype) THEN
        ALTER TYPE marital_status_enum ADD VALUE 'Single';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Less than Class 8' AND enumtypid = 'education_level_enum'::regtype) THEN
        ALTER TYPE education_level_enum ADD VALUE 'Less than Class 8';
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Other' AND enumtypid = 'education_level_enum'::regtype) THEN
        ALTER TYPE education_level_enum ADD VALUE 'Other';
    END IF;
END$$;
