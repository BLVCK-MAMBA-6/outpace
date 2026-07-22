"""
Structured job-posting snapshot collector.

Supported providers:

- github: Public GitHub careers repository
- html: Public server-rendered careers page
- ashby: Public Ashby job board API
- manual: Clearly labelled synthetic fixture data

Greenhouse and Lever are reserved for future provider adapters.

Run:

    python -m workers.scrapers.jobs --source-id <UUID>
"""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urljoin
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from api.utils.supabase_client import get_supabase_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    PROJECT_ROOT / "workers" / "fixtures"
).resolve()


# ============================================================
# VALIDATION
# ============================================================

def valid_uuid(value: str) -> str:
    """Validate a job-source UUID."""
    try:
        return str(UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid job-source UUID: {value}"
        ) from error


def normalize_job(
    job: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize a job from any provider."""
    job_id = str(job.get("id", "")).strip()
    title = str(job.get("title", "")).strip()

    if not job_id:
        raise ValueError(
            "Every job must have a stable id"
        )

    if not title:
        raise ValueError(
            f"Job {job_id} is missing a title"
        )

    return {
        "id": job_id,
        "title": title,
        "department": str(
            job.get("department", "")
        ).strip(),
        "location": str(
            job.get("location", "")
        ).strip(),
        "employment_type": str(
            job.get("employment_type", "")
        ).strip(),
        "workplace_type": str(
            job.get("workplace_type", "")
        ).strip(),
        "url": str(
            job.get("url", "")
        ).strip(),
        "description": str(
            job.get("description", "")
        ).strip(),
        "published_at": (
            str(job.get("published_at")).strip()
            if job.get("published_at")
            else None
        ),
    }


# ============================================================
# MARKDOWN PARSING
# ============================================================

def clean_markdown(value: str) -> str:
    """Remove basic Markdown formatting from display text."""
    value = value.strip()
    value = re.sub(
        r"[*_`]+",
        "",
        value,
    )
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def parse_markdown_link(
    value: str,
) -> tuple[str, str]:
    """Return the label and URL from a Markdown link."""
    value = value.strip()

    match = re.search(
        r"\[([^\]]+)\]\(([^)]+)\)",
        value,
    )

    if not match:
        return clean_markdown(value), ""

    label = clean_markdown(
        match.group(1)
    )
    href = match.group(2).strip()

    return label, href


def build_github_file_url(
    owner: str,
    repo: str,
    branch: str,
    href: str,
) -> str:
    """Convert a relative Markdown link into a GitHub URL."""
    if not href:
        return ""

    if href.startswith(
        (
            "https://",
            "http://",
        )
    ):
        return href

    clean_path = href.split("#", 1)[0]
    clean_path = clean_path.lstrip("./")
    clean_path = quote(
        unquote(clean_path),
        safe="/",
    )

    return (
        f"https://github.com/{owner}/{repo}/blob/"
        f"{branch}/{clean_path}"
    )


def extract_open_positions_section(
    readme: str,
) -> str:
    """Extract the Open Positions section from a Markdown file."""
    heading = re.search(
        r"(?im)^#{1,6}\s+open positions:?\s*$",
        readme,
    )

    if not heading:
        raise ValueError(
            "The GitHub careers README does not contain "
            "an Open Positions heading"
        )

    remaining = readme[heading.end():]

    next_heading = re.search(
        r"(?m)^#{1,6}\s+",
        remaining,
    )

    if next_heading:
        return remaining[:next_heading.start()]

    return remaining


def is_markdown_separator(
    cells: list[str],
) -> bool:
    """Return True for a Markdown table separator row."""
    if not cells:
        return False

    return all(
        bool(
            re.fullmatch(
                r":?-{2,}:?",
                cell.strip(),
            )
        )
        for cell in cells
    )


def stable_job_id(
    owner: str,
    repo: str,
    title: str,
    department: str,
    location: str,
    href: str,
) -> str:
    """Create a stable ID when the provider does not supply one."""
    identity = (
        href
        or "|".join(
            [
                title.casefold(),
                department.casefold(),
                location.casefold(),
            ]
        )
    )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:20]

    return (
        f"github:{owner.casefold()}/"
        f"{repo.casefold()}:{digest}"
    )


def infer_workplace_type(
    location: str,
) -> str:
    """Infer remote/hybrid/onsite from the displayed location."""
    normalized = location.casefold()

    if "hybrid" in normalized:
        return "hybrid"

    if "remote" in normalized:
        return "remote"

    if location:
        return "onsite"

    return ""


def parse_github_jobs(
    readme: str,
    owner: str,
    repo: str,
    branch: str,
) -> list[dict[str, Any]]:
    """Parse current jobs from a public GitHub careers README."""
    section = extract_open_positions_section(
        readme
    )

    jobs = []

    for line in section.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            continue

        cells = [
            cell.strip()
            for cell in stripped.strip("|").split("|")
        ]

        if len(cells) < 3:
            continue

        if is_markdown_separator(cells):
            continue

        location = clean_markdown(cells[0])
        department = clean_markdown(cells[1])
        title, href = parse_markdown_link(
            cells[2]
        )

        if title.casefold() in {
            "role",
            "title",
            "position",
        }:
            continue

        if title in {
            "",
            "-",
            "—",
        }:
            continue

        job_url = build_github_file_url(
            owner=owner,
            repo=repo,
            branch=branch,
            href=href,
        )

        jobs.append(
            {
                "id": stable_job_id(
                    owner=owner,
                    repo=repo,
                    title=title,
                    department=department,
                    location=location,
                    href=href,
                ),
                "title": title,
                "department": (
                    ""
                    if department in {"-", "—"}
                    else department
                ),
                "location": (
                    ""
                    if location in {"-", "—"}
                    else location
                ),
                "employment_type": "",
                "workplace_type": infer_workplace_type(
                    location
                ),
                "url": job_url,
                "description": "",
                "published_at": None,
            }
        )

    return jobs


# ============================================================
# PROVIDERS
# ============================================================

def fetch_github_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch jobs from a public GitHub careers repository."""
    metadata = source.get("metadata") or {}

    owner = str(
        metadata.get("owner", "")
    ).strip()

    repo = str(
        metadata.get("repo", "")
    ).strip()

    configured_branch = str(
        metadata.get("branch", "main")
    ).strip()

    readme_path = str(
        metadata.get("readme_path", "README.md")
    ).strip()

    if not owner or not repo:
        raise ValueError(
            "GitHub job source requires metadata.owner "
            "and metadata.repo"
        )

    branches = list(
        dict.fromkeys(
            [
                configured_branch,
                "main",
                "master",
            ]
        )
    )

    response = None
    selected_branch = None
    errors = []

    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Outpace-Competitive-Monitor/1.0"
            ),
            "Accept": "text/plain",
        },
    ) as client:
        for branch in branches:
            raw_url = (
                "https://raw.githubusercontent.com/"
                f"{owner}/{repo}/{branch}/{readme_path}"
            )

            current_response = client.get(raw_url)

            if current_response.status_code == 200:
                response = current_response
                selected_branch = branch
                break

            errors.append(
                {
                    "branch": branch,
                    "status_code": (
                        current_response.status_code
                    ),
                }
            )

    if response is None or selected_branch is None:
        raise RuntimeError(
            "Unable to fetch the GitHub careers README: "
            + json.dumps(errors)
        )

    jobs = parse_github_jobs(
        readme=response.text,
        owner=owner,
        repo=repo,
        branch=selected_branch,
    )

    return {
        "company_name": metadata.get(
            "company_name"
        ),
        "provider_metadata": {
            "owner": owner,
            "repo": repo,
            "branch": selected_branch,
            "readme_path": readme_path,
        },
        "jobs": jobs,
        "test_fixture": False,
    }


def clean_ashby_description(
    job: dict[str, Any],
) -> str:
    """Return bounded plain text from an Ashby job description."""
    description = str(
        job.get("descriptionPlain") or ""
    ).strip()

    if not description:
        description_html = str(
            job.get("descriptionHtml") or ""
        ).strip()

        if description_html:
            description = BeautifulSoup(
                description_html,
                "html.parser",
            ).get_text(" ", strip=True)

    description = re.sub(
        r"\s+",
        " ",
        description,
    ).strip()

    return description[:8_000]


def parse_ashby_jobs(
    payload: dict[str, Any],
    board_name: str,
) -> list[dict[str, Any]]:
    """Normalize the public Ashby job-board response."""
    raw_jobs = payload.get("jobs") or []

    if not isinstance(raw_jobs, list):
        raise ValueError(
            "Ashby job-board response does not contain a jobs list"
        )

    jobs = []

    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue

        ashby_id = str(
            raw_job.get("id") or ""
        ).strip()
        title = str(
            raw_job.get("title") or ""
        ).strip()

        if not ashby_id or not title:
            continue

        location = str(
            raw_job.get("location") or ""
        ).strip()
        workplace_value = str(
            raw_job.get("workplaceType") or ""
        ).strip().casefold()

        if "hybrid" in workplace_value:
            workplace_type = "hybrid"
        elif "remote" in workplace_value:
            workplace_type = "remote"
        elif workplace_value in {
            "onsite",
            "on-site",
            "on site",
        }:
            workplace_type = "onsite"
        elif raw_job.get("isRemote") is True:
            workplace_type = "remote"
        elif workplace_value or location:
            workplace_type = infer_workplace_type(
                location
            )
        else:
            workplace_type = ""

        job_url = str(
            raw_job.get("jobUrl")
            or raw_job.get("applyUrl")
            or (
                "https://jobs.ashbyhq.com/"
                f"{board_name}/{ashby_id}"
            )
        ).strip()

        jobs.append(
            {
                "id": f"ashby:{ashby_id}",
                "title": title,
                "department": str(
                    raw_job.get("department") or ""
                ).strip(),
                "location": location,
                "employment_type": str(
                    raw_job.get("employmentType") or ""
                ).strip(),
                "workplace_type": workplace_type,
                "url": job_url,
                "description": clean_ashby_description(
                    raw_job
                ),
                "published_at": (
                    str(raw_job.get("publishedAt")).strip()
                    if raw_job.get("publishedAt")
                    else None
                ),
            }
        )

    return jobs


def fetch_ashby_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch jobs from Ashby's public job-board API."""
    metadata = source.get("metadata") or {}
    board_name = str(
        source.get("external_source_id")
        or metadata.get("board_name")
        or ""
    ).strip()

    if not board_name:
        raise ValueError(
            "Ashby job source requires external_source_id "
            "or metadata.board_name"
        )

    if not re.fullmatch(r"[A-Za-z0-9_-]+", board_name):
        raise ValueError(
            "Ashby board name contains unsupported characters"
        )

    endpoint = (
        "https://api.ashbyhq.com/posting-api/job-board/"
        + quote(board_name, safe="")
    )

    response = httpx.get(
        endpoint,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Outpace-Competitive-Monitor/1.0"
            ),
            "Accept": "application/json",
        },
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as error:
        raise ValueError(
            "Ashby job-board response was not valid JSON"
        ) from error

    if not isinstance(payload, dict):
        raise ValueError(
            "Ashby job-board response must be a JSON object"
        )

    jobs = parse_ashby_jobs(
        payload=payload,
        board_name=board_name,
    )

    return {
        "company_name": metadata.get("company_name"),
        "provider_metadata": {
            "board_name": board_name,
            "api_version": payload.get("apiVersion"),
            "endpoint": endpoint,
        },
        "jobs": jobs,
        "test_fixture": False,
    }



def render_careers_page(
    source_url: str,
    link_path: str,
) -> str:
    """Render a client-side careers listing as a fallback."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        try:
            page = browser.new_page(
                user_agent=(
                    "Outpace-Competitive-Monitor/1.0"
                )
            )
            page.goto(
                source_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            try:
                page.wait_for_function(
                    """
                    path => Array.from(document.links).some(
                      link => link.href.includes(path)
                    )
                    """,
                    arg=link_path,
                    timeout=25_000,
                )
            except PlaywrightTimeoutError:
                page.wait_for_timeout(3_000)

            return page.content()
        finally:
            browser.close()


def extract_labeled_line(
    soup: BeautifulSoup,
    labels: set[str],
) -> str:
    """Extract the first text line following a known detail label."""
    lines = [
        line.strip()
        for line in soup.get_text(
            "\n",
            strip=True,
        ).splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines[:-1]):
        if line.casefold() in labels:
            return lines[index + 1]

    return ""


def fetch_html_job_detail(
    job_url: str,
) -> dict[str, Any]:
    """Read structured fields from a server-rendered job page."""
    response = httpx.get(
        job_url,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Outpace-Competitive-Monitor/1.0"
            ),
            "Accept": "text/html",
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )
    heading = soup.find("h1")
    title = (
        " ".join(heading.stripped_strings).strip()
        if heading
        else ""
    )
    location = extract_labeled_line(
        soup,
        {
            "location",
            "office location",
        },
    )
    department = extract_labeled_line(
        soup,
        {
            "department",
            "team",
        },
    )
    employment_type = extract_labeled_line(
        soup,
        {
            "employment type",
            "job type",
        },
    )
    description_tag = soup.find(
        "meta",
        attrs={"name": "description"},
    )

    return {
        "title": title,
        "location": location,
        "department": department,
        "employment_type": employment_type,
        "description": (
            str(description_tag.get("content", "")).strip()
            if description_tag
            else ""
        ),
    }


def parse_html_jobs(
    html: str,
    source_url: str,
    link_path: str,
    location_marker: str,
) -> list[dict[str, Any]]:
    """Parse stable job links from static or rendered HTML."""
    soup = BeautifulSoup(
        html,
        "html.parser",
    )
    jobs = []
    seen_urls = set()
    normalized_source_url = (
        source_url.split("#", 1)[0].rstrip("/")
    )

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        absolute_url = urljoin(
            source_url,
            anchor["href"],
        )
        normalized_url = (
            absolute_url.split("#", 1)[0].rstrip("/")
        )

        if normalized_url == normalized_source_url:
            continue

        if link_path not in normalized_url:
            continue

        if normalized_url in seen_urls:
            continue

        display_text = " ".join(
            anchor.stripped_strings
        ).strip()
        display_text = re.sub(
            r"^output-arrow\s*",
            "",
            display_text,
            flags=re.IGNORECASE,
        ).strip()

        if not display_text:
            continue

        if location_marker in display_text:
            title, location = display_text.rsplit(
                location_marker,
                1,
            )
        else:
            title = display_text
            location = ""

        title = title.strip()
        location = location.strip()
        department = ""
        employment_type = ""
        description = ""
        generic_title = title.casefold() in {
            "apply",
            "apply now",
            "learn more",
            "view job",
            "view role",
        }

        if generic_title or title.casefold().endswith(
            " apply"
        ):
            try:
                detail = fetch_html_job_detail(
                    normalized_url
                )
            except Exception:
                detail = {}

            title = str(
                detail.get("title") or title
            ).strip()
            location = str(
                detail.get("location") or location
            ).strip()
            department = str(
                detail.get("department") or ""
            ).strip()
            employment_type = str(
                detail.get("employment_type") or ""
            ).strip()
            description = str(
                detail.get("description") or ""
            ).strip()

        if not title or title.casefold() in {
            "apply",
            "apply now",
        }:
            continue

        if not department:
            previous_heading = anchor.find_previous(
                [
                    "h2",
                    "h3",
                ]
            )

            if previous_heading:
                department = " ".join(
                    previous_heading.stripped_strings
                ).strip()

                if department.casefold() in {
                    "open roles",
                    "current openings",
                    "careers",
                }:
                    department = ""

        digest = hashlib.sha256(
            normalized_url.encode("utf-8")
        ).hexdigest()[:20]

        jobs.append(
            {
                "id": f"html:{digest}",
                "title": title,
                "department": department,
                "location": location,
                "employment_type": employment_type,
                "workplace_type": (
                    infer_workplace_type(
                        location
                    )
                ),
                "url": normalized_url + "/",
                "description": description,
                "published_at": None,
            }
        )
        seen_urls.add(normalized_url)

    return jobs


def fetch_html_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch jobs from a public server-rendered careers page."""
    metadata = source.get("metadata") or {}
    source_url = str(
        source.get("source_url", "")
    ).strip()

    if not source_url:
        raise ValueError(
            "HTML job source requires source_url"
        )

    link_path = str(
        metadata.get(
            "job_link_path",
            "/careers/",
        )
    ).strip()

    location_marker = str(
        metadata.get(
            "location_marker",
            " location ",
        )
    )

    response = httpx.get(
        source_url,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Outpace-Competitive-Monitor/1.0"
            ),
            "Accept": "text/html",
        },
    )

    response.raise_for_status()

    jobs = parse_html_jobs(
        html=response.text,
        source_url=source_url,
        link_path=link_path,
        location_marker=location_marker,
    )
    rendered_fallback = False

    if not jobs:
        rendered_html = render_careers_page(
            source_url=source_url,
            link_path=link_path,
        )
        jobs = parse_html_jobs(
            html=rendered_html,
            source_url=source_url,
            link_path=link_path,
            location_marker=location_marker,
        )
        page_html = rendered_html
        rendered_fallback = True
    else:
        page_html = response.text

    if not jobs:
        no_openings_phrases = [
            "no current openings",
            "no open positions",
            "there are no open roles",
        ]

        page_text = BeautifulSoup(
            page_html,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        ).casefold()

        if not any(
            phrase in page_text
            for phrase in no_openings_phrases
        ):
            raise ValueError(
                "The HTML careers page returned no jobs "
                "and did not contain a recognized "
                "zero-openings message"
            )

    return {
        "company_name": metadata.get(
            "company_name"
        ),
        "provider_metadata": {
            "job_link_path": link_path,
            "location_marker": location_marker,
            "rendered_fallback": rendered_fallback,
        },
        "jobs": jobs,
        "test_fixture": False,
    }


def load_manual_fixture(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Load synthetic job data from the fixtures directory."""
    fixture_path_value = metadata.get(
        "fixture_path"
    )

    if not fixture_path_value:
        raise ValueError(
            "Manual job source requires "
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
            f"Job fixture not found: {fixture_path}"
        )

    with fixture_path.open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        payload = json.load(fixture_file)

    if not payload.get("test_fixture"):
        raise ValueError(
            "Manual development data must be labelled "
            "test_fixture=true"
        )

    return payload


def fetch_source_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch job data from the configured provider."""
    if source["source"] == "github":
        return fetch_github_payload(source)

    if source["source"] == "html":
        return fetch_html_payload(source)

    if source["source"] == "ashby":
        return fetch_ashby_payload(source)

    if source["source"] == "manual":
        return load_manual_fixture(
            source.get("metadata") or {}
        )

    if source["source"] in {
        "greenhouse",
        "lever",
    }:
        raise RuntimeError(
            f"The {source['source']} provider is reserved "
            "but has not been implemented yet"
        )

    raise ValueError(
        f"Unsupported job provider: {source['source']}"
    )


# ============================================================
# SNAPSHOT BUILDING
# ============================================================

def count_values(
    jobs: list[dict[str, Any]],
    field: str,
) -> dict[str, int]:
    """Count non-empty job values for a field."""
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


def build_job_snapshot(
    source: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Convert provider data into Outpace's job schema."""
    jobs = [
        normalize_job(job)
        for job in payload.get("jobs", [])
    ]

    job_ids = [
        job["id"]
        for job in jobs
    ]

    if len(job_ids) != len(set(job_ids)):
        raise ValueError(
            "The job source contains duplicate job IDs"
        )

    jobs.sort(
        key=lambda job: (
            job["title"].casefold(),
            job["id"],
        )
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
        "job_count": len(jobs),
        "remote_job_count": sum(
            1
            for job in jobs
            if job["workplace_type"] == "remote"
        ),
        "department_counts": count_values(
            jobs,
            "department",
        ),
        "location_counts": count_values(
            jobs,
            "location",
        ),
        "provider_metadata": payload.get(
            "provider_metadata",
            {},
        ),
        "jobs": jobs,
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

def collect_jobs(
    source_id: str,
) -> dict[str, Any]:
    """Collect and store one structured job snapshot."""
    supabase = get_supabase_client()

    source_result = (
        supabase.table("job_sources")
        .select("*")
        .eq("id", source_id)
        .eq("enabled", True)
        .limit(1)
        .execute()
    )

    if not source_result.data:
        raise ValueError(
            f"No enabled job source found with id: "
            f"{source_id}"
        )

    source = source_result.data[0]
    payload = fetch_source_payload(source)

    raw_content = build_job_snapshot(
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
                "signal_type": "jobs",
                "raw_content": raw_content,
            }
        )
        .execute()
    )

    if not snapshot_result.data:
        raise RuntimeError(
            "Supabase did not return the inserted "
            "job snapshot"
        )

    captured_at = raw_content["captured_at"]

    (
        supabase.table("job_sources")
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

    print("Job snapshot stored successfully")
    print(f"Snapshot ID: {snapshot['id']}")
    print(f"Source: {raw_content['source']}")
    print(
        f"Test fixture: "
        f"{raw_content['test_fixture']}"
    )
    print(f"Jobs: {raw_content['job_count']}")
    print(
        f"Remote jobs: "
        f"{raw_content['remote_job_count']}"
    )

    return snapshot


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a normalized job-posting snapshot"
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
        collect_jobs(args.source_id)
    except Exception as error:
        print(
            f"Job collection failed: {error}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
