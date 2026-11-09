# Construction Ops Analytics: proof of concept

A small, tested analytics pipeline for a construction-software product:

1. **Generates** fake product events (invoices, bills, lien waivers, contracts, change orders)
2. **Loads** them into **PostgreSQL** (Supabase) with validation and idempotent inserts
3. **Shows** one founder dashboard: weekly active companies, documents per module, average time from bill received to bill paid
4. **Produces a GA4-safe copy** of every event: only `action`, `module`, `surface`, `channel` and a hashed tenant ID. No dollars, durations, names or tax IDs, with tests that try to break that rule

- Write-up (data model and how the boundary is enforced): **[DESIGN.md](DESIGN.md)**
- Event dictionary: [docs/TRACKING_PLAN.md](docs/TRACKING_PLAN.md)
- Live dashboard: `https://sledge-analytics-poc-8segedxkmkzfu93nxctby3.streamlit.app/`

## What an event looks like

Internal (stays in our database):
```json
{"event_name": "invoice_created", "tenant_id": "ten_1a2b3c4d5e", "company_name": "Apex Plumbing LLC",
 "counterparty_name": "Smith Supply", "counterparty_tax_id": "12-3456789", "amount": 18500.0,
 "module": "invoices", "surface": "web", "channel": "in_app", "...": "..."}
```
GA4-safe (the only thing allowed to leave): see [samples/ga4_events_sample.jsonl](samples/ga4_events_sample.jsonl)
```json
{"client_id": "4f3da39e...", "events": [{"name": "app_action", "params": {
  "action": "create", "module": "invoices", "surface": "web", "channel": "in_app", "tenant_hash": "4f3da39e..."}}]}
```

## Run it in PyCharm (no terminal needed)
1. Open the folder in PyCharm; when asked, create a **.venv** and install `requirements-dev.txt`.
2. Copy `.env.example` to `.env` and fill in `DATABASE_URL` and `GA4_HASH_KEY`.
3. Right-click and **Run**: `check_connection.py` (test the database), then `run_pipeline.py` (build everything),
   then `run_dashboard.py` (open http://localhost:8501). Right-click the `tests` folder -> **Run pytest** for the tests.

## Run it from a terminal (Linux, about 10 minutes)

**1. Get the code and install**
```bash
git clone <your-repo-url> && cd sledge-analytics-poc
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

**2. Create a free Postgres on Supabase** and copy the **Session pooler** connection string
(Supabase dashboard -> *Connect* button -> connection string). The pooler string is recommended
because the "direct" connection is often IPv6-only. Then:
```bash
cp .env.example .env        # open .env and paste DATABASE_URL, set GA4_HASH_KEY
# generate a key:  python -c "import secrets; print(secrets.token_hex(32))"
```

**3. Run the pipeline**
```bash
make pipeline     # create tables+views -> generate events -> load -> export GA4-safe events
make test         # 17 tests: boundary attacks, generator, and live database checks
make dashboard    # opens http://localhost:8501
```
No `make`? The commands are in the [Makefile](Makefile); each is one `python -m src.<name>` line.

**4. (Optional) least-privilege roles + row-level security**
```bash
make harden       # then set passwords for the two new roles in the Supabase SQL editor
```
`dashboard_reader` can read only the aggregate views (no raw events). `ga4_exporter` can read only `ga4.outbox`.

## Deploy the dashboard (free)
1. Push this repo to GitHub (public or private).
2. share.streamlit.io -> *New app* -> pick the repo, main file `dashboard.py`.
3. *Advanced settings -> Secrets*, add: `DATABASE_URL = "postgresql://..."`
   (use the `dashboard_reader` connection string if you ran `make harden`).
4. Free Supabase projects pause after a week of inactivity. Open the project before sharing the link.

## Project map
```
sql/01_schema.sql     tables (internal.events, ga4.outbox) with CHECK constraints
sql/02_views.sql      the three metrics as views + data-quality checks
sql/03_roles.sql      optional least-privilege roles and row-level security
src/taxonomy.py       the closed lists of allowed values + tracking plan (event -> action/module)
src/generate_events.py  fake data with a story (growth, slow vs fast payers, open bills, duplicates)
src/load_events.py    validate (Pydantic) + idempotent load
src/ga4_sanitizer.py  THE BOUNDARY: allowlist + closed enums + strict model + HMAC hash
src/export_ga4.py     builds ga4.outbox and a sample payload file
src/queries.py        dashboard data access (aggregate views only)
dashboard.py          Streamlit founder dashboard
tests/                boundary "canary" tests, generator tests, live-database tests
.github/workflows/    CI: spins up Postgres, runs the whole pipeline, runs all tests
```
