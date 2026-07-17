"""
Compare competitor snapshots for general, pricing, and review signals.

Examples:

    python -m workers.diffing \
        --competitor-id <UUID> \
        --signal-type general

    python -m workers.diffing \
        --competitor-id <UUID> \
        --signal-type pricing

    python -m workers.diffing \
        --competitor-id <UUID> \
        --signal-type reviews
"""

import argparse
import difflib
import json
import re
import unicodedata
from typing import Any
from uuid import UUID

from api.utils.supabase_client import get_supabase_client


# ============================================================
# CLI VALIDATION
# ============================================================

def valid_uuid(value: str) -> str:
    """Validate UUID arguments before querying Supabase."""
    try:
        return str(UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid competitor UUID: {value}"
        ) from error


# ============================================================
# GENERAL WEBSITE DIFFING
# ============================================================

def normalize_text(text: str) -> list[str]:
    """Normalize scraped website text into comparable lines."""
    text = unicodedata.normalize("NFKC", text)
    normalized_lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            normalized_lines.append(line)

    return normalized_lines


def compare_text(
    old_text: str,
    new_text: str,
) -> dict[str, Any]:
    """Return a structured line-by-line website comparison."""
    old_lines = normalize_text(old_text)
    new_lines = normalize_text(new_text)

    matcher = difflib.SequenceMatcher(
        None,
        old_lines,
        new_lines,
        autojunk=False,
    )

    changes = []
    added_lines = []
    removed_lines = []

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue

        removed = old_lines[old_start:old_end]
        added = new_lines[new_start:new_end]

        removed_lines.extend(removed)
        added_lines.extend(added)

        changes.append(
            {
                "type": tag,
                "old_start_line": old_start + 1,
                "old_end_line": old_end,
                "new_start_line": new_start + 1,
                "new_end_line": new_end,
                "removed": removed,
                "added": added,
            }
        )

    return {
        "has_changes": bool(changes),
        "similarity_ratio": round(matcher.ratio(), 4),
        "old_line_count": len(old_lines),
        "new_line_count": len(new_lines),
        "added_line_count": len(added_lines),
        "removed_line_count": len(removed_lines),
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "changes": changes,
    }


# ============================================================
# PRICING DIFFING
# ============================================================

def plan_map(
    plans: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index pricing plans by normalized plan name."""
    indexed = {}

    for plan in plans:
        name = str(plan.get("name", "")).strip()

        if name:
            indexed[name.casefold()] = plan

    return indexed


def normalized_feature_map(
    features: list[str],
) -> dict[str, str]:
    """Index features case-insensitively while preserving display text."""
    return {
        feature.strip().casefold(): feature.strip()
        for feature in features
        if feature and feature.strip()
    }


def compare_pricing_plans(
    old_plans: list[dict[str, Any]],
    new_plans: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare structured plans independently of webpage layout.

    Plan ordering and DOM redesigns do not count as pricing changes.
    """
    old_map = plan_map(old_plans)
    new_map = plan_map(new_plans)

    old_names = set(old_map)
    new_names = set(new_map)

    added_keys = sorted(new_names - old_names)
    removed_keys = sorted(old_names - new_names)
    shared_keys = sorted(old_names & new_names)

    plans_added = [
        new_map[key]
        for key in added_keys
    ]

    plans_removed = [
        old_map[key]
        for key in removed_keys
    ]

    price_changes = []
    description_changes = []
    feature_changes = []
    changes = []

    price_fields = [
        "amount",
        "currency",
        "price_display",
        "billing_period",
    ]

    for key in shared_keys:
        old_plan = old_map[key]
        new_plan = new_map[key]
        plan_name = new_plan.get("name") or old_plan.get("name")

        changed_price_fields = [
            field
            for field in price_fields
            if old_plan.get(field) != new_plan.get(field)
        ]

        if changed_price_fields:
            price_change = {
                "plan": plan_name,
                "changed_fields": changed_price_fields,
                "old": {
                    field: old_plan.get(field)
                    for field in price_fields
                },
                "new": {
                    field: new_plan.get(field)
                    for field in price_fields
                },
            }

            price_changes.append(price_change)

            changes.append(
                {
                    "type": "price_changed",
                    **price_change,
                }
            )

        old_description = old_plan.get("description")
        new_description = new_plan.get("description")

        if old_description != new_description:
            description_change = {
                "plan": plan_name,
                "old": old_description,
                "new": new_description,
            }

            description_changes.append(description_change)

            changes.append(
                {
                    "type": "description_changed",
                    **description_change,
                }
            )

        old_features = normalized_feature_map(
            old_plan.get("features") or []
        )

        new_features = normalized_feature_map(
            new_plan.get("features") or []
        )

        added_feature_keys = sorted(
            set(new_features) - set(old_features)
        )

        removed_feature_keys = sorted(
            set(old_features) - set(new_features)
        )

        if added_feature_keys or removed_feature_keys:
            feature_change = {
                "plan": plan_name,
                "added": [
                    new_features[item]
                    for item in added_feature_keys
                ],
                "removed": [
                    old_features[item]
                    for item in removed_feature_keys
                ],
            }

            feature_changes.append(feature_change)

            changes.append(
                {
                    "type": "features_changed",
                    **feature_change,
                }
            )

    for plan in plans_added:
        changes.append(
            {
                "type": "plan_added",
                "plan": plan,
            }
        )

    for plan in plans_removed:
        changes.append(
            {
                "type": "plan_removed",
                "plan": plan,
            }
        )

    return {
        "has_changes": bool(changes),
        "old_plan_count": len(old_plans),
        "new_plan_count": len(new_plans),
        "plans_added": plans_added,
        "plans_removed": plans_removed,
        "price_changes": price_changes,
        "description_changes": description_changes,
        "feature_changes": feature_changes,
        "change_count": len(changes),
        "changes": changes,
    }


# ============================================================
# REVIEW DIFFING
# ============================================================

def get_review_id(review: dict[str, Any]) -> str:
    """
    Return a review's stable external identifier.

    Supporting several names lets future G2 or Capterra providers use
    their native identifier without changing the diffing system.
    """
    possible_fields = [
        "external_id",
        "external_review_id",
        "review_id",
        "id",
    ]

    for field in possible_fields:
        value = review.get(field)

        if value is not None and str(value).strip():
            return str(value).strip()

    raise ValueError(
        "Review is missing a stable identifier. Expected one of: "
        "external_id, external_review_id, review_id, or id"
    )


def review_map(
    reviews: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index reviews by their stable external identifier."""
    indexed = {}

    for review in reviews:
        review_id = get_review_id(review)

        if review_id in indexed:
            raise ValueError(
                f"Duplicate review identifier found: {review_id}"
            )

        indexed[review_id] = review

    return indexed


def get_numeric_rating(review: dict[str, Any]) -> float:
    """Extract and validate a review rating."""
    rating = review.get("rating")

    if rating is None:
        raise ValueError(
            f"Review {get_review_id(review)} does not contain a rating"
        )

    try:
        numeric_rating = float(rating)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Review {get_review_id(review)} has an invalid rating: {rating}"
        ) from error

    if numeric_rating < 0 or numeric_rating > 5:
        raise ValueError(
            f"Review {get_review_id(review)} has a rating outside 0–5: "
            f"{numeric_rating}"
        )

    return numeric_rating


def rating_key(rating: float) -> str:
    """Convert a numeric rating into a clean JSON object key."""
    if rating.is_integer():
        return str(int(rating))

    return str(rating)


def rating_distribution(
    reviews: list[dict[str, Any]],
) -> dict[str, int]:
    """Count how many reviews exist for each exact rating."""
    counts: dict[float, int] = {}

    for review in reviews:
        rating = get_numeric_rating(review)
        counts[rating] = counts.get(rating, 0) + 1

    return {
        rating_key(rating): counts[rating]
        for rating in sorted(counts)
    }


def calculate_average_rating(
    reviews: list[dict[str, Any]],
) -> float | None:
    """Calculate the average rating directly from the stored reviews."""
    if not reviews:
        return None

    ratings = [
        get_numeric_rating(review)
        for review in reviews
    ]

    return round(sum(ratings) / len(ratings), 4)


def comparable_review(
    review: dict[str, Any],
) -> dict[str, Any]:
    """
    Remove ingestion-only fields before comparing a review.

    A new scrape timestamp should not make an unchanged review appear
    edited. All meaningful review fields remain in the comparison.
    """
    ignored_fields = {
        "fetched_at",
        "scraped_at",
        "ingested_at",
    }

    return {
        key: value
        for key, value in review.items()
        if key not in ignored_fields
    }


def changed_review_fields(
    old_review: dict[str, Any],
    new_review: dict[str, Any],
) -> list[str]:
    """Return the fields that changed in an existing review."""
    old_comparable = comparable_review(old_review)
    new_comparable = comparable_review(new_review)

    all_fields = set(old_comparable) | set(new_comparable)

    return sorted(
        field
        for field in all_fields
        if old_comparable.get(field) != new_comparable.get(field)
    )


def compare_review_snapshots(
    old_content: dict[str, Any],
    new_content: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare two structured review snapshots.

    Detects:

    - New reviews
    - Removed reviews
    - Updated reviews
    - Rating average shifts
    - Rating distribution shifts
    - Newly added negative reviews
    """
    old_reviews = old_content.get("reviews") or []
    new_reviews = new_content.get("reviews") or []

    if not isinstance(old_reviews, list):
        raise ValueError(
            "Old review snapshot raw_content.reviews must be a list"
        )

    if not isinstance(new_reviews, list):
        raise ValueError(
            "New review snapshot raw_content.reviews must be a list"
        )

    old_map = review_map(old_reviews)
    new_map = review_map(new_reviews)

    old_ids = set(old_map)
    new_ids = set(new_map)

    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    shared_ids = sorted(old_ids & new_ids)

    reviews_added = [
        new_map[review_id]
        for review_id in added_ids
    ]

    reviews_removed = [
        old_map[review_id]
        for review_id in removed_ids
    ]

    reviews_updated = []
    changes = []

    for review in reviews_added:
        changes.append(
            {
                "type": "review_added",
                "review_id": get_review_id(review),
                "review": review,
            }
        )

    for review in reviews_removed:
        changes.append(
            {
                "type": "review_removed",
                "review_id": get_review_id(review),
                "review": review,
            }
        )

    for review_id in shared_ids:
        old_review = old_map[review_id]
        new_review = new_map[review_id]

        changed_fields = changed_review_fields(
            old_review,
            new_review,
        )

        if not changed_fields:
            continue

        update = {
            "review_id": review_id,
            "changed_fields": changed_fields,
            "old": old_review,
            "new": new_review,
        }

        reviews_updated.append(update)

        changes.append(
            {
                "type": "review_updated",
                **update,
            }
        )

    old_average = calculate_average_rating(old_reviews)
    new_average = calculate_average_rating(new_reviews)

    if old_average is None or new_average is None:
        average_rating_delta = None
    else:
        average_rating_delta = round(
            new_average - old_average,
            4,
        )

    old_distribution = rating_distribution(old_reviews)
    new_distribution = rating_distribution(new_reviews)

    new_negative_reviews = [
        review
        for review in reviews_added
        if get_numeric_rating(review) <= 2
    ]

    rating_changed = (
        old_average != new_average
        or old_distribution != new_distribution
    )

    return {
        "has_changes": bool(changes),
        "old_review_count": len(old_reviews),
        "new_review_count": len(new_reviews),
        "review_count_delta": len(new_reviews) - len(old_reviews),
        "old_average_rating": old_average,
        "new_average_rating": new_average,
        "average_rating_delta": average_rating_delta,
        "rating_changed": rating_changed,
        "old_rating_distribution": old_distribution,
        "new_rating_distribution": new_distribution,
        "reviews_added": reviews_added,
        "reviews_removed": reviews_removed,
        "reviews_updated": reviews_updated,
        "new_negative_reviews": new_negative_reviews,
        "new_negative_review_count": len(new_negative_reviews),
        "change_count": len(changes),
        "test_fixture": bool(
            old_content.get("test_fixture")
            or new_content.get("test_fixture")
        ),
        "changes": changes,
    }


# ============================================================
# DATABASE SNAPSHOT RETRIEVAL
# ============================================================

def compare_latest_snapshots(
    competitor_id: str,
    signal_type: str = "general",
) -> dict[str, Any]:
    """Retrieve and compare the two latest matching snapshots."""
    supabase = get_supabase_client()

    result = (
        supabase.table("snapshots")
        .select(
            "id,competitor_id,signal_type,"
            "raw_content,scraped_at"
        )
        .eq("competitor_id", competitor_id)
        .eq("signal_type", signal_type)
        .order("scraped_at", desc=True)
        .limit(2)
        .execute()
    )

    snapshots = result.data or []

    if len(snapshots) < 2:
        return {
            "status": "insufficient_snapshots",
            "competitor_id": competitor_id,
            "signal_type": signal_type,
            "snapshot_count": len(snapshots),
            "message": (
                "At least two snapshots are required. "
                "Run the relevant scraper again."
            ),
        }

    new_snapshot = snapshots[0]
    old_snapshot = snapshots[1]

    old_content = old_snapshot.get("raw_content") or {}
    new_content = new_snapshot.get("raw_content") or {}

    if signal_type == "pricing":
        old_plans = old_content.get("plans") or []
        new_plans = new_content.get("plans") or []

        if not old_plans or not new_plans:
            raise ValueError(
                "One or both pricing snapshots do not contain plans"
            )

        diff = compare_pricing_plans(
            old_plans=old_plans,
            new_plans=new_plans,
        )

    elif signal_type == "reviews":
        if "reviews" not in old_content or "reviews" not in new_content:
            raise ValueError(
                "One or both review snapshots do not contain "
                "raw_content.reviews"
            )

        diff = compare_review_snapshots(
            old_content=old_content,
            new_content=new_content,
        )

    else:
        old_text = old_content.get("text", "")
        new_text = new_content.get("text", "")

        if not old_text or not new_text:
            raise ValueError(
                "One or both snapshots do not contain raw_content.text"
            )

        diff = compare_text(
            old_text=old_text,
            new_text=new_text,
        )

    return {
        "status": "compared",
        "competitor_id": competitor_id,
        "signal_type": signal_type,
        "old_snapshot_id": old_snapshot["id"],
        "new_snapshot_id": new_snapshot["id"],
        "old_scraped_at": old_snapshot["scraped_at"],
        "new_scraped_at": new_snapshot["scraped_at"],
        **diff,
    }


# ============================================================
# COMMAND-LINE ENTRY POINT
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare the latest competitor snapshots"
    )

    parser.add_argument(
        "--competitor-id",
        required=True,
        type=valid_uuid,
    )

    parser.add_argument(
        "--signal-type",
        default="general",
        choices=[
            "general",
            "pricing",
            "reviews",
            "jobs",
        ],
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        result = compare_latest_snapshots(
            competitor_id=args.competitor_id,
            signal_type=args.signal_type,
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(error),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()