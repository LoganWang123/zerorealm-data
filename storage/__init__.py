"""Storage layer — database access.

M2: Supabase (PostgreSQL) for signals / knowledge_items.
Falls back to file storage when SUPABASE_URL is not configured.
"""

from storage.db import get_client, is_db_available
from storage.signals import SignalRepository

__all__ = ["get_client", "is_db_available", "SignalRepository"]
