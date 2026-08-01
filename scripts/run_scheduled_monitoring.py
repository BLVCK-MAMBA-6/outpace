"""Run Outpace monitoring directly without Redis or Celery workers."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from api.utils.observability import (
    flush_sentry,
    initialize_sentry,
    report_exception,
    report_message,
)
from api.utils.supabase_client import get_supabase_client

initialize_sentry(
    service="worker",
)

from workers.source_health import classify_source_error
from workers.tasks import (
    list_competitors,
    list_enabled_sources,
    monitor_general,
    monitor_jobs,
    monitor_news,
    monitor_pricing,
    monitor_reviews,
    send_weekly_digest_task,
)


TaskRunner = Callable[[str], dict[str, Any]]

DATABASE_TASKS = {
    "general": monitor_general,
    "pricing": monitor_pricing,
    "reviews": monitor_reviews,
    "jobs": monitor_jobs,
    "news": monitor_news,
}

NON_FATAL_SOURCE_STATUSES = {
    "blocked",
    "unsupported",
    "degraded",
}


def classify_monitoring_error(
    error: Exception,
) -> dict[str, str]:
    """Classify source degradation separately from runner failures."""
    health_status, error_code = classify_source_error(error)

    return {
        "status": (
            "degraded"
            if health_status in NON_FATAL_SOURCE_STATUSES
            else "failed"
        ),
        "health_status": health_status,
        "error_code": error_code,
    }


def digest_execution_result(
    digest_result: dict[str, Any],
) -> dict[str, Any]:
    """Convert per-user delivery results into runner status."""
    failure_count = int(
        digest_result.get("failure_count") or 0
    )

    execution = {
        "signal_type": "digest",
        "status": (
            "failed"
            if failure_count
            else "success"
        ),
        "result": digest_result,
    }

    if failure_count:
        execution["error"] = (
            f"{failure_count} user digest "
            "delivery failure(s)"
        )
        report_message(
            (
                "Weekly digest fan-out reported "
                "delivery failures."
            ),
            tags={
                "signal_type": "digest",
                "failure_count": failure_count,
            },
        )

    return execution


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def json_safe(value: Any) -> Any:
    """Convert task results to JSON-compatible values."""
    return json.loads(
        json.dumps(value, default=str)
    )


def github_annotation(
    level: str,
    title: str,
    message: str,
) -> None:
    """Write a readable GitHub Actions annotation when running in CI."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return

    def escape(value: str) -> str:
        return (
            value
            .replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
            .replace(":", "%3A")
            .replace(",", "%2C")
        )

    print(
        f"::{level} title={escape(title)}::"
        f"{escape(message[:4000])}",
        flush=True,
    )


def recover_interrupted_tasks() -> int:
    """Return old STARTED tasks to the pending queue."""
    db = get_supabase_client()
    cutoff = (
        utc_now() - timedelta(hours=4)
    ).isoformat()

    result = (
        db.table("monitoring_tasks")
        .update(
            {
                "state": "PENDING",
                "started_at": None,
                "updated_at": utc_now().isoformat(),
                "error": (
                    "Previous runner stopped before completion; "
                    "task was queued again."
                ),
            }
        )
        .eq("execution_backend", "database")
        .eq("state", "STARTED")
        .lt("started_at", cutoff)
        .execute()
    )

    return len(result.data or [])


def claim_pending_task(
    task_id: str,
) -> dict[str, Any] | None:
    """Atomically claim one pending database task."""
    db = get_supabase_client()
    now = utc_now().isoformat()

    result = (
        db.table("monitoring_tasks")
        .update(
            {
                "state": "STARTED",
                "started_at": now,
                "completed_at": None,
                "updated_at": now,
                "result": None,
                "error": None,
            }
        )
        .eq("task_id", task_id)
        .eq("execution_backend", "database")
        .eq("state", "PENDING")
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def finish_database_task(
    task_id: str,
    result: dict[str, Any],
) -> None:
    """Persist a successful database task result."""
    now = utc_now().isoformat()

    (
        get_supabase_client()
        .table("monitoring_tasks")
        .update(
            {
                "state": "SUCCESS",
                "result": json_safe(result),
                "error": None,
                "completed_at": now,
                "updated_at": now,
            }
        )
        .eq("task_id", task_id)
        .eq("state", "STARTED")
        .execute()
    )


def fail_database_task(
    task_id: str,
    error: Exception,
) -> None:
    """Persist a failed database task result."""
    now = utc_now().isoformat()

    (
        get_supabase_client()
        .table("monitoring_tasks")
        .update(
            {
                "state": "FAILURE",
                "result": None,
                "error": str(error)[:4000],
                "completed_at": now,
                "updated_at": now,
            }
        )
        .eq("task_id", task_id)
        .eq("state", "STARTED")
        .execute()
    )


def run_pending_tasks(
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Run pending user-requested tasks from Supabase."""
    db = get_supabase_client()
    recovered = recover_interrupted_tasks()

    if recovered:
        print(
            f"Recovered {recovered} interrupted task(s).",
            flush=True,
        )

    pending_result = (
        db.table("monitoring_tasks")
        .select(
            "task_id,signal_type,target_id,"
            "target_type,created_at"
        )
        .eq("execution_backend", "database")
        .eq("state", "PENDING")
        .order("created_at")
        .limit(limit)
        .execute()
    )

    results: list[dict[str, Any]] = []

    for pending in pending_result.data or []:
        task_id = str(pending["task_id"])
        claimed = claim_pending_task(task_id)

        if claimed is None:
            continue

        signal_type = str(claimed["signal_type"])
        target_id = str(claimed["target_id"])
        task = DATABASE_TASKS.get(signal_type)

        print(
            f"Running requested {signal_type}: {target_id}",
            flush=True,
        )

        if task is None:
            error = ValueError(
                f"Unsupported queued signal: {signal_type}"
            )
            fail_database_task(task_id, error)
            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(error),
                }
            )
            continue

        try:
            task_result = task.run(target_id)
            finish_database_task(task_id, task_result)
            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "task_id": task_id,
                    "status": "success",
                    "result": task_result,
                }
            )
        except Exception as error:
            classification = classify_monitoring_error(error)

            if classification["status"] == "failed":
                report_exception(
                    error,
                    tags={
                        "execution_path": "pending-task",
                        "signal_type": signal_type,
                    },
                )

            fail_database_task(task_id, error)
            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "task_id": task_id,
                    "status": classification["status"],
                    "error": str(error),
                    "health_status": classification["health_status"],
                    "error_code": classification["error_code"],
                }
            )

    return results


def run_targets(
    signal_type: str,
    targets: list[dict[str, Any]],
    task: Any,
    id_key: str,
) -> list[dict[str, Any]]:
    """Run one monitoring task per target and retain compact results."""
    results = []

    for target in targets:
        target_id = str(target[id_key])

        print(f"Running {signal_type}: {target_id}", flush=True)

        try:
            result = task.run(target_id)

            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "status": "success",
                    "result": result,
                }
            )
        except Exception as error:
            classification = classify_monitoring_error(error)

            if classification["status"] == "failed":
                report_exception(
                    error,
                    tags={
                        "execution_path": "scheduled-target",
                        "signal_type": signal_type,
                    },
                )

            print(
                f"{signal_type} {classification['status']} "
                f"for {target_id}: {error}",
                flush=True,
            )

            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "status": classification["status"],
                    "error": str(error),
                    "health_status": classification["health_status"],
                    "error_code": classification["error_code"],
                }
            )

    return results


def run_signal(signal_type: str) -> list[dict[str, Any]]:
    """Run all configured targets for one signal type."""
    if signal_type == "general":
        return run_targets(
            signal_type="general",
            targets=list_competitors(),
            task=monitor_general,
            id_key="id",
        )

    if signal_type == "pricing":
        return run_targets(
            signal_type="pricing",
            targets=list_competitors(require_pricing_url=True),
            task=monitor_pricing,
            id_key="id",
        )

    source_config = {
        "reviews": (
            "review_sources",
            monitor_reviews,
        ),
        "jobs": (
            "job_sources",
            monitor_jobs,
        ),
        "news": (
            "news_sources",
            monitor_news,
        ),
    }

    table_name, task = source_config[signal_type]

    return run_targets(
        signal_type=signal_type,
        targets=list_enabled_sources(table_name),
        task=task,
        id_key="id",
    )


def scheduled_signals(now: datetime) -> list[str]:
    """Return signals due during the current twice-daily cycle."""
    signals = ["jobs", "news"]

    morning_cycle = now.hour < 12

    if morning_cycle:
        signals.append("reviews")

        if now.toordinal() % 2 == 0:
            signals.append("pricing")

        if now.weekday() == 0:
            signals.append("general")

    return signals


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scope",
        choices=[
            "scheduled",
            "all",
            "general",
            "pricing",
            "reviews",
            "jobs",
            "news",
            "digest",
            "pending",
        ],
        default="scheduled",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    now = utc_now()

    if args.scope == "scheduled":
        signals = scheduled_signals(now)
        send_digest = now.hour < 12 and now.weekday() == 0
    elif args.scope == "all":
        signals = [
            "general",
            "pricing",
            "reviews",
            "jobs",
            "news",
        ]
        send_digest = False
    elif args.scope == "digest":
        signals = []
        send_digest = True
    elif args.scope == "pending":
        signals = []
        send_digest = False
    else:
        signals = [args.scope]
        send_digest = False

    print(
        "Monitoring signals:",
        ", ".join(signals) if signals else "none",
        flush=True,
    )

    results = run_pending_tasks()

    for signal_type in signals:
        results.extend(run_signal(signal_type))

    if send_digest:
        try:
            digest_result = send_weekly_digest_task.run()
            results.append(
                digest_execution_result(
                    digest_result
                )
            )
        except Exception as error:
            report_exception(
                error,
                tags={
                    "execution_path": "digest",
                    "signal_type": "digest",
                },
            )
            results.append(
                {
                    "signal_type": "digest",
                    "status": "failed",
                    "error": str(error),
                }
            )

    failed = [
        result
        for result in results
        if result["status"] == "failed"
    ]
    degraded = [
        result
        for result in results
        if result["status"] == "degraded"
    ]

    summary = {
        "started_at": now.isoformat(),
        "scope": args.scope,
        "signals": signals,
        "task_count": len(results),
        "success_count": sum(
            result["status"] == "success"
            for result in results
        ),
        "degraded_count": len(degraded),
        "failure_count": len(failed),
        "status": (
            "partial_failure"
            if failed and len(failed) < len(results)
            else "failure"
            if failed
            else "degraded"
            if degraded
            else "success"
        ),
    }

    print(json.dumps(summary, indent=2))

    if degraded:
        print(json.dumps(degraded, indent=2, default=str))
        for degradation in degraded:
            github_annotation(
                level="warning",
                title=(
                    "Monitoring source degraded: "
                    f"{degradation.get('signal_type', 'unknown')}"
                ),
                message=(
                    f"Target "
                    f"{degradation.get('target_id', 'unknown')}: "
                    f"{degradation.get('error', 'Unknown error')}"
                ),
            )

    if failed:
        print(json.dumps(failed, indent=2, default=str))
        for failure in failed:
            github_annotation(
                level="error",
                title=(
                    "Monitoring source failed: "
                    f"{failure.get('signal_type', 'unknown')}"
                ),
                message=(
                    f"Target {failure.get('target_id', 'unknown')}: "
                    f"{failure.get('error', 'Unknown error')}"
                ),
            )
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        flush_sentry()
