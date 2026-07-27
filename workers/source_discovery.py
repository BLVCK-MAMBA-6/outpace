"""Discover a permitted public careers provider from one URL."""

from __future__ import annotations

import ipaddress
import html as html_module
import re
import socket
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx


USER_AGENT = "Outpace-Competitive-Monitor/1.0"
MAX_DISCOVERY_HTML_BYTES = 3_000_000
PROVIDER_ORDER = {
    "deel": 0,
    "ashby": 1,
    "greenhouse": 2,
    "lever": 3,
}


def _clean_identifier(value: str) -> str:
    cleaned = value.strip().strip("/")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
        return ""

    return cleaned


def _path_parts(url: str) -> list[str]:
    return [
        part
        for part in urlparse(url).path.strip("/").split("/")
        if part
    ]


def candidate_from_url(url: str) -> dict[str, Any] | None:
    """Recognize a directly supplied hosted job-board URL."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    parts = _path_parts(url)

    if host in {
        "jobs.deel.com",
        "www.jobs.deel.com",
    } and parts:
        identifier = _clean_identifier(parts[0])
        if identifier:
            return {
                "provider": "deel",
                "external_source_id": identifier,
                "region": None,
            }

    if host in {
        "jobs.ashbyhq.com",
        "www.jobs.ashbyhq.com",
    } and parts:
        identifier = _clean_identifier(parts[0])
        if identifier:
            return {
                "provider": "ashby",
                "external_source_id": identifier,
                "region": None,
            }

    if host == "api.ashbyhq.com" and len(parts) >= 3:
        if parts[:2] == ["posting-api", "job-board"]:
            identifier = _clean_identifier(parts[2])
            if identifier:
                return {
                    "provider": "ashby",
                    "external_source_id": identifier,
                    "region": None,
                }

    if host in {
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
    } and parts:
        query = parse_qs(parsed.query)
        identifier = _clean_identifier(
            (query.get("for") or [""])[0]
            if parts[0] == "embed"
            else parts[0]
        )
        if identifier:
            return {
                "provider": "greenhouse",
                "external_source_id": identifier,
                "region": None,
            }

    if host == "boards-api.greenhouse.io" and len(parts) >= 3:
        if parts[:2] == ["v1", "boards"]:
            identifier = _clean_identifier(parts[2])
            if identifier:
                return {
                    "provider": "greenhouse",
                    "external_source_id": identifier,
                    "region": None,
                }

    lever_hosts = {
        "jobs.lever.co": "global",
        "api.lever.co": "global",
        "jobs.eu.lever.co": "eu",
        "api.eu.lever.co": "eu",
    }
    if host in lever_hosts and parts:
        if host.startswith("api."):
            if len(parts) < 3 or parts[:2] != ["v0", "postings"]:
                return None
            identifier = _clean_identifier(parts[2])
        else:
            identifier = _clean_identifier(parts[0])

        if identifier:
            return {
                "provider": "lever",
                "external_source_id": identifier,
                "region": lever_hosts[host],
            }

    if host in {"github.com", "www.github.com"} and len(parts) >= 2:
        owner = _clean_identifier(parts[0])
        repo = _clean_identifier(parts[1].removesuffix(".git"))
        if owner and repo:
            return {
                "provider": "github",
                "external_source_id": f"{owner}/{repo}",
                "region": None,
                "candidate_url": url,
            }

    return None


def candidates_from_html(html: str) -> list[dict[str, Any]]:
    """Extract hosted job-board references from public page markup."""
    normalized_html = html_module.unescape(
        html.replace(r"\/", "/")
    )
    urls = re.findall(
        r"https?://[^\s\"'<>\\]+",
        normalized_html,
        flags=re.IGNORECASE,
    )
    candidates = []
    seen = set()

    for url in urls:
        candidate = candidate_from_url(url.rstrip(").,;"))
        if not candidate:
            continue

        key = (
            candidate["provider"],
            candidate["external_source_id"],
            candidate.get("region"),
        )
        if key in seen:
            continue

        seen.add(key)
        candidates.append(candidate)

    return candidates


def infer_html_job_link_path(html: str, page_url: str) -> str:
    """Infer a repeated same-site job-detail path when one is visible."""
    normalized_html = html_module.unescape(
        html.replace(r"\/", "/")
    )
    page_host = (urlparse(page_url).hostname or "").casefold()
    candidates: dict[str, int] = {}
    markers = (
        "/jobs/",
        "/job/",
        "/positions/",
        "/position/",
        "/roles/",
        "/role/",
    )

    for href in re.findall(
        r"href\s*=\s*[\"']([^\"']+)[\"']",
        normalized_html,
        flags=re.IGNORECASE,
    ):
        absolute_url = urljoin(page_url, href)
        parsed = urlparse(absolute_url)
        if (parsed.hostname or "").casefold() != page_host:
            continue

        path_with_slash = parsed.path.rstrip("/") + "/"
        for marker in markers:
            marker_index = path_with_slash.casefold().find(marker)
            if marker_index < 0:
                continue
            prefix = path_with_slash[
                : marker_index + len(marker) - 1
            ]
            candidates[prefix] = candidates.get(prefix, 0) + 1
            break

    if candidates:
        return sorted(
            candidates,
            key=lambda value: (-candidates[value], -len(value)),
        )[0]

    path = urlparse(page_url).path or "/careers/"
    if not path.endswith("/"):
        path += "/"
    return path


def candidate_slugs(
    company_name: str,
    source_url: str,
) -> list[str]:
    """Build conservative provider identifiers for verified probing."""
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").casefold()
    host_parts = [
        part
        for part in host.split(".")
        if part and part != "www"
    ]
    domain_stem = host_parts[0] if host_parts else ""
    ascii_name = unicodedata.normalize(
        "NFKD",
        company_name,
    ).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", ascii_name.casefold())
    values = [
        domain_stem,
        "-".join(words),
        "".join(words),
    ]
    slugs = []

    for value in values:
        cleaned = _clean_identifier(value)
        if cleaned and cleaned not in slugs:
            slugs.append(cleaned)

    return slugs[:3]


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Careers URL must use HTTP or HTTPS")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Careers URL must include a hostname")

    normalized_host = hostname.casefold()
    if normalized_host == "localhost" or normalized_host.endswith(
        (".local", ".internal")
    ):
        raise ValueError("Careers URL must resolve to a public host")

    try:
        addresses = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise ValueError("Careers URL hostname could not be resolved") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Careers URL must resolve to a public host")


def _fetch_public_html(url: str) -> tuple[str, str]:
    current_url = url

    with httpx.Client(
        timeout=15,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    ) as client:
        for _ in range(5):
            _assert_public_url(current_url)
            with client.stream(
                "GET",
                current_url,
                follow_redirects=False,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError(
                            "Careers page returned an invalid redirect"
                        )
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get(
                    "content-type",
                    "",
                ).casefold()
                if "html" not in content_type:
                    raise ValueError(
                        "Careers URL did not return an HTML page"
                    )

                raw = bytearray()
                for chunk in response.iter_bytes():
                    remaining = MAX_DISCOVERY_HTML_BYTES - len(raw)
                    if remaining <= 0:
                        break
                    raw.extend(chunk[:remaining])

                encoding = response.encoding or "utf-8"
                return bytes(raw).decode(
                    encoding,
                    errors="replace",
                ), str(response.url)

    raise ValueError("Careers page redirected too many times")


def _provider_endpoint(candidate: dict[str, Any]) -> str:
    identifier = quote(candidate["external_source_id"], safe="")
    provider = candidate["provider"]

    if provider == "deel":
        return f"https://jobs.deel.com/{identifier}"

    if provider == "ashby":
        return (
            "https://api.ashbyhq.com/posting-api/job-board/"
            + identifier
        )
    if provider == "greenhouse":
        return (
            "https://boards-api.greenhouse.io/v1/boards/"
            + identifier
            + "/jobs"
        )
    if provider == "lever":
        api_host = (
            "api.eu.lever.co"
            if candidate.get("region") == "eu"
            else "api.lever.co"
        )
        return f"https://{api_host}/v0/postings/{identifier}?mode=json"

    raise ValueError(f"Cannot probe provider: {provider}")


def probe_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    """Verify that a public provider endpoint returns a job collection."""
    if candidate["provider"] == "github":
        repository_url = str(candidate.get("candidate_url") or "")
        if not repository_url:
            return None
        try:
            response = httpx.get(
                repository_url,
                timeout=10,
                follow_redirects=True,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return {
            **candidate,
            "job_count": None,
            "endpoint": repository_url,
        }

    endpoint = _provider_endpoint(candidate)

    if candidate["provider"] == "deel":
        try:
            response = httpx.get(
                endpoint,
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        if re.search(
            r"<title>\s*Job Board Not Found\s*</title>",
            response.text,
            flags=re.IGNORECASE,
        ):
            return None

        normalized_html = html_module.unescape(
            response.text.replace(r"\/", "/")
        )
        job_ids = set(
            re.findall(
                r"/job-details/"
                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                r"[0-9a-f]{4}-[0-9a-f]{12})",
                normalized_html,
                flags=re.IGNORECASE,
            )
        )
        if "itemListElement" not in normalized_html:
            return None
        return {
            **candidate,
            "job_count": len(job_ids),
            "endpoint": endpoint,
        }

    try:
        response = httpx.get(
            endpoint,
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    if candidate["provider"] in {"ashby", "greenhouse"}:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("jobs"),
            list,
        ):
            return None
        job_count = len(payload["jobs"])
    else:
        if not isinstance(payload, list):
            return None
        job_count = len(payload)

    return {
        **candidate,
        "job_count": job_count,
        "endpoint": endpoint,
    }


def _probe_slug_candidates(slugs: list[str]) -> list[dict[str, Any]]:
    candidates = []
    for slug in slugs:
        candidates.append(
            {
                "provider": "deel",
                "external_source_id": slug,
                "region": None,
            }
        )
        for provider in ("ashby", "greenhouse"):
            candidates.append(
                {
                    "provider": provider,
                    "external_source_id": slug,
                    "region": None,
                }
            )

        for region in ("global", "eu"):
            candidates.append(
                {
                    "provider": "lever",
                    "external_source_id": slug,
                    "region": region,
                }
            )

    if not candidates:
        return []

    verified = []
    with ThreadPoolExecutor(max_workers=min(9, len(candidates))) as executor:
        futures = {
            executor.submit(probe_candidate, candidate): candidate
            for candidate in candidates
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                verified.append(result)

    verified.sort(
        key=lambda item: (
            -int(item.get("job_count") or 0),
            PROVIDER_ORDER[item["provider"]],
            0 if item.get("region") == "global" else 1,
        )
    )
    return verified


def _result(
    candidate: dict[str, Any],
    source_url: str,
    detected_by: str,
    confidence: str,
) -> dict[str, Any]:
    provider = candidate["provider"]
    labels = {
        "deel": "Deel",
        "ashby": "Ashby",
        "greenhouse": "Greenhouse",
        "lever": "Lever",
        "github": "GitHub",
        "html": "Official careers page",
    }
    count = candidate.get("job_count")
    count_text = (
        f" with {count} published role{'s' if count != 1 else ''}"
        if isinstance(count, int)
        else ""
    )

    return {
        "provider": provider,
        "source_url": source_url,
        "external_source_id": candidate.get("external_source_id"),
        "region": candidate.get("region"),
        "confidence": confidence,
        "detected_by": detected_by,
        "job_count": count,
        "requires_confirmation": True,
        "message": f"Detected {labels[provider]}{count_text}.",
        "metadata": candidate.get("metadata") or {},
    }


def _has_published_roles(candidate: dict[str, Any]) -> bool:
    """Require positive evidence for indirect provider discovery."""
    count = candidate.get("job_count")
    return isinstance(count, int) and count > 0


def discover_job_source(
    careers_url: str,
    company_name: str,
) -> dict[str, Any]:
    """Return one verified provider suggestion for user confirmation."""
    direct = candidate_from_url(careers_url)
    if direct:
        verified = probe_candidate(direct)
        if not verified:
            raise ValueError(
                "The hosted job board was recognized but its public "
                "job endpoint could not be verified"
            )
        return _result(
            verified,
            careers_url,
            detected_by="direct_url",
            confidence="high",
        )

    page_error: Exception | None = None
    html = ""
    final_url = careers_url
    try:
        html, final_url = _fetch_public_html(careers_url)
    except (httpx.HTTPError, ValueError) as error:
        page_error = error

    for candidate in candidates_from_html(html):
        verified = probe_candidate(candidate)
        if verified and _has_published_roles(verified):
            return _result(
                verified,
                careers_url,
                detected_by="embedded_reference",
                confidence="high",
            )

    verified_slugs = _probe_slug_candidates(
        candidate_slugs(company_name, final_url)
    )
    verified_with_roles = [
        candidate
        for candidate in verified_slugs
        if _has_published_roles(candidate)
    ]
    if verified_with_roles:
        return _result(
            verified_with_roles[0],
            careers_url,
            detected_by="verified_company_slug",
            confidence="medium",
        )

    if html:
        return _result(
            {
                "provider": "html",
                "external_source_id": None,
                "region": None,
                "job_count": None,
                "metadata": {
                    "job_link_path": infer_html_job_link_path(
                        html,
                        final_url,
                    ),
                },
            },
            careers_url,
            detected_by="public_html_fallback",
            confidence="low",
        )

    if page_error:
        raise ValueError(
            "No supported public careers source could be verified: "
            f"{page_error}"
        ) from page_error

    raise ValueError("No supported public careers source could be verified")
