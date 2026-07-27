"""Regression tests for structured Greenhouse and Lever jobs."""

import sys
import types
from unittest import TestCase
from unittest.mock import patch

import httpx

supabase_module = types.ModuleType("api.utils.supabase_client")
supabase_module.get_supabase_client = lambda: None
sys.modules.setdefault("api.utils.supabase_client", supabase_module)

from workers.scrapers.jobs import (  # noqa: E402
    canonical_html_job_url,
    deel_embedded_org_department,
    deel_listing_jobs,
    deel_listing_jobs_from_html,
    fetch_deel_job,
    find_json_ld,
    parse_deel_job_posting,
    parse_greenhouse_jobs,
    parse_lever_jobs,
)


class JobProviderParserTests(TestCase):
    def test_deel_parses_listing_and_job_posting_json_ld(self) -> None:
        job_id = "76d092b7-423d-4cfc-819a-02f5584348ea"
        detail_url = (
            "https://jobs.deel.com/deel/job-details/"
            f"{job_id}/overview"
        )
        board = find_json_ld(
            (
                '<script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"ItemList",'
                '"itemListElement":[{"@type":"ListItem","position":1,'
                f'"url":"{detail_url}"'
                "}]}</script>"
            ),
            "ItemList",
        )
        self.assertIsNotNone(board)
        assert board is not None

        listings = deel_listing_jobs(board)
        self.assertEqual(
            listings,
            [
                {
                    "id": job_id,
                    "url": detail_url,
                    "title": "",
                }
            ],
        )

        job = parse_deel_job_posting(
            {
                "@type": "JobPosting",
                "title": "Analytics Engineer",
                "description": "<p>Build trusted data products.</p>",
                "employmentType": "FULL_TIME",
                "datePosted": "2026-05-21",
                "jobLocation": [
                    {
                        "address": {
                            "addressLocality": "London",
                            "addressCountry": "GB",
                        }
                    }
                ],
                "occupationalCategory": "Data",
                "url": detail_url,
            },
            job_id=job_id,
            detail_url=detail_url,
        )

        self.assertEqual(job["id"], f"deel:{job_id}")
        self.assertEqual(job["title"], "Analytics Engineer")
        self.assertEqual(job["department"], "Data")
        self.assertEqual(job["location"], "London, GB")
        self.assertEqual(job["employment_type"], "FULL_TIME")
        self.assertEqual(job["workplace_type"], "")
        self.assertEqual(job["published_at"], "2026-05-21")
        self.assertEqual(
            job["description"],
            "Build trusted data products.",
        )

    def test_deel_discovers_embedded_job_urls_after_redirect(
        self,
    ) -> None:
        first_id = "b1bf0dc5-f27b-4d3d-a51c-883feffcf2d4"
        second_id = "88ecfd41-8126-4091-beab-5c5d10cb12f3"
        html = (
            "<html><body>"
            f'"/job-details/{first_id}/overview"'
            f'"/job-details/{first_id}/overview"'
            f'"/job-details/{second_id}/overview"'
            "</body></html>"
        )

        listings = deel_listing_jobs_from_html(html, "deel")

        self.assertEqual(
            listings,
            [
                {
                    "id": first_id,
                    "url": (
                        "https://jobs.deel.com/deel/job-details/"
                        f"{first_id}/overview"
                    ),
                    "title": "",
                },
                {
                    "id": second_id,
                    "url": (
                        "https://jobs.deel.com/deel/job-details/"
                        f"{second_id}/overview"
                    ),
                    "title": "",
                },
            ],
        )

    def test_deel_embedded_listing_rejects_missing_ids(self) -> None:
        self.assertEqual(
            deel_listing_jobs_from_html(
                "<html><body>No published roles</body></html>",
                "deel",
            ),
            [],
        )

    def test_deel_reads_embedded_org_department(self) -> None:
        html = (
            r'{\"jobTags\":[{\"tag\":{\"id\":\"tag-1\",'
            r'\"name\":\"Immigration \\u0026 Mobility\"}}],'
            r'\"jobDepartments\":'
            r'[{\"department\":{\"id\":\"department-1\",'
            r'\"name\":\"Org Department\"}}]}'
        )

        self.assertEqual(
            deel_embedded_org_department(html),
            "Immigration & Mobility",
        )

    def test_deel_honors_explicit_remote_workplace(self) -> None:
        job = parse_deel_job_posting(
            {
                "@type": "JobPosting",
                "title": "Customer Success Manager",
                "jobLocationType": "TELECOMMUTE",
                "jobLocation": {
                    "address": {
                        "addressCountry": "GB",
                    }
                },
            },
            job_id="remote-job",
            detail_url="https://example.com/remote-job",
        )

        self.assertEqual(job["workplace_type"], "remote")

    def test_deel_retries_transient_detail_failure(self) -> None:
        job_id = "b1bf0dc5-f27b-4d3d-a51c-883feffcf2d4"
        detail_url = (
            "https://jobs.deel.com/deel/job-details/"
            f"{job_id}/overview"
        )
        response = types.SimpleNamespace(
            status_code=200,
            text=(
                '<script type="application/ld+json">'
                '{"@type":"JobPosting","title":"Sales Manager",'
                '"employmentType":"FULL_TIME"}'
                "</script>"
            ),
            raise_for_status=lambda: None,
        )

        with (
            patch(
                "workers.scrapers.jobs.httpx.get",
                side_effect=[
                    httpx.ConnectError("temporary failure"),
                    response,
                ],
            ) as mocked_get,
            patch("workers.scrapers.jobs.time.sleep"),
        ):
            job = fetch_deel_job(
                {
                    "id": job_id,
                    "url": detail_url,
                    "title": "",
                }
            )

        self.assertEqual(mocked_get.call_count, 2)
        self.assertEqual(job["title"], "Sales Manager")

    def test_deel_rejects_listed_job_returning_404(self) -> None:
        response = types.SimpleNamespace(
            status_code=404,
            text="",
            raise_for_status=lambda: None,
        )

        with patch(
            "workers.scrapers.jobs.httpx.get",
            return_value=response,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "returned 404 while still present",
            ):
                fetch_deel_job(
                    {
                        "id": "missing-job",
                        "url": "https://example.com/missing-job",
                        "title": "",
                    }
                )

    def test_query_based_html_job_url_is_not_corrupted(self) -> None:
        self.assertEqual(
            canonical_html_job_url(
                "https://example.com/careers/job?ats_id=123"
            ),
            "https://example.com/careers/job?ats_id=123",
        )

    def test_greenhouse_normalizes_public_job(self) -> None:
        jobs = parse_greenhouse_jobs(
            {
                "jobs": [
                    {
                        "id": 42,
                        "title": "Staff Engineer",
                        "location": {"name": "Remote — US"},
                        "departments": [{"name": "Engineering"}],
                        "metadata": [
                            {
                                "name": "Employment Type",
                                "value": "Full-time",
                            }
                        ],
                        "absolute_url": (
                            "https://boards.greenhouse.io/acme/jobs/42"
                        ),
                        "content": "<p>Build reliable systems.</p>",
                    }
                ]
            },
            "acme",
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "greenhouse:42")
        self.assertEqual(jobs[0]["department"], "Engineering")
        self.assertEqual(jobs[0]["workplace_type"], "remote")
        self.assertEqual(jobs[0]["employment_type"], "Full-time")
        self.assertEqual(
            jobs[0]["description"],
            "Build reliable systems.",
        )

    def test_greenhouse_accepts_valid_zero_job_board(self) -> None:
        self.assertEqual(parse_greenhouse_jobs({"jobs": []}, "acme"), [])

    def test_lever_preserves_explicit_hybrid_workplace(self) -> None:
        jobs = parse_lever_jobs(
            [
                {
                    "id": "abc-123",
                    "text": "Account Executive",
                    "categories": {
                        "location": "London",
                        "team": "Sales",
                        "commitment": "Full-time",
                    },
                    "workplaceType": "hybrid",
                    "hostedUrl": (
                        "https://jobs.lever.co/acme/abc-123"
                    ),
                    "description": "<p>Grow the market.</p>",
                    "createdAt": 1_700_000_000_000,
                }
            ],
            "acme",
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "lever:abc-123")
        self.assertEqual(jobs[0]["department"], "Sales")
        self.assertEqual(jobs[0]["workplace_type"], "hybrid")
        self.assertEqual(jobs[0]["employment_type"], "Full-time")
        self.assertEqual(jobs[0]["description"], "Grow the market.")
        self.assertEqual(
            jobs[0]["published_at"],
            "2023-11-14T22:13:20+00:00",
        )
