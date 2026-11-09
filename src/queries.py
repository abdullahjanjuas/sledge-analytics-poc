"""The dashboard's data access. It reads ONLY the aggregate views, never the raw events table."""
import pandas as pd

from .db import connect


def fetch_df(sql: str) -> pd.DataFrame:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def weekly_active_companies() -> pd.DataFrame:
    return fetch_df("SELECT week_start, active_companies FROM internal.v_weekly_active_companies ORDER BY 1")


def documents_per_module() -> pd.DataFrame:
    return fetch_df("SELECT module, documents FROM internal.v_documents_per_module ORDER BY documents DESC")


def weekly_days_to_pay() -> pd.DataFrame:
    return fetch_df("SELECT week_start, bills_paid, avg_days_to_pay FROM internal.v_weekly_days_to_pay ORDER BY 1")


def bill_summary() -> pd.DataFrame:
    return fetch_df("SELECT avg_days_to_pay, paid_bills, open_bills, invalid_bills FROM internal.v_bill_summary")


def data_quality() -> pd.DataFrame:
    return fetch_df("SELECT check_name, value FROM internal.v_data_quality")
