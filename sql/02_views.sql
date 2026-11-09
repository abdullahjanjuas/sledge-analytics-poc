-- 02_views.sql  --  the metrics. Views = saved queries; the dashboard only reads these.

-- METRIC 1: weekly active companies
-- "Active company" = a tenant that produced at least one event in that ISO week (Mon-Sun, UTC).
CREATE OR REPLACE VIEW internal.v_weekly_active_companies AS
SELECT date_trunc('week', occurred_at AT TIME ZONE 'UTC')::date AS week_start,
       COUNT(DISTINCT tenant_id)                                AS active_companies
FROM internal.events
GROUP BY 1
ORDER BY 1;

-- METRIC 2: documents processed per module
-- Every event in this dataset is one document being processed in a module.
CREATE OR REPLACE VIEW internal.v_documents_per_module AS
SELECT module, COUNT(*) AS documents
FROM internal.events
GROUP BY module
ORDER BY documents DESC;

-- Helper: one row per bill, built by pairing bill_received with bill_paid via bill_id.
CREATE OR REPLACE VIEW internal.v_bills AS
WITH b AS (
    SELECT bill_id,
           MIN(tenant_id)                                                       AS tenant_id,
           MIN(occurred_at) FILTER (WHERE event_name = 'bill_received')         AS received_at,
           MIN(occurred_at) FILTER (WHERE event_name = 'bill_paid')             AS paid_at
    FROM internal.events
    WHERE bill_id IS NOT NULL
    GROUP BY bill_id
)
SELECT b.*,
       CASE WHEN received_at IS NULL THEN 'paid_without_received'
            WHEN paid_at     IS NULL THEN 'open'
            WHEN paid_at < received_at THEN 'invalid_order'
            ELSE 'paid' END AS status,
       CASE WHEN received_at IS NOT NULL AND paid_at >= received_at
            THEN ROUND((EXTRACT(EPOCH FROM (paid_at - received_at)) / 86400.0)::numeric, 2)
       END AS days_to_pay
FROM b;

-- METRIC 3a: average days from bill received to bill paid, by the week the bill was paid
CREATE OR REPLACE VIEW internal.v_weekly_days_to_pay AS
SELECT date_trunc('week', paid_at AT TIME ZONE 'UTC')::date AS week_start,
       COUNT(*)                                             AS bills_paid,
       ROUND(AVG(days_to_pay), 1)                           AS avg_days_to_pay
FROM internal.v_bills
WHERE status = 'paid'
GROUP BY 1
ORDER BY 1;

-- METRIC 3b: headline numbers for bills (open bills are NOT counted in the average)
CREATE OR REPLACE VIEW internal.v_bill_summary AS
SELECT ROUND(AVG(days_to_pay) FILTER (WHERE status = 'paid'), 1) AS avg_days_to_pay,
       COUNT(*) FILTER (WHERE status = 'paid')                   AS paid_bills,
       COUNT(*) FILTER (WHERE status = 'open')                   AS open_bills,
       COUNT(*) FILTER (WHERE status IN ('invalid_order','paid_without_received')) AS invalid_bills
FROM internal.v_bills;

-- Simple data-quality report shown at the bottom of the dashboard
CREATE OR REPLACE VIEW internal.v_data_quality AS
SELECT 'events_loaded'                      AS check_name, COUNT(*)::bigint AS value FROM internal.events
UNION ALL
SELECT 'bills_paid_before_received',        COUNT(*) FROM internal.v_bills WHERE status = 'invalid_order'
UNION ALL
SELECT 'bills_paid_without_received',       COUNT(*) FROM internal.v_bills WHERE status = 'paid_without_received'
UNION ALL
SELECT 'bills_still_open',                  COUNT(*) FROM internal.v_bills WHERE status = 'open';
