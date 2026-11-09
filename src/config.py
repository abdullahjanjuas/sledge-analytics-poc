"""Reads secrets from the environment (.env file locally, platform secrets when deployed).

Secrets never live in code. If a required secret is missing we fail loudly instead of
silently using a weak default.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if there is one (it is git-ignored)


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return url


def get_hash_key() -> bytes:
    """Secret key for hashing tenant IDs. Must be long enough to be a real secret."""
    key = os.environ.get("GA4_HASH_KEY", "")
    if len(key) < 16:
        raise RuntimeError(
            "GA4_HASH_KEY is missing or too short (need 16+ characters). "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return key.encode("utf-8")
