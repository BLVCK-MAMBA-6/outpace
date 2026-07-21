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
# JOB-POSTING DIFFING
# ============================================================

def job_map(
    jobs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index jobs by their stable provider identifier."""
    indexed = {}

    for job in jobs:
        job_id = str(
            job.get("id", "")
        ).strip()

        if not job_id:
            raise ValueError(
                "Every job must have a stable id"
            )

        if job_id in indexed:
            raise ValueError(
                f"Duplicate job identifier found: {job_id}"
            )

        indexed[job_id] = job

    return indexed


def comparable_job(
    job: dict[str, Any],
) -> dict[str, Any]:
    """Remove ingestion-only fields before comparison."""
    ignored_fields = {
        "fetched_at",
        "scraped_at",
        "captured_at",
        "ingested_at",
    }

    return {
        key: value
        for key, value in job.items()
        if key not in ignored_fields
    }


def changed_job_fields(
    old_job: dict[str, Any],
    new_job: dict[str, Any],
) -> list[str]:
    """Return fields changed on an existing job."""
    old_comparable = comparable_job(old_job)
    new_comparable = comparable_job(new_job)

    all_fields = (
        set(old_comparable)
        | set(new_comparable)
    )

    return sorted(
        field
        for field in all_fields
        if old_comparable.get(field)
        != new_comparable.get(field)
    )


def job_field_counts(
    jobs: list[dict[str, Any]],
    field: str,
) -> dict[str, int]:
    """Count non-empty department or location values."""
    counts: dict[str, int] = {}

    for job in jobs:
        value = str(
            job.get(field, "")
        ).strip()

        if not value:
            continue

        counts[value] = counts.get(value, 0) + 1

    return dict(
        sorted(
            counts.items(),
            key=lambda item: item[0].casefold(),
        )
    )


def is_remote_job(
    job: dict[str, Any],
) -> bool:
    """Identify a remote job from normalized fields."""
    workplace_type = str(
        job.get("workplace_type", "")
    ).casefold()

    location = str(
        job.get("location", "")
    ).casefold()

    return (
        workplace_type == "remote"
        or "remote" in location
    )


def compare_job_snapshots(
    old_content: dict[str, Any],
    new_content: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare structured job snapshots.

    Detects:

    - Newly opened jobs
    - Removed or closed jobs
    - Updated job fields
    - New remote jobs
    - Department and location changes
    """
    old_jobs = old_content.get("jobs") or []
    new_jobs = new_content.get("jobs") or []

    if not isinstance(old_jobs, list):
        raise ValueError(
            "Old job snapshot raw_content.jobs "
            "must be a list"
        )

    if not isinstance(new_jobs, list):
        raise ValueError(
            "New job snapshot raw_content.jobs "
            "must be a list"
        )

    old_map = job_map(old_jobs)
    new_map = job_map(new_jobs)

    old_ids = set(old_map)
    new_ids = set(new_map)

    added_ids = sorted(
        new_ids - old_ids
    )

    removed_ids = sorted(
        old_ids - new_ids
    )

    shared_ids = sorted(
        old_ids & new_ids
    )

    jobs_added = [
        new_map[job_id]
        for job_id in added_ids
    ]

    jobs_removed = [
        old_map[job_id]
        for job_id in removed_ids
    ]

    jobs_updated = []
    changes = []

    for job in jobs_added:
        changes.append(
            {
                "type": "job_added",
                "job_id": job["id"],
                "job": job,
            }
        )

    for job in jobs_removed:
        changes.append(
            {
                "type": "job_removed",
                "job_id": job["id"],
                "job": job,
            }
        )

    for job_id in shared_ids:
        old_job = old_map[job_id]
        new_job = new_map[job_id]

        changed_fields = changed_job_fields(
            old_job=old_job,
            new_job=new_job,
        )

        if not changed_fields:
            continue

        update = {
            "job_id": job_id,
            "changed_fields": changed_fields,
            "old": old_job,
            "new": new_job,
        }

        jobs_updated.append(update)

        changes.append(
            {
                "type": "job_updated",
                **update,
            }
        )

    new_remote_jobs = [
        job
        for job in jobs_added
        if is_remote_job(job)
    ]

    old_department_counts = job_field_counts(
        old_jobs,
        "department",
    )

    new_department_counts = job_field_counts(
        new_jobs,
        "department",
    )

    old_location_counts = job_field_counts(
        old_jobs,
        "location",
    )

    new_location_counts = job_field_counts(
        new_jobs,
        "location",
    )

    return {
        "has_changes": bool(changes),
        "old_job_count": len(old_jobs),
        "new_job_count": len(new_jobs),
        "job_count_delta": (
            len(new_jobs) - len(old_jobs)
        ),
        "jobs_added": jobs_added,
        "jobs_removed": jobs_removed,
        "jobs_updated": jobs_updated,
        "new_remote_jobs": new_remote_jobs,
        "new_remote_job_count": len(
            new_remote_jobs
        ),
        "old_department_counts": (
            old_department_counts
        ),
        "new_department_counts": (
            new_department_counts
        ),
        "old_location_counts": (
            old_location_counts
        ),
        "new_location_counts": (
            new_location_counts
        ),
        "change_count": len(changes),
        "test_fixture": bool(
            old_content.get("test_fixture")
            or new_content.get("test_fixture")
        ),
        "changes": changes,
    }



# ============================================================
# NEWS AND PRESS DIFFING
# ============================================================

def news_article_map(
    articles: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index normalized news articles by stable article ID."""
    article_map: dict[str, dict[str, Any]] = {}

    for article in articles:
        if not isinstance(article, dict):
            raise ValueError(
                "Every news article must be an object"
            )

        article_id = str(
            article.get("id", "")
        ).strip()

        if not article_id:
            raise ValueError(
                "Every news article must have an id"
            )

        if article_id in article_map:
            raise ValueError(
                f"Duplicate news article id: {article_id}"
            )

        article_map[article_id] = article

    return article_map


def comparable_news_article(
    article: dict[str, Any],
) -> dict[str, Any]:
    """
    Return article fields that represent meaningful content.

    matched_keywords is compared separately because keyword
    configuration can change without the article changing.
    """
    comparable_fields = (
        "title",
        "summary",
        "author",
        "section",
        "published_at",
        "modified_at",
    )

    return {
        field: article.get(field)
        for field in comparable_fields
    }


def changed_news_article_fields(
    old_article: dict[str, Any],
    new_article: dict[str, Any],
) -> list[str]:
    """Return meaningful fields changed on an existing article."""
    old_comparable = comparable_news_article(old_article)
    new_comparable = comparable_news_article(new_article)

    return [
        field
        for field in old_comparable
        if old_comparable.get(field)
        != new_comparable.get(field)
    ]


def article_keyword_set(
    article: dict[str, Any],
) -> set[str]:
    """Return normalized configured keyword matches."""
    keywords = article.get("matched_keywords") or []

    if not isinstance(keywords, list):
        return set()

    return {
        str(keyword).strip()
        for keyword in keywords
        if str(keyword).strip()
    }


def compare_news_snapshots(
    old_content: dict[str, Any],
    new_content: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare structured news and press snapshots.

    Articles disappearing from a listing are recorded, but do not
    trigger a brief by themselves. Blog index pages often use rolling
    windows, so disappearance does not prove an article was deleted.
    """
    old_articles = old_content.get("articles") or []
    new_articles = new_content.get("articles") or []

    if not isinstance(old_articles, list):
        raise ValueError(
            "Old news snapshot raw_content.articles must be a list"
        )

    if not isinstance(new_articles, list):
        raise ValueError(
            "New news snapshot raw_content.articles must be a list"
        )

    old_map = news_article_map(old_articles)
    new_map = news_article_map(new_articles)

    old_ids = set(old_map)
    new_ids = set(new_map)

    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    shared_ids = sorted(old_ids & new_ids)

    articles_added = [
        new_map[article_id]
        for article_id in added_ids
    ]

    articles_removed_from_listing = [
        old_map[article_id]
        for article_id in removed_ids
    ]

    articles_updated = []
    new_keyword_matches = []
    changes = []

    for article in articles_added:
        changes.append(
            {
                "type": "article_added",
                "article_id": article["id"],
                "article": article,
            }
        )

        matched_keywords = sorted(
            article_keyword_set(article),
            key=str.casefold,
        )

        if matched_keywords:
            new_keyword_matches.append(
                {
                    "article_id": article["id"],
                    "newly_matched_keywords": matched_keywords,
                    "article": article,
                }
            )

    for article in articles_removed_from_listing:
        changes.append(
            {
                "type": "article_removed_from_listing",
                "article_id": article["id"],
                "article": article,
                "meaningful": False,
            }
        )

    for article_id in shared_ids:
        old_article = old_map[article_id]
        new_article = new_map[article_id]

        changed_fields = changed_news_article_fields(
            old_article=old_article,
            new_article=new_article,
        )

        if changed_fields:
            update = {
                "article_id": article_id,
                "changed_fields": changed_fields,
                "old": old_article,
                "new": new_article,
            }

            articles_updated.append(update)

            changes.append(
                {
                    "type": "article_updated",
                    **update,
                }
            )

        newly_matched_keywords = sorted(
            article_keyword_set(new_article)
            - article_keyword_set(old_article),
            key=str.casefold,
        )

        if newly_matched_keywords:
            new_keyword_matches.append(
                {
                    "article_id": article_id,
                    "newly_matched_keywords": newly_matched_keywords,
                    "article": new_article,
                }
            )

    old_keyword_match_count = sum(
        bool(article_keyword_set(article))
        for article in old_articles
    )

    new_keyword_match_count = sum(
        bool(article_keyword_set(article))
        for article in new_articles
    )

    meaningful_change_count = (
        len(articles_added)
        + len(articles_updated)
    )

    return {
        "has_changes": meaningful_change_count > 0,
        "old_article_count": len(old_articles),
        "new_article_count": len(new_articles),
        "article_count_delta": (
            len(new_articles) - len(old_articles)
        ),
        "articles_added": articles_added,
        "articles_updated": articles_updated,
        "articles_removed_from_listing": (
            articles_removed_from_listing
        ),
        "listing_removal_count": len(
            articles_removed_from_listing
        ),
        "old_keyword_match_count": old_keyword_match_count,
        "new_keyword_match_count": new_keyword_match_count,
        "keyword_match_count_delta": (
            new_keyword_match_count
            - old_keyword_match_count
        ),
        "new_keyword_matches": new_keyword_matches,
        "new_keyword_match_event_count": len(
            new_keyword_matches
        ),
        "meaningful_change_count": meaningful_change_count,
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
        if (
            "reviews" not in old_content
            or "reviews" not in new_content
        ):
            raise ValueError(
                "One or both review snapshots do not contain "
                "raw_content.reviews"
            )

        diff = compare_review_snapshots(
            old_content=old_content,
            new_content=new_content,
        )

    elif signal_type == "jobs":
        if (
            "jobs" not in old_content
            or "jobs" not in new_content
        ):
            raise ValueError(
                "One or both job snapshots do not contain "
                "raw_content.jobs"
            )

        diff = compare_job_snapshots(
            old_content=old_content,
            new_content=new_content,
        )

    elif signal_type == "news":
        if (
            "articles" not in old_content
            or "articles" not in new_content
        ):
            raise ValueError(
                "One or both news snapshots do not contain "
                "raw_content.articles"
            )

        diff = compare_news_snapshots(
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
            "news",
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