"""Supabase Postgres connection helper for the rate-shopping feature.

The legacy pricing tables (competitors/runs/recommendations) still live in the local
SQLite file. The rate-shopping feature, which accumulates competitor price history over
time, uses Supabase Postgres instead so the data survives Streamlit Cloud redeploys.

All access is server-side over a direct (pooled) Postgres connection. The connection
string lives in SUPABASE_DB_URL and is never exposed to the browser.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

# Best-effort load of a local .env when running outside Streamlit Cloud.
try:  # pragma: no cover - convenience only
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

RATESHOP_SCHEMA = "rateshop"


class MissingConfigError(RuntimeError):
    """Raised when the Supabase connection is requested but not configured."""


def _connection_string() -> str:
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        raise MissingConfigError(
            "SUPABASE_DB_URL is not set. Add the Supabase 'Transaction pooler' "
            "connection string (port 6543) to your .env / Streamlit secrets. "
            "See .env.example for the exact format."
        )
    return url


def get_conn():
    """Open a new psycopg2 connection with search_path pinned to the rateshop schema."""
    try:
        import psycopg2  # noqa: WPS433 (import here so the rest of the app runs without it)
    except ImportError as exc:  # pragma: no cover
        raise MissingConfigError(
            "psycopg2-binary is not installed. Run: pip install -r requirements.txt"
        ) from exc

    conn = psycopg2.connect(
        _connection_string(),
        connect_timeout=10,
        options=f"-c search_path={RATESHOP_SCHEMA},public",
    )
    return conn


@contextmanager
def cursor(commit: bool = False):
    """Context manager yielding a cursor and guaranteeing the connection is closed."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_configured() -> bool:
    """True if a Supabase connection string is present (used to gate UI gracefully)."""
    return bool(os.getenv("SUPABASE_DB_URL", "").strip())
