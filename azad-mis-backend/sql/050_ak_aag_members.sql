-- 050_ak_aag_members.sql — AAG (Azad Alumni Group) membership + payment tracking
--
-- AAG is a paid membership programme for graduated AK alumni. The membership
-- fee is ₹100 per alumni; it can be deposited Full (one shot) or Partial
-- (in instalments). The two tables here track:
--   * ak_aag_members      — one row per registered alumni
--   * ak_aag_payments     — one row per deposit (initial / partial / final)
--
-- Computed values are calculated server-side at read time:
--   amount_paid = SUM(ak_aag_payments.amount) for the member
--   remaining   = membership_fee_required − amount_paid
--   payment_status = 'Fully Paid' when amount_paid ≥ required, else 'Partial'
--
-- Safe to re-run: uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS mis_azad.ak_aag_members (
    id                       SERIAL PRIMARY KEY,
    alumni_id                INTEGER NOT NULL REFERENCES mis_azad.ak_alumni(id),
    membership_fee_required  NUMERIC(10,2) NOT NULL DEFAULT 100.00,
    deposit_type             VARCHAR(20),  -- 'Full' | 'Partial'
    membership_fee_deposited VARCHAR(10),  -- 'Yes' | 'No'  (initial registration answer)
    status                   VARCHAR(20) NOT NULL DEFAULT 'Active',
    registered_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at               TIMESTAMPTZ,
    CONSTRAINT ak_aag_members_alumni_id_unique UNIQUE (alumni_id)
);

CREATE INDEX IF NOT EXISTS idx_ak_aag_members_alumni
    ON mis_azad.ak_aag_members (alumni_id);
CREATE INDEX IF NOT EXISTS idx_ak_aag_members_status
    ON mis_azad.ak_aag_members (status) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS mis_azad.ak_aag_payments (
    id              SERIAL PRIMARY KEY,
    aag_member_id   INTEGER NOT NULL REFERENCES mis_azad.ak_aag_members(id) ON DELETE CASCADE,
    amount          NUMERIC(10,2) NOT NULL CHECK (amount >= 0),
    date_of_deposit DATE NOT NULL,
    payment_type    VARCHAR(20) NOT NULL DEFAULT 'Partial',  -- 'Initial' | 'Partial' | 'Final'
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ak_aag_payments_member
    ON mis_azad.ak_aag_payments (aag_member_id);
