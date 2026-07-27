"""Regression tests for safe public job-source discovery."""

from unittest import TestCase
from unittest.mock import patch

from workers.source_discovery import (
    candidate_from_url,
    candidate_slugs,
    candidates_from_html,
    discover_job_source,
    infer_html_job_link_path,
)


class JobSourceDiscoveryTests(TestCase):
    def test_recognizes_supported_hosted_urls(self) -> None:
        cases = {
            "https://jobs.deel.com/deel": (
                "deel",
                "deel",
                None,
            ),
            (
                "https://jobs.deel.com/deel/job-details/"
                "76d092b7-423d-4cfc-819a-02f5584348ea/overview"
            ): (
                "deel",
                "deel",
                None,
            ),
            "https://jobs.ashbyhq.com/acme": (
                "ashby",
                "acme",
                None,
            ),
            "https://boards.greenhouse.io/acme/jobs/123": (
                "greenhouse",
                "acme",
                None,
            ),
            (
                "https://boards.greenhouse.io/embed/"
                "job_board?for=acme"
            ): (
                "greenhouse",
                "acme",
                None,
            ),
            "https://jobs.lever.co/acme": (
                "lever",
                "acme",
                "global",
            ),
            "https://jobs.eu.lever.co/acme": (
                "lever",
                "acme",
                "eu",
            ),
        }

        for url, expected in cases.items():
            with self.subTest(url=url):
                candidate = candidate_from_url(url)
                self.assertIsNotNone(candidate)
                assert candidate is not None
                self.assertEqual(candidate["provider"], expected[0])
                self.assertEqual(
                    candidate["external_source_id"],
                    expected[1],
                )
                self.assertEqual(candidate.get("region"), expected[2])

    def test_extracts_embedded_provider_reference(self) -> None:
        html = (
            '<script src="https://jobs.ashbyhq.com/harvey"></script>'
            '<a href="https://jobs.ashbyhq.com/harvey">Jobs</a>'
        )

        candidates = candidates_from_html(html)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["provider"], "ashby")
        self.assertEqual(
            candidates[0]["external_source_id"],
            "harvey",
        )

    def test_extracts_json_escaped_provider_reference(self) -> None:
        candidates = candidates_from_html(
            r'{"board":"https:\/\/jobs.ashbyhq.com\/harvey"}'
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["provider"], "ashby")
        self.assertEqual(
            candidates[0]["external_source_id"],
            "harvey",
        )

    def test_builds_conservative_company_slugs(self) -> None:
        self.assertEqual(
            candidate_slugs(
                "Harvey AI",
                "https://www.harvey.ai/careers",
            ),
            ["harvey", "harvey-ai", "harveyai"],
        )

    def test_infers_query_based_job_detail_path(self) -> None:
        html = (
            '<a href="/careers/job?ats_id=one">First role</a>'
            '<a href="/careers/job?ats_id=two">Second role</a>'
        )

        self.assertEqual(
            infer_html_job_link_path(
                html,
                "https://www.deel.com/careers/",
            ),
            "/careers/job",
        )

    @patch("workers.source_discovery._probe_slug_candidates")
    @patch("workers.source_discovery._fetch_public_html")
    def test_company_slug_result_requires_confirmation(
        self,
        fetch_html,
        probe_slugs,
    ) -> None:
        fetch_html.return_value = (
            "<html><body>Careers</body></html>",
            "https://www.harvey.ai/careers",
        )
        probe_slugs.return_value = [
            {
                "provider": "ashby",
                "external_source_id": "harvey",
                "region": None,
                "job_count": 344,
            }
        ]

        result = discover_job_source(
            "https://www.harvey.ai/careers",
            "Harvey AI",
        )

        self.assertEqual(result["provider"], "ashby")
        self.assertEqual(result["job_count"], 344)
        self.assertEqual(result["confidence"], "medium")
        self.assertTrue(result["requires_confirmation"])

    @patch("workers.source_discovery._probe_slug_candidates")
    @patch("workers.source_discovery._fetch_public_html")
    def test_uses_html_only_after_provider_probes_fail(
        self,
        fetch_html,
        probe_slugs,
    ) -> None:
        fetch_html.return_value = (
            "<html><body><a href='/careers/role'>Role</a></body></html>",
            "https://example.com/careers/",
        )
        probe_slugs.return_value = []

        result = discover_job_source(
            "https://example.com/careers/",
            "Example",
        )

        self.assertEqual(result["provider"], "html")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(
            result["metadata"]["job_link_path"],
            "/careers/role",
        )
        self.assertTrue(result["requires_confirmation"])

    @patch("workers.source_discovery._probe_slug_candidates")
    @patch("workers.source_discovery.probe_candidate")
    @patch("workers.source_discovery._fetch_public_html")
    def test_ignores_zero_job_indirect_provider_reference(
        self,
        fetch_html,
        probe_candidate,
        probe_slugs,
    ) -> None:
        fetch_html.return_value = (
            (
                '<a href="https://jobs.ashbyhq.com/deel">ATS</a>'
                '<a href="/careers/job?ats_id=123">Live role</a>'
            ),
            "https://www.deel.com/careers/",
        )
        probe_candidate.return_value = {
            "provider": "ashby",
            "external_source_id": "deel",
            "region": None,
            "job_count": 0,
        }
        probe_slugs.return_value = [
            {
                "provider": "ashby",
                "external_source_id": "deel",
                "region": None,
                "job_count": 0,
            }
        ]

        result = discover_job_source(
            "https://www.deel.com/careers/",
            "Deel",
        )

        self.assertEqual(result["provider"], "html")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(
            result["metadata"]["job_link_path"],
            "/careers/job",
        )
