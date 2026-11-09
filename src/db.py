"""One place that knows how to connect to Postgres."""
import psycopg

from .config import get_database_url


def connect() -> psycopg.Connection:
    # prepare_threshold=None turns off server-side prepared statements. Supabase's
    # "transaction pooler" does not support them; this makes the code work on any pooler.
    return psycopg.connect(get_database_url(), prepare_threshold=None)
