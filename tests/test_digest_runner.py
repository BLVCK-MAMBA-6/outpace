import unittest

from scripts.run_scheduled_monitoring import (
    digest_execution_result,
)


class DigestRunnerTests(
    unittest.TestCase
):
    def test_zero_delivery_failures_are_successful(self):
        execution = digest_execution_result(
            {
                "status": "success",
                "preference_count": 2,
                "sent_count": 1,
                "no_briefs_count": 1,
                "failure_count": 0,
            }
        )

        self.assertEqual(
            execution["status"],
            "success",
        )
        self.assertNotIn(
            "error",
            execution,
        )

    def test_any_delivery_failure_fails_digest_signal(self):
        execution = digest_execution_result(
            {
                "status": "partial_failure",
                "preference_count": 3,
                "sent_count": 2,
                "no_briefs_count": 0,
                "failure_count": 1,
            }
        )

        self.assertEqual(
            execution["status"],
            "failed",
        )
        self.assertEqual(
            execution["error"],
            "1 user digest delivery failure(s)",
        )


if __name__ == "__main__":
    unittest.main()
