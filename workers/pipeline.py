"""
End-to-end competitor monitoring pipeline.

Run:

    python -m workers.pipeline --competitor-id <UUID>
"""

import argparse
import json
from typing import Any

from api.utils.supabase_client import get_supabase_client
from workers.diffing import compare_latest_snapshots, valid_uuid
from workers.synthesis import generate_brief


def get_competitor(competitor_id: str) -> dict[str, Any]:
    """Retrieve the competitor and its owner."""
    supabase = get_supabase_client()

    result = (
        supabase.table("competitors")
        .select("id,name,user_id")
        .eq("id", competitor_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(f"No competitor found with id: {competitor_id}")

    return result.data[0]


def find_existing_brief(
    competitor_id: str,
    new_snapshot_id: str,
    signal_type: str,
) -> dict[str, Any] | None:
    """Prevent duplicate briefs when a pipeline job is retried."""
    supabase = get_supabase_client()

    result = (
        supabase.table("briefs")
        .select("*")
        .eq("competitor_id", competitor_id)
        .eq("new_snapshot_id", new_snapshot_id)
        .eq("signal_type", signal_type)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def store_brief(
    competitor: dict[str, Any],
    signal_type: str,
    diff: dict[str, Any],
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    """Store a generated brief in Supabase."""
    old_snapshot_id = diff.get("old_snapshot_id")
    new_snapshot_id = diff.get("new_snapshot_id")

    if not old_snapshot_id or not new_snapshot_id:
        raise ValueError(
            "The diff must contain old_snapshot_id and new_snapshot_id"
        )

    row = {
        "competitor_id": competitor["id"],
        "user_id": competitor["user_id"],
        "signal_type": signal_type,
        "old_snapshot_id": old_snapshot_id,
        "new_snapshot_id": new_snapshot_id,
        "raw_diff": diff,
        "synthesis": synthesis,
        "priority": synthesis["priority"],
        "delivered": False,
    }

    supabase = get_supabase_client()
    result = supabase.table("briefs").insert(row).execute()

    if not result.data:
        raise RuntimeError("Supabase did not return the inserted brief")

    return result.data[0]


def run_pipeline(
    competitor_id: str,
    signal_type: str = "general",
) -> dict[str, Any]:
    """Run diffing, synthesis, and storage for one competitor."""
    competitor = get_competitor(competitor_id)

    diff = compare_latest_snapshots(
        competitor_id=competitor_id,
        signal_type=signal_type,
    )

    if diff.get("status") == "insufficient_snapshots":
        return diff

    if not diff.get("has_changes"):
        return {
            "status": "no_changes",
            "competitor_id": competitor_id,
            "competitor_name": competitor["name"],
            "message": (
                "No meaningful change was detected. "
                "Gemini was not called and no brief was stored."
            ),
        }

    existing_brief = find_existing_brief(
        competitor_id=competitor_id,
        new_snapshot_id=diff["new_snapshot_id"],
        signal_type=signal_type,
    )

    if existing_brief:
        return {
            "status": "already_stored",
            "brief": existing_brief,
        }

    generated = generate_brief(
        competitor_name=competitor["name"],
        signal_type=signal_type,
        diff=diff,
    )

    brief = store_brief(
        competitor=competitor,
        signal_type=signal_type,
        diff=diff,
        synthesis=generated["synthesis"],
    )

    return {
        "status": "brief_stored",
        "model": generated["model"],
        "attempt": generated["attempt"],
        "brief": brief,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Outpace monitoring pipeline"
    )

    parser.add_argument(
        "--competitor-id",
        required=True,
        type=valid_uuid,
        help="Competitor UUID",
    )

    parser.add_argument(
        "--signal-type",
        default="general",
        choices=["general", "pricing", "reviews", "jobs"],
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        result = run_pipeline(
            competitor_id=args.competitor_id,
            signal_type=args.signal_type,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(error),
                },
                indent=2,
            )
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()