"""Record collection health without creating false snapshots."""

from datetime import datetime, timezone
from typing import Any

from api.utils.supabase_client import get_supabase_client


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def classify_source_error(
    error: Exception,
) -> tuple[str, str]:
    """Map provider failures into stable operational categories."""
    message = str(error).strip()
    normalized = message.casefold()

    blocked_markers = (
        "cloudflare",
        "captcha",
        "verify you are human",
        "just a moment",
        "access denied",
        "status code 401",
        "status code 403",
        "status code 429",
        "401 unauthorized",
        "403 forbidden",
        "429 too many requests",
    )
    unsupported_markers = (
        "unsupported provider",
        "provider is reserved",
        "has not been implemented",
        "entitlement",
        "not entitled",
        "requires a permitted live provider",
    )
    degraded_markers = (
        "timed out",
        "timeout",
        "connection",
        "temporary failure",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "returned no jobs",
        "did not contain a recognized zero-openings",
        "status code 500",
        "status code 502",
        "status code 503",
        "status code 504",
    )

    if any(marker in normalized for marker in blocked_markers):
        return "blocked", "access_blocked"

    if any(
        marker in normalized
        for marker in unsupported_markers
    ):
        return "unsupported", "provider_unsupported"

    if any(marker in normalized for marker in degraded_markers):
        return "degraded", "provider_degraded"

    return "failed", "collection_failed"


def _existing_health(
    competitor_id: str,
    signal_type: str,
) -> dict[str, Any] | None:
    db = get_supabase_client()
    result = (
        db.table("monitoring_source_health")
        .select("*")
        .eq("competitor_id", competitor_id)
        .eq("signal_type", signal_type)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def _upsert_health(
    competitor_id: str,
    signal_type: str,
    values: dict[str, Any],
) -> None:
    db = get_supabase_client()
    row = {
        "competitor_id": competitor_id,
        "signal_type": signal_type,
        "updated_at": utc_now(),
        **values,
    }

    (
        db.table("monitoring_source_health")
        .upsert(
            row,
            on_conflict="competitor_id,signal_type",
        )
        .execute()
    )


def record_source_attempt(
    competitor_id: str,
    signal_type: str,
    provider: str,
    source_id: str | None = None,
) -> None:
    """Record the beginning of a collection attempt."""
    _upsert_health(
        competitor_id=competitor_id,
        signal_type=signal_type,
        values={
            "source_id": source_id,
            "provider": provider,
            "last_attempt_at": utc_now(),
        },
    )


def record_source_success(
    competitor_id: str,
    signal_type: str,
    provider: str,
    snapshot_id: str,
    source_id: str | None = None,
) -> None:
    """Mark a collection healthy only after snapshot insertion."""
    now = utc_now()
    _upsert_health(
        competitor_id=competitor_id,
        signal_type=signal_type,
        values={
            "source_id": source_id,
            "provider": provider,
            "status": "healthy",
            "last_attempt_at": now,
            "last_success_at": now,
            "last_error_code": None,
            "last_error_message": None,
            "consecutive_failures": 0,
            "metadata": {
                "latest_snapshot_id": snapshot_id,
            },
        },
    )


def record_source_failure(
    competitor_id: str,
    signal_type: str,
    provider: str,
    error: Exception,
    source_id: str | None = None,
) -> None:
    """Record failure details while preserving the last good snapshot."""
    existing = _existing_health(
        competitor_id=competitor_id,
        signal_type=signal_type,
    )
    status, error_code = classify_source_error(error)
    now = utc_now()
    message = str(error).strip() or error.__class__.__name__

    _upsert_health(
        competitor_id=competitor_id,
        signal_type=signal_type,
        values={
            "source_id": source_id,
            "provider": provider,
            "status": status,
            "last_attempt_at": now,
            "last_failure_at": now,
            "last_error_code": error_code,
            "last_error_message": message[:1_000],
            "consecutive_failures": int(
                (existing or {}).get(
                    "consecutive_failures",
                    0,
                )
            ) + 1,
        },
    )


def get_source_context(
    table_name: str,
    source_id: str,
) -> dict[str, str]:
    """Resolve a provider source before its collection starts."""
    db = get_supabase_client()
    result = (
        db.table(table_name)
        .select("id,competitor_id,source")
        .eq("id", source_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(
            f"Monitoring source not found: {source_id}"
        )

    row = result.data[0]

    return {
        "source_id": row["id"],
        "competitor_id": row["competitor_id"],
        "provider": row["source"],
    }
