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
    CompetitorMonitoringResponse,
    CompetitorResponse,
    CompetitorUpdate,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()


SIGNAL_TYPES = (
    "general",
    "pricing",
    "reviews",
    "jobs",
    "news",
)

SOURCE_TABLES = {
    "reviews": "review_sources",
    "jobs": "job_sources",
    "news": "news_sources",
}


def _get_owned_competitor(
    competitor_id: str,
    user_id: str,
) -> dict:
    """Retrieve one competitor only when owned by this user."""
    try:
        result = (
            supabase.table("competitors")
            .select("*")
            .eq("id", competitor_id)
            .eq("user_id", user_id)
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
    return _get_owned_competitor(
        competitor_id=str(competitor_id),
        user_id=str(current_user.id),
    )


@router.get(
    "/{competitor_id}/monitoring",
    response_model=CompetitorMonitoringResponse,
)
def get_competitor_monitoring(
    competitor_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Return real source and snapshot state for all five signals."""
    competitor_id_value = str(competitor_id)
    competitor = _get_owned_competitor(
        competitor_id=competitor_id_value,
        user_id=str(current_user.id),
    )

    source_rows = {}

    try:
        for signal_type, table_name in SOURCE_TABLES.items():
            result = (
                supabase.table(table_name)
                .select(
                    "id,source,source_url,enabled,"
                    "last_polled_at,updated_at"
                )
                .eq("competitor_id", competitor_id_value)
                .order("updated_at", desc=True)
                .execute()
            )

            rows = result.data or []
            source_rows[signal_type] = next(
                (
                    row
                    for row in rows
                    if row.get("enabled")
                ),
                rows[0] if rows else None,
            )

        latest_snapshots = {}

        for signal_type in SIGNAL_TYPES:
            result = (
                supabase.table("snapshots")
                .select("id,scraped_at")
                .eq("competitor_id", competitor_id_value)
                .eq("signal_type", signal_type)
                .order("scraped_at", desc=True)
                .limit(1)
                .execute()
            )
            latest_snapshots[signal_type] = (
                result.data[0]
                if result.data
                else None
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to fetch competitor monitoring state: "
                f"{error}"
            ),
        ) from error

    signals = []

    for signal_type in SIGNAL_TYPES:
        source = source_rows.get(signal_type)
        snapshot = latest_snapshots.get(signal_type)

        if signal_type == "general":
            configured = True
            enabled = True
            provider = "website"
            source_url = competitor["website_url"]
            source_id = None
            last_polled_at = None

        elif signal_type == "pricing":
            configured = bool(competitor.get("pricing_url"))
            enabled = configured
            provider = "pricing_page" if configured else None
            source_url = competitor.get("pricing_url")
            source_id = None
            last_polled_at = None

        else:
            configured = source is not None
            enabled = bool(
                source and source.get("enabled")
            )
            provider = (
                source.get("source")
                if source
                else None
            )
            source_url = (
                source.get("source_url")
                if source
                else None
            )
            source_id = (
                source.get("id")
                if source
                else None
            )
            last_polled_at = (
                source.get("last_polled_at")
                if source
                else None
            )

        signals.append(
            {
                "signal_type": signal_type,
                "configured": configured,
                "enabled": enabled,
                "source_id": source_id,
                "provider": provider,
                "source_url": source_url,
                "last_polled_at": last_polled_at,
                "latest_snapshot_id": (
                    snapshot.get("id")
                    if snapshot
                    else None
                ),
                "latest_snapshot_at": (
                    snapshot.get("scraped_at")
                    if snapshot
                    else None
                ),
            }
        )

    return {
        "competitor": competitor,
        "signals": signals,
    }


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
