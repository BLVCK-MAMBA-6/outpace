"""
Structured competitor news and press collector.

The HTML provider discovers official article URLs from a company blog or
newsroom, fetches each article, and extracts normalized metadata.

Run:

    python -m workers.scrapers.news --source-id <UUID>
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from api.utils.supabase_client import get_supabase_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT / "workers" / "fixtures"
).resolve()


# ============================================================
# VALIDATION
# ============================================================

def valid_uuid(value: str) -> str:
    """Validate a news-source UUID."""
    try:
        return str(UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid news-source UUID: {value}"
        ) from error


def normalize_article(
    article: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize one article."""
    article_id = str(
        article.get("id", "")
    ).strip()

    title = str(
        article.get("title", "")
    ).strip()

    url = str(
        article.get("url", "")
    ).strip()

    if not article_id:
        raise ValueError(
            "Every article must have a stable id"
        )

    if not title:
        raise ValueError(
            f"Article {article_id} is missing a title"
        )

    if not url:
        raise ValueError(
            f"Article {article_id} is missing a URL"
        )

    matched_keywords = article.get(
        "matched_keywords"
    ) or []

    if not isinstance(
        matched_keywords,
        list,
    ):
        raise ValueError(
            f"Article {article_id} matched_keywords "
            "must be a list"
        )

    return {
        "id": article_id,
        "title": title,
        "summary": str(
            article.get("summary", "")
        ).strip(),
        "url": url,
        "author": str(
            article.get("author", "")
        ).strip(),
        "section": str(
            article.get("section", "")
        ).strip(),
        "published_at": (
            str(
                article.get("published_at")
            ).strip()
            if article.get("published_at")
            else None
        ),
        "modified_at": (
            str(
                article.get("modified_at")
            ).strip()
            if article.get("modified_at")
            else None
        ),
        "matched_keywords": sorted(
            {
                str(keyword).strip()
                for keyword in matched_keywords
                if str(keyword).strip()
            },
            key=str.casefold,
        ),
    }


# ============================================================
# METADATA EXTRACTION
# ============================================================

def get_meta_content(
    soup: BeautifulSoup,
    *keys: str,
) -> str:
    """Return the first matching meta-tag value."""
    for key in keys:
        for attribute in (
            "property",
            "name",
        ):
            tag = soup.find(
                "meta",
                attrs={
                    attribute: key,
                },
            )

            if tag and tag.get("content"):
                return str(
                    tag["content"]
                ).strip()

    return ""


def find_json_value(
    node: Any,
    key: str,
) -> Any:
    """Recursively find a key inside JSON-LD data."""
    if isinstance(node, dict):
        if key in node:
            return node[key]

        for value in node.values():
            found = find_json_value(
                value,
                key,
            )

            if found is not None:
                return found

    elif isinstance(node, list):
        for item in node:
            found = find_json_value(
                item,
                key,
            )

            if found is not None:
                return found

    return None


def extract_json_ld(
    soup: BeautifulSoup,
) -> list[Any]:
    """Parse valid JSON-LD objects from a page."""
    objects = []

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json",
        },
    ):
        raw = script.string or script.get_text(
            strip=True
        )

        if not raw:
            continue

        try:
            objects.append(
                json.loads(raw)
            )
        except json.JSONDecodeError:
            continue

    return objects


def json_ld_value(
    objects: list[Any],
    key: str,
) -> Any:
    """Return a value from the first matching JSON-LD object."""
    for item in objects:
        value = find_json_value(
            item,
            key,
        )

        if value is not None:
            return value

    return None


def normalize_author(
    value: Any,
) -> str:
    """Convert JSON-LD author data into display text."""
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        return str(
            value.get("name", "")
        ).strip()

    if isinstance(value, list):
        authors = [
            normalize_author(item)
            for item in value
        ]

        return ", ".join(
            author
            for author in authors
            if author
        )

    return ""


def canonical_url(
    soup: BeautifulSoup,
    requested_url: str,
) -> str:
    """Return the article's canonical URL."""
    open_graph_url = get_meta_content(
        soup,
        "og:url",
    )

    if open_graph_url:
        return urljoin(
            requested_url,
            open_graph_url,
        ).split("#", 1)[0].rstrip("/")

    canonical = soup.find(
        "link",
        rel="canonical",
    )

    if canonical and canonical.get("href"):
        return urljoin(
            requested_url,
            canonical["href"],
        ).split("#", 1)[0].rstrip("/")

    return requested_url.split(
        "#",
        1,
    )[0].rstrip("/")


def match_keywords(
    article: dict[str, Any],
    keywords: list[str],
) -> list[str]:
    """Return configured keywords found in title or summary."""
    searchable = " ".join(
        [
            str(
                article.get("title", "")
            ),
            str(
                article.get("summary", "")
            ),
            str(
                article.get("section", "")
            ),
        ]
    ).casefold()

    return sorted(
        {
            keyword.strip()
            for keyword in keywords
            if keyword.strip()
            and keyword.strip().casefold()
            in searchable
        },
        key=str.casefold,
    )


def extract_article(
    requested_url: str,
    html: str,
    keywords: list[str],
) -> dict[str, Any]:
    """Extract normalized metadata from one article page."""
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    json_ld = extract_json_ld(
        soup
    )

    title = get_meta_content(
        soup,
        "og:title",
        "twitter:title",
    )

    if not title:
        heading = soup.find("h1")

        if heading:
            title = " ".join(
                heading.stripped_strings
            ).strip()

    summary = get_meta_content(
        soup,
        "og:description",
        "twitter:description",
        "description",
    )

    published_at = get_meta_content(
        soup,
        "article:published_time",
        "datePublished",
    )

    if not published_at:
        published_at = (
            json_ld_value(
                json_ld,
                "datePublished",
            )
            or ""
        )

    if not published_at:
        time_tag = soup.find(
            "time",
            datetime=True,
        )

        if time_tag:
            published_at = str(
                time_tag["datetime"]
            ).strip()

    modified_at = get_meta_content(
        soup,
        "article:modified_time",
        "dateModified",
    )

    if not modified_at:
        modified_at = (
            json_ld_value(
                json_ld,
                "dateModified",
            )
            or ""
        )

    author = get_meta_content(
        soup,
        "article:author",
        "author",
    )

    if not author:
        author = normalize_author(
            json_ld_value(
                json_ld,
                "author",
            )
        )

    section = get_meta_content(
        soup,
        "article:section",
    )

    if not section:
        section = str(
            json_ld_value(
                json_ld,
                "articleSection",
            )
            or ""
        ).strip()

    url = canonical_url(
        soup=soup,
        requested_url=requested_url,
    )

    digest = hashlib.sha256(
        url.casefold().encode("utf-8")
    ).hexdigest()[:24]

    article = {
        "id": f"html:{digest}",
        "title": title,
        "summary": summary,
        "url": url,
        "author": author,
        "section": section,
        "published_at": (
            str(published_at).strip()
            if published_at
            else None
        ),
        "modified_at": (
            str(modified_at).strip()
            if modified_at
            else None
        ),
    }

    article["matched_keywords"] = match_keywords(
        article=article,
        keywords=keywords,
    )

    return normalize_article(
        article
    )


# ============================================================
# PROVIDERS
# ============================================================

def discover_article_urls(
    source_url: str,
    html: str,
    article_link_path: str,
    max_articles: int,
) -> list[str]:
    """Discover stable article links from a listing page."""
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    discovered = []
    seen = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        absolute_url = urljoin(
            source_url,
            anchor["href"],
        )

        absolute_url = absolute_url.split(
            "#",
            1,
        )[0].rstrip("/")

        if article_link_path not in absolute_url:
            continue

        if absolute_url in seen:
            continue

        discovered.append(
            absolute_url
        )
        seen.add(
            absolute_url
        )

        if len(discovered) >= max_articles:
            break

    if not discovered:
        raise ValueError(
            "No article URLs were discovered from "
            "the HTML news source"
        )

    return discovered


def fetch_html_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch articles from an official HTML blog or newsroom."""
    metadata = source.get("metadata") or {}
    source_url = str(
        source.get("source_url", "")
    ).strip()

    article_link_path = str(
        metadata.get(
            "article_link_path",
            "/blog/post/",
        )
    ).strip()

    try:
        max_articles = int(
            metadata.get(
                "max_articles",
                25,
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "metadata.max_articles must be an integer"
        ) from error

    if max_articles < 1 or max_articles > 100:
        raise ValueError(
            "metadata.max_articles must be between 1 and 100"
        )

    keywords = source.get(
        "keywords"
    ) or []

    if not isinstance(keywords, list):
        raise ValueError(
            "news_sources.keywords must be a JSON array"
        )

    headers = {
        "User-Agent": (
            "Outpace-Competitive-Monitor/1.0"
        ),
        "Accept": "text/html",
    }

    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        listing_response = client.get(
            source_url
        )
        listing_response.raise_for_status()

        article_urls = discover_article_urls(
            source_url=source_url,
            html=listing_response.text,
            article_link_path=article_link_path,
            max_articles=max_articles,
        )

        articles = []

        for article_url in article_urls:
            response = client.get(
                article_url
            )
            response.raise_for_status()

            articles.append(
                extract_article(
                    requested_url=article_url,
                    html=response.text,
                    keywords=keywords,
                )
            )

    return {
        "company_name": metadata.get(
            "company_name"
        ),
        "provider_metadata": {
            "article_link_path": article_link_path,
            "max_articles": max_articles,
        },
        "articles": articles,
        "test_fixture": False,
    }


def load_manual_fixture(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Load synthetic news data from the fixture directory."""
    fixture_path_value = metadata.get(
        "fixture_path"
    )

    if not fixture_path_value:
        raise ValueError(
            "Manual news source requires "
            "metadata.fixture_path"
        )

    fixture_path = (
        PROJECT_ROOT / fixture_path_value
    ).resolve()

    if (
        fixture_path != FIXTURE_ROOT
        and FIXTURE_ROOT not in fixture_path.parents
    ):
        raise ValueError(
            "Fixture path must be inside workers/fixtures"
        )

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"News fixture not found: {fixture_path}"
        )

    with fixture_path.open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        payload = json.load(
            fixture_file
        )

    if not payload.get("test_fixture"):
        raise ValueError(
            "Manual news data must be labelled "
            "test_fixture=true"
        )

    return payload


def fetch_source_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch news from the configured provider."""
    if source["source"] == "html":
        return fetch_html_payload(
            source
        )

    if source["source"] == "manual":
        return load_manual_fixture(
            source.get("metadata") or {}
        )

    if source["source"] in {
        "rss",
        "atom",
        "sitemap",
    }:
        raise RuntimeError(
            f"The {source['source']} news provider "
            "is reserved but not implemented yet"
        )

    raise ValueError(
        f"Unsupported news provider: {source['source']}"
    )


# ============================================================
# SNAPSHOT BUILDING
# ============================================================

def build_news_snapshot(
    source: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build normalized news snapshot content."""
    articles = [
        normalize_article(article)
        for article in payload.get(
            "articles",
            [],
        )
    ]

    if not articles:
        raise ValueError(
            "The news source returned no articles"
        )

    article_ids = [
        article["id"]
        for article in articles
    ]

    if len(article_ids) != len(
        set(article_ids)
    ):
        raise ValueError(
            "The news source contains duplicate article IDs"
        )

    articles.sort(
        key=lambda article: (
            article.get("published_at") or "",
            article["url"],
        ),
        reverse=True,
    )

    normalized_content = {
        "source": source["source"],
        "external_source_id": source.get(
            "external_source_id"
        ),
        "source_url": source.get(
            "source_url"
        ),
        "company_name": payload.get(
            "company_name"
        ),
        "article_count": len(
            articles
        ),
        "keyword_match_count": sum(
            1
            for article in articles
            if article["matched_keywords"]
        ),
        "keywords": source.get(
            "keywords"
        ) or [],
        "provider_metadata": payload.get(
            "provider_metadata",
            {},
        ),
        "articles": articles,
        "test_fixture": bool(
            payload.get("test_fixture")
        ),
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
        "captured_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


# ============================================================
# COLLECTION
# ============================================================

def collect_news(
    source_id: str,
) -> dict[str, Any]:
    """Collect and store one news snapshot."""
    supabase = get_supabase_client()

    source_result = (
        supabase.table("news_sources")
        .select("*")
        .eq("id", source_id)
        .eq("enabled", True)
        .limit(1)
        .execute()
    )

    if not source_result.data:
        raise ValueError(
            f"No enabled news source found with id: "
            f"{source_id}"
        )

    source = source_result.data[0]

    payload = fetch_source_payload(
        source
    )

    raw_content = build_news_snapshot(
        source=source,
        payload=payload,
    )

    snapshot_result = (
        supabase.table("snapshots")
        .insert(
            {
                "competitor_id": (
                    source["competitor_id"]
                ),
                "signal_type": "news",
                "raw_content": raw_content,
            }
        )
        .execute()
    )

    if not snapshot_result.data:
        raise RuntimeError(
            "Supabase did not return the inserted "
            "news snapshot"
        )

    captured_at = raw_content[
        "captured_at"
    ]

    (
        supabase.table("news_sources")
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

    print("News snapshot stored successfully")
    print(f"Snapshot ID: {snapshot['id']}")
    print(f"Source: {raw_content['source']}")
    print(
        f"Test fixture: "
        f"{raw_content['test_fixture']}"
    )
    print(
        f"Articles: "
        f"{raw_content['article_count']}"
    )
    print(
        f"Keyword matches: "
        f"{raw_content['keyword_match_count']}"
    )

    return snapshot


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a normalized news snapshot"
        )
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
        collect_news(
            args.source_id
        )
    except Exception as error:
        print(
            f"News collection failed: {error}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()