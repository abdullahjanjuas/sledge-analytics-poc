"""Runs against a real Postgres. Skipped automatically if DATABASE_URL is not set.
Run the pipeline first:  make pipeline
"""
import os

import pytest

from src import config  # noqa: F401  (importing loads the .env file)
from src.db import connect

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="no DATABASE_URL set")


def scalar(sql: str):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def test_outbox_has_only_allowed_columns():
    cols = scalar("""SELECT array_agg(column_name::text ORDER BY column_name)
                     FROM information_schema.columns WHERE table_schema='ga4' AND table_name='outbox'""")
    assert cols == ["action", "channel", "id", "module", "surface", "tenant_hash"]


def test_outbox_matches_events_one_to_one():
    assert scalar("SELECT count(*) FROM ga4.outbox") == scalar("SELECT count(*) FROM internal.events")


def test_no_raw_tenant_id_or_name_appears_in_outbox():
    assert scalar("SELECT count(*) FROM ga4.outbox o JOIN internal.events e ON o.tenant_hash = e.tenant_id") == 0
    assert scalar("""SELECT count(*) FROM ga4.outbox o
                     JOIN (SELECT DISTINCT company_name FROM internal.events) c
                       ON (o.action||o.module||o.surface||o.channel||o.tenant_hash) ILIKE '%'||c.company_name||'%'""") == 0


def test_no_negative_bill_durations():
    assert scalar("SELECT count(*) FROM internal.v_bills WHERE days_to_pay < 0") == 0
