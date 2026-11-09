-- 01_schema.sql  --  tables. Safe to run many times (IF NOT EXISTS).
--
-- Two schemas = two trust zones:
--   internal : the real data (amounts, names, tax IDs). Never leaves our infrastructure.
--   ga4      : only what is allowed to be sent to Google Analytics.

CREATE SCHEMA IF NOT EXISTS internal;
CREATE SCHEMA IF NOT EXISTS ga4;

-- One row per product event. event_id is the PRIMARY KEY, so loading the same
-- event twice can never create a duplicate (idempotent loads).
CREATE TABLE IF NOT EXISTS internal.events (
    event_id            uuid PRIMARY KEY,
    event_name          text        NOT NULL CHECK (event_name IN (
                            'invoice_created','contract_signed','lien_waiver_uploaded',
                            'bill_received','bill_paid','change_order_approved')),
    occurred_at         timestamptz NOT NULL,           -- always stored in UTC
    tenant_id           text        NOT NULL,           -- the customer account (contractor)
    company_name        text        NOT NULL,           -- SENSITIVE: never leaves
    counterparty_name   text,                           -- SENSITIVE: party name, never leaves
    counterparty_tax_id text,                           -- SENSITIVE: never leaves
    amount              numeric(14,2) NOT NULL CHECK (amount >= 0),  -- SENSITIVE: dollars
    bill_id             text,                           -- links bill_received to bill_paid
    module              text        NOT NULL CHECK (module IN (
                            'invoices','contracts','lien_waivers','bills','change_orders')),
    surface             text        NOT NULL CHECK (surface IN ('web','mobile','api')),
    channel             text        NOT NULL CHECK (channel IN ('in_app','email','integration')),
    loaded_at           timestamptz NOT NULL DEFAULT now(),
    -- bill events must carry a bill_id, other events must not
    CHECK ((event_name IN ('bill_received','bill_paid')) = (bill_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON internal.events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_tenant_time ON internal.events (tenant_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_bill        ON internal.events (bill_id) WHERE bill_id IS NOT NULL;

-- The GA4 outbox: the ONLY thing allowed to be sent outside.
-- Note what is missing: no amount, no names, no tax ID, no duration, no raw tenant id,
-- not even a timestamp. CHECK constraints make the database itself reject anything else.
CREATE TABLE IF NOT EXISTS ga4.outbox (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,   -- meaningless counter
    action      text NOT NULL CHECK (action  IN ('create','sign','upload','receive','pay','approve')),
    module      text NOT NULL CHECK (module  IN ('invoices','contracts','lien_waivers','bills','change_orders')),
    surface     text NOT NULL CHECK (surface IN ('web','mobile','api')),
    channel     text NOT NULL CHECK (channel IN ('in_app','email','integration')),
    tenant_hash text NOT NULL CHECK (tenant_hash ~ '^[0-9a-f]{32}$')
);
