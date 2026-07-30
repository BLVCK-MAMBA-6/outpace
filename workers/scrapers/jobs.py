"""
Structured job-posting snapshot collector.

Supported providers:

- github: Public GitHub careers repository
- html: Public server-rendered careers page
- ashby: Public Ashby job board API
- greenhouse: Public Greenhouse Job Board API
- lever: Public Lever Postings API
- deel: Public Deel-hosted job board JSON-LD
- manual: Clearly labelled synthetic fixture data

Run:

    python -m workers.scrapers.jobs --source-id <UUID>
"""

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse
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


def clean_provider_html(value: Any) -> str:
    """Convert bounded provider HTML or text into normalized text."""
    text = BeautifulSoup(
        str(value or ""),
        "html.parser",
    ).get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:8_000]


def canonical_html_job_url(value: str) -> str:
    """Preserve query-based job URLs; normalize path URLs with a slash."""
    parsed = urlparse(value)
    if parsed.query:
        return value
    return value.rstrip("/") + "/"


def greenhouse_metadata_value(
    job: dict[str, Any],
    *names: str,
) -> str:
    """Read a named Greenhouse metadata value when it is public."""
    expected = {name.casefold() for name in names}

    for item in job.get("metadata") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().casefold()
        if name not in expected:
            continue
        value = item.get("value")
        if isinstance(value, list):
            return ", ".join(
                str(entry).strip()
                for entry in value
                if str(entry).strip()
            )
        return str(value or "").strip()

    return ""


def parse_greenhouse_jobs(
    payload: dict[str, Any],
    board_token: str,
) -> list[dict[str, Any]]:
    """Normalize Greenhouse's public published-job response."""
    raw_jobs = payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError(
            "Greenhouse response does not contain a jobs list"
        )

    jobs = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue

        job_id = str(raw_job.get("id") or "").strip()
        title = str(raw_job.get("title") or "").strip()
        if not job_id or not title:
            continue

        location_data = raw_job.get("location") or {}
        location = (
            str(location_data.get("name") or "").strip()
            if isinstance(location_data, dict)
            else str(location_data).strip()
        )
        departments = raw_job.get("departments") or []
        department = ""
        if departments and isinstance(departments[0], dict):
            department = str(
                departments[0].get("name") or ""
            ).strip()

        jobs.append(
            {
                "id": f"greenhouse:{job_id}",
                "title": title,
                "department": department,
                "location": location,
                "employment_type": greenhouse_metadata_value(
                    raw_job,
                    "employment type",
                    "employment_type",
                    "commitment",
                ),
                "workplace_type": infer_workplace_type(
                    f"{title} {location}"
                ),
                "url": str(
                    raw_job.get("absolute_url")
                    or (
                        "https://boards.greenhouse.io/"
                        f"{board_token}/jobs/{job_id}"
                    )
                ).strip(),
                "description": clean_provider_html(
                    raw_job.get("content")
                ),
                "published_at": None,
            }
        )

    return jobs


def fetch_greenhouse_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch published jobs from Greenhouse's public board API."""
    metadata = source.get("metadata") or {}
    board_token = str(
        source.get("external_source_id")
        or metadata.get("board_token")
        or ""
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", board_token):
        raise ValueError(
            "Greenhouse source requires a valid board token"
        )

    endpoint = (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{quote(board_token, safe='')}/jobs?content=true"
    )
    response = httpx.get(
        endpoint,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": "Outpace-Competitive-Monitor/1.0",
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise ValueError(
            "Greenhouse response was not valid JSON"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError(
            "Greenhouse response must be a JSON object"
        )

    return {
        "company_name": metadata.get("company_name"),
        "provider_metadata": {
            "board_token": board_token,
            "endpoint": endpoint,
        },
        "jobs": parse_greenhouse_jobs(payload, board_token),
        "test_fixture": False,
    }


def lever_timestamp(value: Any) -> str | None:
    """Convert an optional Lever millisecond timestamp to ISO-8601."""
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(
            value / 1_000,
            tz=timezone.utc,
        ).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def parse_lever_jobs(
    payload: list[Any],
    site_name: str,
) -> list[dict[str, Any]]:
    """Normalize Lever's public published-postings response."""
    jobs = []
    for raw_job in payload:
        if not isinstance(raw_job, dict):
            continue

        job_id = str(raw_job.get("id") or "").strip()
        title = str(raw_job.get("text") or "").strip()
        if not job_id or not title:
            continue

        categories = raw_job.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        location = str(
            categories.get("location") or ""
        ).strip()
        workplace_value = str(
            raw_job.get("workplaceType") or ""
        ).strip().casefold()
        workplace_map = {
            "remote": "remote",
            "hybrid": "hybrid",
            "on-site": "onsite",
            "onsite": "onsite",
        }

        jobs.append(
            {
                "id": f"lever:{job_id}",
                "title": title,
                "department": str(
                    categories.get("department")
                    or categories.get("team")
                    or ""
                ).strip(),
                "location": location,
                "employment_type": str(
                    categories.get("commitment") or ""
                ).strip(),
                "workplace_type": workplace_map.get(
                    workplace_value,
                    infer_workplace_type(
                        f"{title} {location}"
                    ),
                ),
                "url": str(
                    raw_job.get("hostedUrl")
                    or f"https://jobs.lever.co/{site_name}/{job_id}"
                ).strip(),
                "description": clean_provider_html(
                    raw_job.get("descriptionPlain")
                    or raw_job.get("description")
                ),
                "published_at": lever_timestamp(
                    raw_job.get("createdAt")
                ),
            }
        )

    return jobs


def fetch_lever_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch published jobs from Lever's public postings API."""
    metadata = source.get("metadata") or {}
    site_name = str(
        source.get("external_source_id")
        or metadata.get("site_name")
        or ""
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", site_name):
        raise ValueError(
            "Lever source requires a valid site name"
        )

    region = str(metadata.get("region") or "global").casefold()
    api_host = (
        "api.eu.lever.co"
        if region == "eu"
        else "api.lever.co"
    )
    endpoint = (
        f"https://{api_host}/v0/postings/"
        f"{quote(site_name, safe='')}?mode=json"
    )
    response = httpx.get(
        endpoint,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": "Outpace-Competitive-Monitor/1.0",
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise ValueError(
            "Lever response was not valid JSON"
        ) from error
    if not isinstance(payload, list):
        raise ValueError(
            "Lever response must be a JSON list"
        )

    return {
        "company_name": metadata.get("company_name"),
        "provider_metadata": {
            "site_name": site_name,
            "region": region,
            "endpoint": endpoint,
        },
        "jobs": parse_lever_jobs(payload, site_name),
        "test_fixture": False,
    }


DEEL_JOB_ID_PATTERN = re.compile(
    r"/job-details/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

DEEL_RETRYABLE_STATUS_CODES = {
    403,
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}

DEEL_DETAIL_ATTEMPTS = 3
DEEL_DETAIL_WORKERS = 2
DEEL_BATCH_PAUSE_SECONDS = 0.75
DEEL_FINAL_RETRY_PAUSE_SECONDS = 5


def iter_json_ld_nodes(value: Any):
    """Yield nested JSON-LD objects without assuming one page shape."""
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, (dict, list)):
            yield from iter_json_ld_nodes(graph)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_ld_nodes(item)


def find_json_ld(
    html: str,
    type_name: str,
) -> dict[str, Any] | None:
    """Return the first JSON-LD object with the requested schema type."""
    soup = BeautifulSoup(html, "html.parser")
    expected = type_name.casefold()

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue

        for node in iter_json_ld_nodes(data):
            node_type = node.get("@type")
            values = (
                node_type
                if isinstance(node_type, list)
                else [node_type]
            )
            if any(
                str(value).casefold() == expected
                for value in values
            ):
                return node

    return None


def deel_listing_jobs(
    item_list: dict[str, Any],
) -> list[dict[str, str]]:
    """Read stable job UUIDs and detail URLs from a Deel ItemList."""
    elements = item_list.get("itemListElement")
    if not isinstance(elements, list):
        raise ValueError(
            "Deel board ItemList does not contain itemListElement"
        )

    jobs = []
    seen_ids = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        item = element.get("item")
        if not isinstance(item, dict):
            item = element

        detail_url = str(
            item.get("url")
            or element.get("url")
            or item.get("@id")
            or ""
        ).strip()
        match = DEEL_JOB_ID_PATTERN.search(detail_url)
        if not match:
            continue

        job_id = match.group(1).casefold()
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append(
            {
                "id": job_id,
                "url": detail_url,
                "title": str(
                    item.get("name")
                    or item.get("title")
                    or element.get("name")
                    or ""
                ).strip(),
            }
        )

    return jobs


def deel_listing_jobs_from_html(
    html: str,
    tenant: str,
) -> list[dict[str, str]]:
    """Read stable job UUIDs from Deel's embedded careers-page data."""
    jobs = []
    seen_ids = set()

    for match in DEEL_JOB_ID_PATTERN.finditer(html):
        job_id = match.group(1).casefold()
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append(
            {
                "id": job_id,
                "url": (
                    f"https://jobs.deel.com/{tenant}/job-details/"
                    f"{job_id}/overview"
                ),
                "title": "",
            }
        )

    return jobs


def deel_embedded_org_department(html: str) -> str:
    """Read Deel's Org Department value from embedded page data."""
    normalized = html.replace('\\"', '"')
    marker_pattern = re.compile(
        r'"name"\s*:\s*"Org Department"',
        re.IGNORECASE,
    )

    for marker in marker_pattern.finditer(normalized):
        prefix = normalized[
            max(0, marker.start() - 800):marker.start()
        ]
        names = re.findall(
            r'"name"\s*:\s*"([^"]+)"',
            prefix,
        )
        if names:
            department = re.sub(
                r"\\+u([0-9a-fA-F]{4})",
                lambda match: chr(
                    int(match.group(1), 16)
                ),
                names[-1],
            ).strip()
            if department.casefold() != "org department":
                return department

    return ""


def json_ld_location(value: Any) -> str:
    """Flatten Schema.org job locations into a stable display value."""
    values = value if isinstance(value, list) else [value]
    locations = []

    for item in values:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if not isinstance(address, dict):
            address = item
        parts = [
            str(address.get(field) or "").strip()
            for field in (
                "addressLocality",
                "addressRegion",
                "addressCountry",
            )
        ]
        location = ", ".join(
            part for part in parts if part
        )
        if not location:
            location = str(
                item.get("name") or address.get("name") or ""
            ).strip()
        if location and location not in locations:
            locations.append(location)

    return " · ".join(locations)


def parse_deel_job_posting(
    posting: dict[str, Any],
    job_id: str,
    detail_url: str,
    fallback_title: str = "",
) -> dict[str, Any]:
    """Normalize one Deel JobPosting JSON-LD object."""
    title = str(
        posting.get("title")
        or posting.get("name")
        or fallback_title
        or ""
    ).strip()
    if not title:
        raise ValueError(
            f"Deel job {job_id} is missing a title"
        )

    location = json_ld_location(
        posting.get("jobLocation")
    )
    applicant_location = json_ld_location(
        posting.get("applicantLocationRequirements")
    )
    if not location:
        location = applicant_location

    employment_type = posting.get("employmentType")
    if isinstance(employment_type, list):
        employment_type = ", ".join(
            str(value).strip()
            for value in employment_type
            if str(value).strip()
        )

    job_location_type = str(
        posting.get("jobLocationType") or ""
    ).strip().casefold()
    explicit_workplace_types = {
        "telecommute": "remote",
        "remote": "remote",
        "hybrid": "hybrid",
        "onsite": "onsite",
        "on-site": "onsite",
    }
    workplace_type = explicit_workplace_types.get(
        job_location_type,
        "",
    )
    if not workplace_type:
        inferred_workplace_type = infer_workplace_type(
            f"{title} {location} {applicant_location}"
        )
        # A geographic eligibility list does not prove that a Deel role
        # requires office attendance. Preserve unknown rather than
        # manufacturing an onsite classification.
        workplace_type = (
            inferred_workplace_type
            if inferred_workplace_type in {"remote", "hybrid"}
            else ""
        )

    occupational_category = posting.get(
        "occupationalCategory"
    )
    if isinstance(occupational_category, dict):
        occupational_category = (
            occupational_category.get("name")
            or occupational_category.get("codeValue")
            or ""
        )

    return {
        "id": f"deel:{job_id}",
        "title": title,
        "department": str(
            occupational_category
            or posting.get("department")
            or ""
        ).strip(),
        "location": location,
        "employment_type": str(
            employment_type or ""
        ).strip(),
        "workplace_type": workplace_type,
        "url": str(
            posting.get("url") or detail_url
        ).strip(),
        "description": clean_provider_html(
            posting.get("description")
        ),
        "published_at": (
            str(posting.get("datePosted")).strip()
            if posting.get("datePosted")
            else None
        ),
    }


def fetch_deel_job(
    listing: dict[str, str],
) -> dict[str, Any]:
    """Fetch one public Deel detail page and parse JobPosting JSON-LD."""
    last_error: Exception | None = None

    for attempt in range(DEEL_DETAIL_ATTEMPTS):
        try:
            response = httpx.get(
                listing["url"],
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Outpace-Competitive-Monitor/1.0"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Cache-Control": "no-cache",
                },
            )
        except httpx.TransportError as error:
            last_error = error
            if attempt < DEEL_DETAIL_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
            continue

        if response.status_code == 404:
            last_error = ValueError(
                f"Deel job {listing['id']} returned 404 while still "
                "present on the public board"
            )
        elif (
            response.status_code
            in DEEL_RETRYABLE_STATUS_CODES
        ):
            last_error = ValueError(
                f"Deel job {listing['id']} returned retryable "
                f"HTTP {response.status_code}"
            )
        else:
            try:
                response.raise_for_status()
            except httpx.HTTPError as error:
                last_error = error
            else:
                posting = find_json_ld(
                    response.text,
                    "JobPosting",
                )
                if posting:
                    if not (
                        posting.get("occupationalCategory")
                        or posting.get("department")
                    ):
                        posting = dict(posting)
                        posting["department"] = (
                            deel_embedded_org_department(
                                response.text
                            )
                        )
                    return parse_deel_job_posting(
                        posting=posting,
                        job_id=listing["id"],
                        detail_url=listing["url"],
                        fallback_title=listing["title"],
                    )

                # Deel occasionally returns a successful transitional
                # page before its JobPosting data is available. Treat
                # this as retryable rather than rejecting the entire
                # source after a single unstructured response.
                last_error = ValueError(
                    f"Deel job {listing['id']} did not expose "
                    "JobPosting JSON-LD"
                )

        if attempt < DEEL_DETAIL_ATTEMPTS - 1:
            time.sleep(2 ** attempt)

    raise ValueError(
        f"Deel job {listing['id']} could not be parsed after "
        f"{DEEL_DETAIL_ATTEMPTS} attempts: {last_error}"
    )


def fetch_deel_jobs(
    listings: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str], int]:
    """Fetch Deel details politely, then retry failures sequentially."""
    jobs = []
    failed_listings: list[
        tuple[dict[str, str], Exception]
    ] = []

    for offset in range(0, len(listings), DEEL_DETAIL_WORKERS):
        batch = listings[
            offset:offset + DEEL_DETAIL_WORKERS
        ]
        with ThreadPoolExecutor(
            max_workers=len(batch)
        ) as executor:
            futures = {
                executor.submit(
                    fetch_deel_job,
                    listing,
                ): listing
                for listing in batch
            }
            for future in as_completed(futures):
                listing = futures[future]
                try:
                    jobs.append(future.result())
                except (httpx.HTTPError, ValueError) as error:
                    failed_listings.append((listing, error))

        if offset + len(batch) < len(listings):
            time.sleep(DEEL_BATCH_PAUSE_SECONDS)

    retry_count = len(failed_listings)
    final_failures = []

    if failed_listings:
        time.sleep(DEEL_FINAL_RETRY_PAUSE_SECONDS)

    # Shared CI runner IPs are more likely to receive transient,
    # unstructured Deel pages. Retrying the small failed subset
    # sequentially avoids compounding provider pressure.
    for listing, initial_error in failed_listings:
        try:
            jobs.append(fetch_deel_job(listing))
        except (httpx.HTTPError, ValueError) as error:
            final_failures.append(
                f"{listing['id']}: {error} "
                f"(initial failure: {initial_error})"
            )

    return jobs, final_failures, retry_count


def fetch_deel_payload(
    source: dict[str, Any],
) -> dict[str, Any]:
    """Fetch a Deel-hosted board and its public JSON-LD job pages."""
    metadata = source.get("metadata") or {}
    tenant = str(
        source.get("external_source_id")
        or metadata.get("tenant")
        or ""
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tenant):
        raise ValueError(
            "Deel source requires a valid tenant identifier"
        )

    endpoint = f"https://jobs.deel.com/{quote(tenant, safe='')}"
    response = httpx.get(
        endpoint,
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": "Outpace-Competitive-Monitor/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    if re.search(
        r"<title>\s*Job Board Not Found\s*</title>",
        response.text,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            f"Deel board '{tenant}' does not exist"
        )

    item_list = find_json_ld(
        response.text,
        "ItemList",
    )
    if item_list:
        listings = deel_listing_jobs(item_list)
        listing_source = "item_list_json_ld"
    else:
        listings = deel_listing_jobs_from_html(
            response.text,
            tenant,
        )
        listing_source = "embedded_job_urls"

    if not listings:
        raise ValueError(
            "Deel board did not expose stable public job identifiers"
        )

    jobs, failures, retry_count = fetch_deel_jobs(
        listings
    )

    if failures:
        failure_preview = "; ".join(failures[:3])
        raise ValueError(
            "Deel detail crawl was incomplete; snapshot rejected "
            f"to prevent false removals ({len(failures)} failures): "
            f"{failure_preview}"
        )

    if listings and not jobs:
        raise ValueError(
            "Deel board listed jobs but none of its detail pages "
            "could be parsed"
        )

    jobs.sort(key=lambda job: job["id"])
    return {
        "company_name": metadata.get("company_name"),
        "provider_metadata": {
            "tenant": tenant,
            "endpoint": endpoint,
            "resolved_endpoint": str(response.url),
            "listing_source": listing_source,
            "listed_job_count": len(listings),
            "retried_detail_count": retry_count,
            "detail_failure_count": len(failures),
            "detail_failures": failures[:10],
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
                "url": canonical_html_job_url(normalized_url),
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

    if source["source"] == "greenhouse":
        return fetch_greenhouse_payload(source)

    if source["source"] == "lever":
        return fetch_lever_payload(source)

    if source["source"] == "deel":
        return fetch_deel_payload(source)

    if source["source"] == "manual":
        return load_manual_fixture(
            source.get("metadata") or {}
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
