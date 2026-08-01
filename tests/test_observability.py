"""Tests for privacy-safe production error monitoring."""

import os
import unittest
from unittest.mock import patch

from api.utils import observability


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        observability._initialized = False

    def tearDown(self):
        observability._initialized = False

    def test_scrub_event_removes_identity_and_secrets(self):
        event = {
            "user": {
                "email": "private@example.com",
            },
            "request": {
                "url": (
                    "https://outpace.example/auth/callback"
                    "?token=secret#fragment"
                ),
                "headers": {
                    "Authorization": "Bearer secret",
                    "Accept": "application/json",
                    "Cookie": "session=secret",
                },
                "cookies": {"session": "secret"},
                "data": {"email": "private@example.com"},
                "env": {"REMOTE_ADDR": "127.0.0.1"},
                "query_string": "token=secret",
            },
            "breadcrumbs": {
                "values": [
                    {
                        "data": {
                            "url": (
                                "https://outpace.example/login"
                                "?code=secret"
                            ),
                            "headers": {
                                "Cookie": "secret",
                            },
                            "body": "secret",
                        },
                    },
                ],
            },
        }

        result = observability.scrub_event(
            event,
            {},
        )

        self.assertNotIn("user", result)

        request = result["request"]
        self.assertEqual(
            request["url"],
            "https://outpace.example/auth/callback",
        )
        self.assertEqual(
            request["headers"]["Authorization"],
            "[Filtered]",
        )
        self.assertEqual(
            request["headers"]["Cookie"],
            "[Filtered]",
        )
        self.assertNotIn("cookies", request)
        self.assertNotIn("data", request)
        self.assertNotIn("env", request)
        self.assertNotIn("query_string", request)

        breadcrumb = (
            result["breadcrumbs"]["values"][0]["data"]
        )
        self.assertEqual(
            breadcrumb["url"],
            "https://outpace.example/login",
        )
        self.assertEqual(
            breadcrumb["headers"]["Cookie"],
            "[Filtered]",
        )
        self.assertEqual(
            breadcrumb["body"],
            "[Filtered]",
        )

    def test_missing_dsn_keeps_monitoring_disabled(self):
        with patch.dict(
            os.environ,
            {"SENTRY_DSN": ""},
            clear=False,
        ):
            initialized = (
                observability.initialize_sentry(
                    "api",
                    include_fastapi=True,
                )
            )

        self.assertFalse(initialized)
        self.assertFalse(
            observability._initialized
        )

    def test_initialization_disables_pii_and_tracing(self):
        environment = {
            "SENTRY_DSN": (
                "https://public@example.ingest.sentry.io/1"
            ),
            "SENTRY_ENVIRONMENT": "production-worker",
            "GITHUB_SHA": "abc123",
        }

        with (
            patch.dict(
                os.environ,
                environment,
                clear=True,
            ),
            patch.object(
                observability.sentry_sdk,
                "init",
            ) as initialize,
            patch.object(
                observability.sentry_sdk,
                "set_tag",
            ) as set_tag,
        ):
            initialized = (
                observability.initialize_sentry(
                    "worker"
                )
            )

        self.assertTrue(initialized)

        options = initialize.call_args.kwargs
        self.assertFalse(
            options["send_default_pii"]
        )
        self.assertFalse(
            options["include_local_variables"]
        )
        self.assertEqual(
            options["max_request_body_size"],
            "never",
        )
        self.assertEqual(
            options["traces_sample_rate"],
            0.0,
        )
        self.assertEqual(
            options["profiles_sample_rate"],
            0.0,
        )
        self.assertEqual(
            options["environment"],
            "production-worker",
        )
        self.assertEqual(
            options["release"],
            "outpace@abc123",
        )
        set_tag.assert_called_once_with(
            "service",
            "worker",
        )


if __name__ == "__main__":
    unittest.main()
