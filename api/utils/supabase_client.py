"""
supabase_client.py — Shared Supabase Connection
==================================================
Instead of every file creating its own Supabase connection (wasteful
and error-prone), we create ONE shared client here and import it
wherever we need database access.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase_client() -> Client:
    """
    Returns a configured Supabase client using the service_role key.

    We use service_role (not anon) here because this is backend code —
    it needs full access to read/write on behalf of any user, bypassing
    Row Level Security. RLS is what protects users from each other when
    THEY query the database directly (e.g. from a frontend using the
    anon key) — our backend is trusted, so it doesn't need that restriction.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Missing Supabase credentials in .env")

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)