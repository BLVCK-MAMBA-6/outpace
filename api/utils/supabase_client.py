"""
Shared Supabase clients.

The service-role client is for trusted backend database operations.
The Auth client uses the public anon/publishable key for user-facing
authentication and JWT validation.
"""

import os

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLIC_KEY = (
    os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("SUPABASE_KEY")
)
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)



def get_supabase_client() -> Client:
    """Return the trusted service-role database client."""
    if (
        not SUPABASE_URL
        or not SUPABASE_SERVICE_ROLE_KEY
    ):
        raise ValueError(
            "Missing Supabase service credentials in .env"
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
    )


def get_supabase_auth_client() -> Client:
    """Return a public-key client for Auth operations."""
    if (
        not SUPABASE_URL
        or not SUPABASE_PUBLIC_KEY
    ):
        raise ValueError(
            "Missing Supabase public Auth credentials in .env"
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_PUBLIC_KEY,
    )
