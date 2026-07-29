"""Run Outpace monitoring directly without Redis or Celery workers."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
            print(
                f"{signal_type} failed for {target_id}: {error}",
                flush=True,
            )

            results.append(
                {
                    "signal_type": signal_type,
                    "target_id": target_id,
                    "status": "failed",
                    "error": str(error),
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
        ],
        default="scheduled",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    now = datetime.now(timezone.utc)

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
    else:
        signals = [args.scope]
        send_digest = False

    print(
        "Monitoring signals:",
        ", ".join(signals) if signals else "none",
        flush=True,
    )

    results: list[dict[str, Any]] = []

    for signal_type in signals:
        results.extend(run_signal(signal_type))

    if send_digest:
        try:
            digest_result = send_weekly_digest_task.run()
            results.append(
                {
                    "signal_type": "digest",
                    "status": "success",
                    "result": digest_result,
                }
            )
        except Exception as error:
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

    summary = {
        "started_at": now.isoformat(),
        "scope": args.scope,
        "signals": signals,
        "task_count": len(results),
        "success_count": len(results) - len(failed),
        "failure_count": len(failed),
    }

    print(json.dumps(summary, indent=2))

    if failed:
        print(json.dumps(failed, indent=2, default=str))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
