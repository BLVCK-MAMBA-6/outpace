"""
Authenticated competitor management endpoints.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    CompetitorCreate,
    CompetitorResponse,
    CompetitorUpdate,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()


@router.post(
    "/",
    response_model=CompetitorResponse,
    status_code=201,
)
def add_competitor(
    competitor: CompetitorCreate,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Create a competitor owned by the authenticated user."""
    row = {
        "user_id": str(current_user.id),
        "name": competitor.name.strip(),
        "website_url": str(competitor.website_url),
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
def list_competitors(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """List competitors owned by the authenticated user."""
    try:
        result = (
            supabase.table("competitors")
            .select("*")
            .eq("user_id", str(current_user.id))
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
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Retrieve one competitor owned by the authenticated user."""
    try:
        result = (
            supabase.table("competitors")
            .select("*")
            .eq("id", str(competitor_id))
            .eq("user_id", str(current_user.id))
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
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Update one competitor owned by the authenticated user."""
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
            .eq("user_id", str(current_user.id))
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
