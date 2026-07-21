"""
Authenticated brief retrieval endpoints.
"""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    BriefPriority,
    BriefResponse,
    SignalType,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()


@router.get(
    "/",
    response_model=list[BriefResponse],
)
def list_briefs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    competitor_id: UUID | None = None,
    signal_type: SignalType | None = None,
    priority: BriefPriority | None = None,
    delivered: bool | None = None,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Return the authenticated user's filtered briefs."""
    try:
        query = (
            supabase.table("briefs")
            .select("*")
            .eq("user_id", str(current_user.id))
        )

        if competitor_id is not None:
            query = query.eq(
                "competitor_id",
                str(competitor_id),
            )

        if signal_type is not None:
            query = query.eq(
                "signal_type",
                signal_type.value,
            )

        if priority is not None:
            query = query.eq(
                "priority",
                priority.value,
            )

        if delivered is not None:
            query = query.eq(
                "delivered",
                delivered,
            )

        result = (
            query.order(
                "created_at",
                desc=True,
            )
            .limit(limit)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve briefs: {error}",
        ) from error

    return result.data or []


@router.get(
    "/{brief_id}",
    response_model=BriefResponse,
)
def get_brief(
    brief_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Retrieve one brief owned by the authenticated user."""
    try:
        result = (
            supabase.table("briefs")
            .select("*")
            .eq("id", str(brief_id))
            .eq("user_id", str(current_user.id))
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve brief: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Brief not found",
        )

    return result.data[0]
