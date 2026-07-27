"""
Authenticated competitor management endpoints.
"""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    CompetitorCreate,
    CompetitorMonitoringResponse,
    CompetitorResponse,
    CompetitorUpdate,
    JobSourceCreate,
    JobSourceDiscoveryRequest,
    JobSourceDiscoveryResponse,
    MonitoringSourceResponse,
    NewsSourceCreate,
)
from api.utils.supabase_client import get_supabase_client
from workers.source_discovery import discover_job_source


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


def _validated_provider_identifier(
    value: str,
    label: str,
) -> str:
    """Reject malformed provider IDs before they reach storage."""
    normalized = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
        raise HTTPException(
            status_code=422,
            detail=f"{label} contains unsupported characters",
        )
    return normalized


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

        health_result = (
            supabase.table("monitoring_source_health")
            .select(
                "signal_type,status,last_attempt_at,"
                "last_success_at,last_failure_at,"
                "last_error_code,last_error_message,"
                "consecutive_failures"
            )
            .eq("competitor_id", competitor_id_value)
            .execute()
        )
        health_rows = {
            row["signal_type"]: row
            for row in health_result.data or []
        }

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
        health = health_rows.get(signal_type)

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

        if not configured:
            health_status = "unconfigured"
        elif not enabled:
            health_status = "disabled"
        elif health:
            health_status = health["status"]
        elif snapshot:
            health_status = "healthy"
        else:
            health_status = "pending"

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
                "health_status": health_status,
                "last_attempt_at": (
                    health.get("last_attempt_at")
                    if health
                    else None
                ),
                "last_success_at": (
                    health.get("last_success_at")
                    if health
                    else (
                        snapshot.get("scraped_at")
                        if snapshot
                        else None
                    )
                ),
                "last_failure_at": (
                    health.get("last_failure_at")
                    if health
                    else None
                ),
                "last_error_code": (
                    health.get("last_error_code")
                    if health
                    else None
                ),
                "last_error_message": (
                    health.get("last_error_message")
                    if health
                    else None
                ),
                "consecutive_failures": int(
                    health.get("consecutive_failures", 0)
                    if health
                    else 0
                ),
            }
        )

    return {
        "competitor": competitor,
        "signals": signals,
    }


def _source_response(
    row: dict,
    signal_type: str,
) -> dict:
    """Map a provider row to the public source response."""
    return {
        "id": row["id"],
        "competitor_id": row["competitor_id"],
        "signal_type": signal_type,
        "provider": row["source"],
        "source_url": row["source_url"],
        "enabled": row["enabled"],
    }


@router.post(
    "/{competitor_id}/sources/jobs/discover",
    response_model=JobSourceDiscoveryResponse,
)
def discover_jobs_source(
    competitor_id: UUID,
    request: JobSourceDiscoveryRequest,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Suggest a verified public careers provider for confirmation."""
    competitor = _get_owned_competitor(
        competitor_id=str(competitor_id),
        user_id=str(current_user.id),
    )

    try:
        return discover_job_source(
            careers_url=str(request.careers_url),
            company_name=competitor["name"],
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Careers source discovery failed safely: "
                f"{error}"
            ),
        ) from error


@router.post(
    "/{competitor_id}/sources/jobs",
    response_model=MonitoringSourceResponse,
    status_code=201,
)
def configure_job_source(
    competitor_id: UUID,
    source: JobSourceCreate,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Configure the supported careers source for a competitor."""
    competitor_id_value = str(competitor_id)
    competitor = _get_owned_competitor(
        competitor_id=competitor_id_value,
        user_id=str(current_user.id),
    )
    source_url = str(source.source_url)
    metadata = {
        "company_name": competitor["name"],
    }
    external_source_id = source.external_source_id

    if source.provider == "github":
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]

        if host not in {"github.com", "www.github.com"} or len(
            path_parts
        ) < 2:
            raise HTTPException(
                status_code=422,
                detail=(
                    "GitHub careers source must be a public "
                    "github.com owner/repository URL"
                ),
            )

        owner = path_parts[0]
        repo = path_parts[1].removesuffix(".git")
        external_source_id = f"{owner}/{repo}"
        metadata.update(
            {
                "owner": owner,
                "repo": repo,
                "branch": source.branch.strip(),
                "readme_path": source.readme_path.strip(),
            }
        )
    elif source.provider == "ashby":
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]
        board_name = (
            source.board_name.strip()
            if source.board_name
            else (
                source.external_source_id
                or (
                    path_parts[0]
                    if host in {
                        "jobs.ashbyhq.com",
                        "www.jobs.ashbyhq.com",
                    } and path_parts
                    else ""
                )
            )
        )

        if not board_name:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Ashby sources require a jobs.ashbyhq.com "
                    "board URL or board_name"
                ),
            )

        board_name = _validated_provider_identifier(
            board_name,
            "Ashby board name",
        )
        external_source_id = board_name
        metadata["board_name"] = board_name

    elif source.provider == "greenhouse":
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]
        board_token = source.external_source_id or ""

        if not board_token and host in {
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
        } and path_parts:
            board_token = (
                (parse_qs(parsed.query).get("for") or [""])[0]
                if path_parts[0] == "embed"
                else path_parts[0]
            )
        elif (
            not board_token
            and host == "boards-api.greenhouse.io"
            and len(path_parts) >= 3
            and path_parts[:2] == ["v1", "boards"]
        ):
            board_token = path_parts[2]

        if not board_token:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Greenhouse sources require a hosted board URL "
                    "or verified external_source_id"
                ),
            )

        board_token = _validated_provider_identifier(
            board_token,
            "Greenhouse board token",
        )
        external_source_id = board_token
        metadata["board_token"] = board_token

    elif source.provider == "lever":
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]
        site_name = source.external_source_id or ""

        if not site_name and host in {
            "jobs.lever.co",
            "jobs.eu.lever.co",
        } and path_parts:
            site_name = path_parts[0]
        elif (
            not site_name
            and host in {
                "api.lever.co",
                "api.eu.lever.co",
            }
            and len(path_parts) >= 3
            and path_parts[:2] == ["v0", "postings"]
        ):
            site_name = path_parts[2]

        if not site_name:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Lever sources require a hosted jobs URL "
                    "or verified external_source_id"
                ),
            )

        site_name = _validated_provider_identifier(
            site_name,
            "Lever site name",
        )
        region = source.region or (
            "eu" if ".eu.lever.co" in host else "global"
        )
        external_source_id = site_name
        metadata.update(
            {
                "site_name": site_name,
                "region": region,
            }
        )

    elif source.provider == "deel":
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower()
        path_parts = [
            part
            for part in parsed.path.strip("/").split("/")
            if part
        ]
        tenant = source.external_source_id or ""

        if (
            not tenant
            and host in {
                "jobs.deel.com",
                "www.jobs.deel.com",
            }
            and path_parts
        ):
            tenant = path_parts[0]

        if not tenant:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Deel sources require a jobs.deel.com tenant "
                    "URL or verified external_source_id"
                ),
            )

        tenant = _validated_provider_identifier(
            tenant,
            "Deel tenant",
        )
        external_source_id = tenant
        metadata["tenant"] = tenant

    else:
        metadata["job_link_path"] = (
            source.job_link_path.strip()
        )

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "competitor_id": competitor_id_value,
        "source": source.provider,
        "external_source_id": external_source_id,
        "source_url": source_url,
        "enabled": True,
        "metadata": metadata,
        "updated_at": now,
    }

    try:
        result = (
            supabase.table("job_sources")
            .upsert(
                row,
                on_conflict="competitor_id,source",
            )
            .execute()
        )

        if not result.data:
            raise RuntimeError(
                "Database returned no job source"
            )

        stored = result.data[0]

        (
            supabase.table("job_sources")
            .update(
                {
                    "enabled": False,
                    "updated_at": now,
                }
            )
            .eq("competitor_id", competitor_id_value)
            .neq("id", stored["id"])
            .execute()
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure job source: {error}",
        ) from error

    return _source_response(
        stored,
        "jobs",
    )


@router.post(
    "/{competitor_id}/sources/news",
    response_model=MonitoringSourceResponse,
    status_code=201,
)
def configure_news_source(
    competitor_id: UUID,
    source: NewsSourceCreate,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Configure one supported official blog or newsroom source."""
    competitor_id_value = str(competitor_id)
    competitor = _get_owned_competitor(
        competitor_id=competitor_id_value,
        user_id=str(current_user.id),
    )
    source_url = str(source.source_url)
    keywords = []
    seen_keywords = set()

    for keyword in source.keywords:
        normalized = keyword.strip()
        comparison_key = normalized.casefold()

        if normalized and comparison_key not in seen_keywords:
            keywords.append(normalized)
            seen_keywords.add(comparison_key)

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "competitor_id": competitor_id_value,
        "source": source.provider,
        "external_source_id": None,
        "source_url": source_url,
        "enabled": True,
        "keywords": keywords,
        "metadata": {
            "company_name": competitor["name"],
            "article_link_path": (
                source.article_link_path.strip()
            ),
            "max_articles": source.max_articles,
        },
        "updated_at": now,
    }

    try:
        result = (
            supabase.table("news_sources")
            .upsert(
                row,
                on_conflict=(
                    "competitor_id,source,source_url"
                ),
            )
            .execute()
        )

        if not result.data:
            raise RuntimeError(
                "Database returned no news source"
            )

        stored = result.data[0]

        (
            supabase.table("news_sources")
            .update(
                {
                    "enabled": False,
                    "updated_at": now,
                }
            )
            .eq("competitor_id", competitor_id_value)
            .neq("id", stored["id"])
            .execute()
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure news source: {error}",
        ) from error

    return _source_response(
        stored,
        "news",
    )


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
