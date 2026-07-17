"""
Brief retrieval endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from api.models.schemas import BriefResponse
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()

# Replace this after Supabase Auth is implemented.
PLACEHOLDER_USER_ID = "56b30126-44f2-49e5-a52e-ed6e91d4896c"


@router.get("/", response_model=list[BriefResponse])
def list_briefs(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return the current user's briefs, newest first."""
    try:
        result = (
            supabase.table("briefs")
            .select("*")
            .eq("user_id", PLACEHOLDER_USER_ID)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve briefs: {error}",
        ) from error

    return result.data