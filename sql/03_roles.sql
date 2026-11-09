-- 03_roles.sql  -- hardening (run with: make harden)
-- Principle of least privilege: each actor gets the minimum access it needs.
--   dashboard_reader : can read ONLY the aggregate views (no raw events, no amounts, no names)
--   ga4_exporter     : can read ONLY ga4.outbox
-- After running this, set passwords yourself in the SQL editor (never commit them):
--   ALTER ROLE dashboard_reader PASSWORD '...';
--   ALTER ROLE ga4_exporter     PASSWORD '...';

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dashboard_reader') THEN
    CREATE ROLE dashboard_reader LOGIN;   -- no password yet = cannot log in yet
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ga4_exporter') THEN
    CREATE ROLE ga4_exporter LOGIN;
  END IF;
END $$;

-- Start from "nobody can do anything" ...
REVOKE ALL ON SCHEMA internal FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA internal FROM PUBLIC;
REVOKE ALL ON SCHEMA ga4 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA ga4 FROM PUBLIC;

-- Supabase's built-in API roles (only exist on Supabase) get nothing either.
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON SCHEMA internal FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA internal FROM %I', r);
      EXECUTE format('REVOKE ALL ON SCHEMA ga4 FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA ga4 FROM %I', r);
    END IF;
  END LOOP;
END $$;

-- ... then grant back only what is needed.
GRANT USAGE ON SCHEMA internal TO dashboard_reader;
GRANT SELECT ON internal.v_weekly_active_companies,
                internal.v_documents_per_module,
                internal.v_weekly_days_to_pay,
                internal.v_bill_summary,
                internal.v_data_quality
      TO dashboard_reader;

GRANT USAGE ON SCHEMA ga4 TO ga4_exporter;
GRANT SELECT ON ga4.outbox TO ga4_exporter;

-- Row-level security (RLS): a second lock. With RLS on and no policy,
-- any role that is not the table owner sees zero rows.
ALTER TABLE internal.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ga4.outbox      ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS exporter_read ON ga4.outbox;
CREATE POLICY exporter_read ON ga4.outbox FOR SELECT TO ga4_exporter USING (true);
