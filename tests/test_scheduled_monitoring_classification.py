import unittest

from scripts.run_scheduled_monitoring import (
    classify_monitoring_error,
    run_targets,
)


class DegradedTask:
    @staticmethod
    def run(target_id: str) -> dict:
        raise ValueError(
            "Deel detail crawl was incomplete; snapshot rejected "
            "to prevent false removals"
        )


class ScheduledMonitoringClassificationTests(unittest.TestCase):
    def test_incomplete_deel_snapshot_is_degraded(self) -> None:
        classification = classify_monitoring_error(
            ValueError(
                "Deel detail crawl was incomplete; snapshot rejected "
                "to prevent false removals"
            )
        )

        self.assertEqual(
            classification,
            {
                "status": "degraded",
                "health_status": "degraded",
                "error_code": "provider_degraded",
            },
        )

    def test_empty_html_news_source_is_degraded(self) -> None:
        classification = classify_monitoring_error(
            ValueError(
                "No article URLs were discovered from "
                "the HTML news source"
            )
        )

        self.assertEqual(
            classification,
            {
                "status": "degraded",
                "health_status": "degraded",
                "error_code": "provider_degraded",
            },
        )

    def test_blocked_source_is_nonfatal(self) -> None:
        classification = classify_monitoring_error(
            ValueError("Cloudflare access denied")
        )

        self.assertEqual(classification["status"], "degraded")
        self.assertEqual(
            classification["health_status"],
            "blocked",
        )

    def test_unknown_application_failure_remains_fatal(self) -> None:
        classification = classify_monitoring_error(
            RuntimeError("Unexpected database invariant violation")
        )

        self.assertEqual(classification["status"], "failed")
        self.assertEqual(
            classification["error_code"],
            "collection_failed",
        )

    def test_run_targets_retains_degraded_result(self) -> None:
        results = run_targets(
            signal_type="jobs",
            targets=[{"id": "deel-source"}],
            task=DegradedTask,
            id_key="id",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "degraded")
        self.assertEqual(
            results[0]["health_status"],
            "degraded",
        )


if __name__ == "__main__":
    unittest.main()
