"""Run this FIRST. It only checks that Python can reach your Supabase database."""
from urllib.parse import urlparse

from src.config import get_database_url
from src.db import connect

url = get_database_url()
if "[" in url or "YOURPASSWORD" in url or "YOURREF" in url:
    raise SystemExit("Your .env still contains placeholder text. Replace DATABASE_URL with the real "
                     "connection string from Supabase (and remove the square brackets).")

p = urlparse(url)
print(f"Connecting to host={p.hostname} port={p.port} user={p.username} ...")
try:
    with connect() as conn:
        version = conn.execute("select version()").fetchone()[0]
    print("SUCCESS: connected to PostgreSQL ->", version[:60])
except Exception as exc:
    msg = str(exc)
    print("FAILED:", msg.strip()[:300])
    if "translate host" in msg or "unreachable" in msg or "timeout" in msg.lower():
        print("HINT: use the 'Session pooler' connection string from Supabase, not 'Direct connection'.")
    elif "password authentication failed" in msg:
        print("HINT: wrong database password, or the password contains special characters "
              "(@ : / # ?). Reset the password in Supabase using letters and numbers only.")
    elif "Tenant or user not found" in msg:
        print("HINT: the username must look like postgres.<project-ref>. Copy the string again from Supabase.")
    raise SystemExit(1)
