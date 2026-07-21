"""
Competitor management endpoints.

Authentication remains a known MVP shortcut. All queries are scoped to
the placeholder user until Supabase Auth is connected.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from api.models.schemas import (
    CompetitorCreate,
    CompetitorResponse,
    CompetitorUpdate,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()

PLACEHOLDER_USER_ID = (
    "56b30126-44f2-49e5-a52e-ed6e91d4896c"
)


@router.post(
    "/",
    response_model=CompetitorResponse,
    status_code=201,
)
def add_competitor(
    competitor: CompetitorCreate,
):
    """Create a competitor for the current MVP user."""
    row = {
        "user_id": PLACEHOLDER_USER_ID,
        "name": competitor.name.strip(),
        "website_url": str(
            competitor.website_url
        ),
        "pricing_url": (
            str(competitor.pricing_url)
            if competitor.pricing_url
            else None
        ),
    }

    try:
        result = (
            supabase.table("competitors")
            .insert(row)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add competitor: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Database returned no competitor",
        )

    return result.data[0]


@router.get(
    "/",
    response_model=list[CompetitorResponse],
)
def list_competitors():
    """List competitors belonging to the MVP user."""
    try:
        result = (
            supabase.table("competitors")
            .select("*")
            .eq("user_id", PLACEHOLDER_USER_ID)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch competitors: {error}",
        ) from error

    return result.data or []


@router.get(
    "/{competitor_id}",
    response_model=CompetitorResponse,
)
def get_competitor(
    competitor_id: UUID,
):
    """Retrieve one competitor belonging to the MVP user."""
    try:
        result = (
            supabase.table("competitors")
            .select("*")
            .eq("id", str(competitor_id))
            .eq("user_id", PLACEHOLDER_USER_ID)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch competitor: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Competitor not found",
        )

    return result.data[0]


@router.patch(
    "/{competitor_id}",
    response_model=CompetitorResponse,
)
def update_competitor(
    competitor_id: UUID,
    competitor: CompetitorUpdate,
):
    """Update supplied fields on one competitor."""
    supplied = competitor.model_dump(
        exclude_unset=True
    )

    if not supplied:
        raise HTTPException(
            status_code=400,
            detail="No update fields were supplied",
        )

    updates = {}

    for field, value in supplied.items():
        if field in {
            "website_url",
            "pricing_url",
        }:
            updates[field] = (
                str(value)
                if value is not None
                else None
            )
        elif field == "name":
            updates[field] = value.strip()
        else:
            updates[field] = value

    updates["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        result = (
            supabase.table("competitors")
            .update(updates)
            .eq("id", str(competitor_id))
            .eq("user_id", PLACEHOLDER_USER_ID)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update competitor: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Competitor not found",
        )

    return result.data[0]
