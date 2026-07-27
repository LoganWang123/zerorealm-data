"""Database client — Supabase connection management.

Usage::

    from storage.db import get_client, is_db_available

    if is_db_available():
        client = get_client()
        client.table("signals").insert({...}).execute()

Environment variables:
    SUPABASE_URL   - e.g. https://xxxx.supabase.co
    SUPABASE_KEY   - service_role or anon key
"""

import os
from functools import lru_cache

from utils.logger import get_logger


def is_db_available() -> bool:
    """Check whether Supabase credentials are configured."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))


@lru_cache(maxsize=1)
def get_client():
    """Return a cached Supabase client instance.

    Raises RuntimeError when credentials are missing.
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY in .env"
        )

    from supabase import create_client

    logger = get_logger()
    logger.info("[db] Connecting to Supabase: %s", url[:30] + "...")

    client = create_client(url, key)
    return client
