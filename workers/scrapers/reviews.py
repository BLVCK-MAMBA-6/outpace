"""
Review snapshot collector.

The manual provider uses explicitly labelled fixture data while
official provider access is being arranged.

Run:

    python -m workers.scrapers.reviews --source-id <UUID>
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from api.utils.supabase_client import get_supabase_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (PROJECT_ROOT / "workers" / "fixtures").resolve()


def valid_uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid review-source UUID: {value}"
        ) from error


def normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a review from any provider."""
    review_id = str(review.get("id", "")).strip()

    if not review_id:
        raise ValueError("Every review must have an id")

    try:
        rating = float(review["rating"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Review {review_id} has an invalid rating"
        ) from error

    if not 1 <= rating <= 5:
        raise ValueError(
            f"Review {review_id} rating must be between 1 and 5"
        )

    published_at = str(review.get("published_at", "")).strip()

    if not published_at:
        raise ValueError(
            f"Review {review_id} is missing published_at"
        )

    return {
        "id": review_id,
        "rating": rating,
        "title": str(review.get("title", "")).strip(),
        "pros": str(review.get("pros", "")).strip(),
        "cons": str(review.get("cons", "")).strip(),
        "published_at": published_at,
    }


def load_manual_fixture(metadata: dict[str, Any]) -> dict[str, Any]:
    """Load review data from the permitted fixtures directory."""
    fixture_path_value = metadata.get("fixture_path")

    if not fixture_path_value:
        raise ValueError(
            "Manual review source requires metadata.fixture_path"
        )

    fixture_path = (PROJECT_ROOT / fixture_path_value).resolve()

    if fixture_path != FIXTURE_ROOT and FIXTURE_ROOT not in fixture_path.parents:
        raise ValueError(
            "Fixture path must be inside workers/fixtures"
        )

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Review fixture not found: {fixture_path}"
        )

    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)

    if not payload.get("test_fixture"):
        raise ValueError(
            "Manual development data must be labelled test_fixture=true"
        )

    return payload


def build_review_snapshot(
    source: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Convert provider data into Outpace's normalized review schema."""
    reviews = [
        normalize_review(review)
        for review in payload.get("reviews", [])
    ]

    if not reviews:
        raise ValueError("The review source returned no reviews")

    review_ids = [review["id"] for review in reviews]

    if len(review_ids) != len(set(review_ids)):
        raise ValueError("The review source contains duplicate review IDs")

    reviews.sort(
        key=lambda review: review["published_at"],
        reverse=True,
    )

    average_rating = round(
        sum(review["rating"] for review in reviews) / len(reviews),
        2,
    )

    normalized_content = {
        "source": source["source"],
        "external_product_id": source.get("external_product_id"),
        "source_url": source.get("source_url"),
        "product_name": payload.get("product_name"),
        "average_rating": average_rating,
        "review_count": len(reviews),
        "reviews": reviews,
        "test_fixture": bool(payload.get("test_fixture")),
    }

    content_hash = hashlib.sha256(
        json.dumps(
            normalized_content,
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    return {
        **normalized_content,
        "content_hash": content_hash,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_source_payload(source: dict[str, Any]) -> dict[str, Any]:
    """Fetch data from the configured review provider."""
    if source["source"] == "manual":
        return load_manual_fixture(source.get("metadata") or {})

    if source["source"] == "g2":
        raise RuntimeError(
            "G2 connector is configured, but this account currently "
            "has access to zero G2 products. Product data entitlement "
            "is required before G2 reviews can be collected."
        )

    raise ValueError(
        f"Unsupported review provider: {source['source']}"
    )


def collect_reviews(source_id: str) -> dict[str, Any]:
    """Collect and store a review snapshot."""
    supabase = get_supabase_client()

    source_result = (
        supabase.table("review_sources")
        .select("*")
        .eq("id", source_id)
        .eq("enabled", True)
        .limit(1)
        .execute()
    )

    if not source_result.data:
        raise ValueError(
            f"No enabled review source found with id: {source_id}"
        )

    source = source_result.data[0]
    payload = fetch_source_payload(source)
    raw_content = build_review_snapshot(source, payload)

    snapshot_result = (
        supabase.table("snapshots")
        .insert(
            {
                "competitor_id": source["competitor_id"],
                "signal_type": "reviews",
                "raw_content": raw_content,
            }
        )
        .execute()
    )

    if not snapshot_result.data:
        raise RuntimeError(
            "Supabase did not return the inserted review snapshot"
        )

    captured_at = raw_content["captured_at"]

    (
        supabase.table("review_sources")
        .update(
            {
                "last_polled_at": captured_at,
                "updated_at": captured_at,
            }
        )
        .eq("id", source_id)
        .execute()
    )

    snapshot = snapshot_result.data[0]

    print("Review snapshot stored successfully")
    print(f"Snapshot ID: {snapshot['id']}")
    print(f"Source: {raw_content['source']}")
    print(f"Test fixture: {raw_content['test_fixture']}")
    print(f"Reviews: {raw_content['review_count']}")
    print(f"Average rating: {raw_content['average_rating']}")

    return snapshot


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a normalized review snapshot"
    )

    parser.add_argument(
        "--source-id",
        required=True,
        type=valid_uuid,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        collect_reviews(args.source_id)
    except Exception as error:
        print(f"Review collection failed: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()