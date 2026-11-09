PY ?= python

.PHONY: setup schema generate load export pipeline harden test dashboard

setup:      ## install dependencies
	$(PY) -m pip install -r requirements-dev.txt

schema:     ## create schemas, tables and views in Postgres
	$(PY) -m src.apply_sql sql/01_schema.sql sql/02_views.sql

generate:   ## make fake events -> data/events.jsonl
	$(PY) -m src.generate_events

load:       ## validate + load events into internal.events
	$(PY) -m src.load_events

export:     ## build the GA4-safe events (ga4.outbox + sample file)
	$(PY) -m src.export_ga4

pipeline: schema generate load export   ## run everything in order

harden:     ## optional: least-privilege DB roles + row-level security
	$(PY) -m src.apply_sql sql/03_roles.sql

test:
	$(PY) -m pytest -q

dashboard:
	streamlit run dashboard.py
