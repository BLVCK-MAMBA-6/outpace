"""Tests for scheduled-worker error reporting."""

import unittest
from unittest.mock import patch

from scripts import run_scheduled_monitoring as monitoring


class FailingTask:
    def __init__(
        self,
        error: Exception,
    ):
        self.error = error

    def run(
        self,
        target_id: str,
    ):
        del target_id
        raise self.error


class ScheduledMonitoringObservabilityTests(
    unittest.TestCase
):
    def test_fatal_source_failure_is_reported(self):
        task = FailingTask(
            RuntimeError(
                "Unexpected application failure"
            )
        )

        with patch.object(
            monitoring,
            "report_exception",
        ) as report:
            results = monitoring.run_targets(
                signal_type="jobs",
                targets=[{"id": "source-id"}],
                task=task,
                id_key="id",
            )

        self.assertEqual(
            results[0]["status"],
            "failed",
        )
        report.assert_called_once()

    def test_degraded_source_is_not_reported_as_error(self):
        task = FailingTask(
            ValueError(
                "Deel detail crawl was incomplete; "
                "snapshot rejected to prevent false removals"
            )
        )

        with patch.object(
            monitoring,
            "report_exception",
        ) as report:
            results = monitoring.run_targets(
                signal_type="jobs",
                targets=[{"id": "source-id"}],
                task=task,
                id_key="id",
            )

        self.assertEqual(
            results[0]["status"],
            "degraded",
        )
        report.assert_not_called()

    def test_digest_delivery_failures_are_reported(self):
        with patch.object(
            monitoring,
            "report_message",
        ) as report:
            result = (
                monitoring.digest_execution_result(
                    {
                        "failure_count": 2,
                    }
                )
            )

        self.assertEqual(
            result["status"],
            "failed",
        )
        report.assert_called_once()

    def test_successful_digest_is_not_reported(self):
        with patch.object(
            monitoring,
            "report_message",
        ) as report:
            result = (
                monitoring.digest_execution_result(
                    {
                        "failure_count": 0,
                    }
                )
            )

        self.assertEqual(
            result["status"],
            "success",
        )
        report.assert_not_called()


if __name__ == "__main__":
    unittest.main()
