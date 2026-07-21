"""
Celery tasks for collecting signals and running the Outpace pipeline.

Scheduled fan-out tasks discover enabled competitors or source rows and
enqueue one monitoring task per target.
"""

import asyncio
import os
from typing import Any

from api.utils.supabase_client import get_supabase_client
from workers.celery_app import celery_app
from workers.email.digest import send_weekly_digest
from workers.pipeline import run_pipeline
from workers.scrapers.general import scrape_competitor
from workers.scrapers.jobs import collect_jobs
from workers.scrapers.news import collect_news
from workers.scrapers.pricing import scrape_pricing
from workers.scrapers.reviews import collect_reviews


def excluded_competitor_ids() -> set[str]:
    """Read comma-separated competitor IDs excluded from automation."""
    raw_value = os.getenv(
        "MONITORING_EXCLUDED_COMPETITOR_IDS",
        "",
    )

    return {
        value.strip()
        for value in raw_value.split(",")
        if value.strip()
    }


def summarize_pipeline(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Keep Celery results small instead of storing entire raw diffs."""
    summary = {
        "status": result.get("status"),
    }

    for key in (
        "competitor_id",
        "competitor_name",
        "signal_type",
        "snapshot_count",
        "message",
    ):
        if key in result:
            summary[key] = result[key]

    brief = result.get("brief")

    if isinstance(brief, dict):
        summary["brief_id"] = brief.get("id")
        summary["priority"] = brief.get("priority")

    if "model" in result:
        summary["model"] = result["model"]

    return summary


def list_competitors(
    require_pricing_url: bool = False,
) -> list[dict[str, Any]]:
    """Return monitorable competitors from Supabase."""
    db = get_supabase_client()

    result = (
        db.table("competitors")
        .select("id,name,website_url,pricing_url")
        .execute()
    )

    excluded = excluded_competitor_ids()
    competitors = []

    for competitor in result.data or []:
        if competitor["id"] in excluded:
            continue

        if (
            require_pricing_url
            and not competitor.get("pricing_url")
        ):
            continue

        competitors.append(competitor)

    return competitors


def list_enabled_sources(
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Return enabled non-manual source rows.

    Manual fixture sources are deliberately excluded from scheduled
    automation so synthetic data cannot enter routine monitoring.
    """
    db = get_supabase_client()

    result = (
        db.table(table_name)
        .select("id,competitor_id,source,enabled")
        .eq("enabled", True)
        .execute()
    )

    excluded = excluded_competitor_ids()

    return [
        source
        for source in result.data or []
        if source.get("source") != "manual"
        and source["competitor_id"] not in excluded
    ]


@celery_app.task(
    name="outpace.monitor_general",
)
def monitor_general(
    competitor_id: str,
) -> dict[str, Any]:
    """Collect a homepage snapshot and process its diff."""
    snapshot = asyncio.run(
        scrape_competitor(competitor_id)
    )

    pipeline_result = run_pipeline(
        competitor_id=competitor_id,
        signal_type="general",
    )

    return {
        "signal_type": "general",
        "competitor_id": competitor_id,
        "snapshot_id": snapshot["id"],
        "pipeline": summarize_pipeline(
            pipeline_result
        ),
    }


@celery_app.task(
    name="outpace.monitor_pricing",
)
def monitor_pricing(
    competitor_id: str,
) -> dict[str, Any]:
    """Collect a pricing snapshot and process its diff."""
    snapshot = asyncio.run(
        scrape_pricing(competitor_id)
    )

    pipeline_result = run_pipeline(
        competitor_id=competitor_id,
        signal_type="pricing",
    )

    return {
        "signal_type": "pricing",
        "competitor_id": competitor_id,
        "snapshot_id": snapshot["id"],
        "pipeline": summarize_pipeline(
            pipeline_result
        ),
    }


@celery_app.task(
    name="outpace.monitor_reviews",
)
def monitor_reviews(
    source_id: str,
) -> dict[str, Any]:
    """Collect a review snapshot and process its diff."""
    snapshot = collect_reviews(source_id)
    competitor_id = snapshot["competitor_id"]

    pipeline_result = run_pipeline(
        competitor_id=competitor_id,
        signal_type="reviews",
    )

    return {
        "signal_type": "reviews",
        "competitor_id": competitor_id,
        "source_id": source_id,
        "snapshot_id": snapshot["id"],
        "pipeline": summarize_pipeline(
            pipeline_result
        ),
    }


@celery_app.task(
    name="outpace.monitor_jobs",
)
def monitor_jobs(
    source_id: str,
) -> dict[str, Any]:
    """Collect a job snapshot and process its diff."""
    snapshot = collect_jobs(source_id)
    competitor_id = snapshot["competitor_id"]

    pipeline_result = run_pipeline(
        competitor_id=competitor_id,
        signal_type="jobs",
    )

    return {
        "signal_type": "jobs",
        "competitor_id": competitor_id,
        "source_id": source_id,
        "snapshot_id": snapshot["id"],
        "pipeline": summarize_pipeline(
            pipeline_result
        ),
    }


@celery_app.task(
    name="outpace.monitor_news",
)
def monitor_news(
    source_id: str,
) -> dict[str, Any]:
    """Collect a news snapshot and process its diff."""
    snapshot = collect_news(source_id)
    competitor_id = snapshot["competitor_id"]

    pipeline_result = run_pipeline(
        competitor_id=competitor_id,
        signal_type="news",
    )

    return {
        "signal_type": "news",
        "competitor_id": competitor_id,
        "source_id": source_id,
        "snapshot_id": snapshot["id"],
        "pipeline": summarize_pipeline(
            pipeline_result
        ),
    }


@celery_app.task(
    name="outpace.send_weekly_digest",
)
def send_weekly_digest_task() -> dict[str, Any]:
    """
    Send real undelivered briefs for the configured MVP user.

    Synthetic fixture briefs are excluded by the digest module.
    """
    user_id = os.getenv("DIGEST_USER_ID")

    if not user_id:
        raise ValueError(
            "DIGEST_USER_ID is missing from .env"
        )

    return send_weekly_digest(user_id)


@celery_app.task(
    name="outpace.schedule_general_monitoring",
)
def schedule_general_monitoring() -> dict[str, Any]:
    """Enqueue weekly homepage monitoring tasks."""
    competitors = list_competitors()
    queued = []

    for competitor in competitors:
        task = monitor_general.delay(
            competitor["id"]
        )

        queued.append(
            {
                "task_id": task.id,
                "competitor_id": competitor["id"],
                "competitor_name": competitor["name"],
            }
        )

    return {
        "signal_type": "general",
        "queued_count": len(queued),
        "queued": queued,
    }


@celery_app.task(
    name="outpace.schedule_pricing_monitoring",
)
def schedule_pricing_monitoring() -> dict[str, Any]:
    """Enqueue pricing monitoring for competitors with pricing URLs."""
    competitors = list_competitors(
        require_pricing_url=True
    )
    queued = []

    for competitor in competitors:
        task = monitor_pricing.delay(
            competitor["id"]
        )

        queued.append(
            {
                "task_id": task.id,
                "competitor_id": competitor["id"],
                "competitor_name": competitor["name"],
            }
        )

    return {
        "signal_type": "pricing",
        "queued_count": len(queued),
        "queued": queued,
    }


def enqueue_source_tasks(
    table_name: str,
    signal_type: str,
    task_function: Any,
) -> dict[str, Any]:
    """Enqueue one task for every enabled non-manual source."""
    sources = list_enabled_sources(table_name)
    queued = []

    for source in sources:
        task = task_function.delay(
            source["id"]
        )

        queued.append(
            {
                "task_id": task.id,
                "source_id": source["id"],
                "competitor_id": (
                    source["competitor_id"]
                ),
                "provider": source["source"],
            }
        )

    return {
        "signal_type": signal_type,
        "queued_count": len(queued),
        "queued": queued,
    }


@celery_app.task(
    name="outpace.schedule_review_monitoring",
)
def schedule_review_monitoring() -> dict[str, Any]:
    """Enqueue enabled live review sources."""
    return enqueue_source_tasks(
        table_name="review_sources",
        signal_type="reviews",
        task_function=monitor_reviews,
    )


@celery_app.task(
    name="outpace.schedule_job_monitoring",
)
def schedule_job_monitoring() -> dict[str, Any]:
    """Enqueue enabled live job sources."""
    return enqueue_source_tasks(
        table_name="job_sources",
        signal_type="jobs",
        task_function=monitor_jobs,
    )


@celery_app.task(
    name="outpace.schedule_news_monitoring",
)
def schedule_news_monitoring() -> dict[str, Any]:
    """Enqueue enabled live news sources."""
    return enqueue_source_tasks(
        table_name="news_sources",
        signal_type="news",
        task_function=monitor_news,
    )
