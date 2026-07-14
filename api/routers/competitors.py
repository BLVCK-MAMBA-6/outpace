"""
competitors.py — Competitor Management Endpoints
====================================================
This router handles everything related to competitors:
adding a new one, listing a user's competitors, etc.

Right now this is intentionally minimal — just enough to prove
the full pipeline works (API -> Database -> back to API).
We'll expand this as we build out more features.
"""

from fastapi import APIRouter, HTTPException
from api.models.schemas import CompetitorCreate, CompetitorResponse
from api.utils.supabase_client import get_supabase_client

# APIRouter groups related endpoints together.
# This gets "mounted" onto the main app in main.py with the prefix "/competitors"
router = APIRouter()

# Grab our Supabase connection (we'll build this helper file next)
supabase = get_supabase_client()


@router.post("/", response_model=CompetitorResponse)
def add_competitor(competitor: CompetitorCreate):
    """
    Add a new competitor to track.

    NOTE: For now, we're not enforcing real user authentication yet —
    we're using a placeholder user_id. Once Supabase Auth is fully wired
    into the frontend, we'll pull the real logged-in user's ID here instead.
    """

    # TODO: Replace this with the real authenticated user's ID once auth is wired up
    PLACEHOLDER_USER_ID = "56b30126-44f2-49e5-a52e-ed6e91d4896c"

    # Build the row we want to insert into the competitors table.
    # HttpUrl objects need to be converted to plain strings before
    # they can be stored/sent as JSON.
    new_row = {
        "user_id": PLACEHOLDER_USER_ID,
        "name": competitor.name,
        "website_url": str(competitor.website_url),
        "pricing_url": str(competitor.pricing_url) if competitor.pricing_url else None,
    }

    try:
        result = supabase.table("competitors").insert(new_row).execute()
    except Exception as e:
        # If something goes wrong talking to the database, return a clean
        # error instead of crashing the whole server.
        raise HTTPException(status_code=500, detail=f"Failed to add competitor: {str(e)}")

    # result.data is a list of the row(s) that were just inserted.
    # We return the first (only) one.
    return result.data[0]


@router.get("/", response_model=list[CompetitorResponse])
def list_competitors():
    """
    List all competitors.

    NOTE: Same placeholder situation — once auth is wired in, this will
    only return competitors belonging to the logged-in user (enforced
    by our Row Level Security policies in Supabase).
    """
    try:
        result = supabase.table("competitors").select("*").execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch competitors: {str(e)}")

    return result.data