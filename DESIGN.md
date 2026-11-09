# Write-up: data model and the GA4 boundary

## 1. What I built
A small pipeline in which one stream of internal product events feeds two destinations:
a private Postgres warehouse (everything, including dollars and names) and a GA4-safe stream
(five categorical fields only). The founders' dashboard reads only aggregate views of the
private side.

```
 fake app events (JSONL)
        |  validate (Pydantic), dedupe on event_id
        v
 internal.events  -----> internal.v_* views -----> founder dashboard (Streamlit)
        |
        |  SELECT 4 columns only: event_name, tenant_id, surface, channel
        v
 ga4_sanitizer (allowlist + HMAC) ---> ga4.outbox ---> GA4 payloads (dry run, nothing is sent)
```

## 2. Data model
Two schemas, one per trust zone.

| Object | Purpose |
|---|---|
| `internal.events` | One row per event. PK `event_id` (idempotent loads). Holds tenant, company/party names, tax ID, amount, `bill_id`, module/surface/channel, UTC timestamp. CHECK constraints restrict event names and categorical values; `bill_id` is required for bill events and forbidden for the rest. |
| `internal.v_bills` | One row per bill, pairing `bill_received` with `bill_paid` through `bill_id`; derives `status` (paid / open / invalid) and `days_to_pay`. |
| `internal.v_weekly_active_companies`, `v_documents_per_module`, `v_weekly_days_to_pay`, `v_bill_summary`, `v_data_quality` | The three dashboard metrics plus quality checks. The dashboard reads only these. |
| `ga4.outbox` | Derived, rebuildable table of what may leave. Columns: `action, module, surface, channel, tenant_hash` (+ a meaningless counter). CHECK constraints allow only the closed value lists and a 32-hex hash. |

**Definitions.** *Active company*: a tenant with at least one event in an ISO week (Mon-Sun, UTC).
*Document processed*: one event, each event being one document handled in a module.
*Time to pay*: `bill_paid.occurred_at - bill_received.occurred_at` for the same `bill_id`; open bills
are excluded from the average and reported separately. *Surface*: web / mobile / api.
*Channel*: how the work entered the product: in_app / email / integration.

## 3. How the boundary is enforced
Never leaves our infrastructure: **dollar amounts, durations, tax IDs, company and party names, raw tenant IDs.**
Allowed to leave: **action, module, surface, channel, hashed tenant ID.**

I treat this as defence in depth, so no single mistake can leak data:

1. **Allowlist, not blocklist.** `sanitize()` builds the safe event from scratch from exactly four input
   fields. A sensitive field added to the raw event next year cannot leak, because nothing reads it.
2. **Data minimisation.** The export query selects only those four columns; amounts and names are never loaded into the exporter.
3. **Closed value lists.** Action, module, surface and channel are Enums, so free text such as a company name cannot be placed in them. The module comes from the tracking plan, not the raw row.
4. **Strict immutable model.** `SafeEvent` uses `extra="forbid"`; an unexpected field raises an error.
5. **Keyed hash.** The tenant ID is hashed with HMAC-SHA256 and a secret key held outside the repo.
   A plain hash of a short ID can be reversed by hashing every possible ID; a keyed hash cannot without the key.
   The hash is stable, so GA4 can still count distinct companies. It is pseudonymous, not anonymous.
6. **Fail closed.** An event name absent from the tracking plan raises `UnmappedEventError` and is not exported.
7. **One door.** The payload builder accepts only a `SafeEvent`; passing a raw dict raises `TypeError`.
8. **The database repeats the rules.** CHECK constraints on `ga4.outbox`; optional least-privilege roles
   (`dashboard_reader` sees only aggregate views, `ga4_exporter` only `ga4.outbox`) and row-level security on `internal.events`.

**Proof.** `tests/test_boundary.py` plants canary values (a fake company, party name, tax ID, amount,
duration, raw tenant ID, and an unplanned `bank_account` field) and asserts none appears anywhere in the
serialized GA4 payload. I also checked the tests detect real failures: replacing the hash with the raw
tenant ID, or allowing extra fields, each makes tests fail. A live-database test confirms no raw tenant
ID or company name appears in `ga4.outbox`. CI runs the full pipeline against a throw-away Postgres on every push.

## 4. Pipeline reliability
Events are validated before loading (bad rows are counted and skipped). Loading is idempotent
(`ON CONFLICT DO NOTHING`), so reruns and the duplicate events I inject on purpose add no rows.
All timestamps are timezone-aware UTC. Out-of-order arrival is handled because metrics are computed
in SQL from timestamps, not from file order. The data-quality view reports invalid or open bills.

## 5. Assumptions and honest limits
- Data is synthetic; volumes are small, so no partitioning, queues or orchestration.
- *Average days to pay by week paid* is biased low in the earliest weeks (slow bills are not paid yet).
  A cohort view by week received would remove that bias; I flagged it on the dashboard rather than hide it.
- `client_id` in the GA4 payload is the tenant hash, so GA4 "users" equal companies, not individual people.
- The GA4 call is a dry run: payloads are built and stored, never sent. GA4 parameter naming and length
  limits should be checked against current documentation before connecting a real property.

## 6. If this were production
Rotate the hash key with a documented policy (rotation breaks continuity in GA4); add a consent check;
move instrumentation into a shared event schema package so engineers cannot ship an unmapped event
(CI fails on it); add dbt or scheduled jobs for transformations; send the same safe stream to PostHog
or Segment through the same sanitizer; alert on data-quality failures; add cohort retention views.
