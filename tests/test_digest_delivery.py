import unittest
from unittest.mock import patch

from workers.email import digest


class DigestDeliveryTests(
    unittest.TestCase
):
    def test_one_user_delivery_is_scoped_and_recorded(self):
        briefs = [
            {
                "id": "brief-1",
            },
            {
                "id": "brief-2",
            },
        ]

        with (
            patch.object(
                digest,
                "get_undelivered_briefs",
                return_value=briefs,
            ),
            patch.object(
                digest,
                "send_email",
                return_value={
                    "status": "sent",
                    "email_id": "email-1",
                    "brief_count": 2,
                },
            ) as send_email,
            patch.object(
                digest,
                "mark_delivered",
            ) as mark_delivered,
            patch.object(
                digest,
                "mark_digest_sent",
            ) as mark_digest_sent,
        ):
            result = digest.send_weekly_digest(
                user_id="user-1",
                recipient_email=(
                    "  USER@Example.com "
                ),
            )

        send_email.assert_called_once_with(
            briefs=briefs,
            test_mode=False,
            recipient_email="user@example.com",
        )
        mark_delivered.assert_called_once_with(
            "user-1",
            [
                "brief-1",
                "brief-2",
            ],
        )
        mark_digest_sent.assert_called_once_with(
            "user-1"
        )
        self.assertEqual(
            result["status"],
            "sent",
        )

    def test_no_briefs_sends_nothing(self):
        with (
            patch.object(
                digest,
                "get_undelivered_briefs",
                return_value=[],
            ),
            patch.object(
                digest,
                "send_email",
            ) as send_email,
            patch.object(
                digest,
                "mark_delivered",
            ) as mark_delivered,
            patch.object(
                digest,
                "mark_digest_sent",
            ) as mark_digest_sent,
        ):
            result = digest.send_weekly_digest(
                user_id="user-1",
                recipient_email="user@example.com",
            )

        self.assertEqual(
            result["status"],
            "no_briefs",
        )
        send_email.assert_not_called()
        mark_delivered.assert_not_called()
        mark_digest_sent.assert_not_called()

    def test_fanout_continues_after_one_failure(self):
        preferences = [
            {
                "user_id": "user-1",
                "delivery_email": "one@example.com",
            },
            {
                "user_id": "user-2",
                "delivery_email": "two@example.com",
            },
            {
                "user_id": "user-3",
                "delivery_email": "three@example.com",
            },
        ]

        outcomes = [
            RuntimeError("Resend unavailable"),
            {
                "status": "sent",
                "brief_count": 3,
                "email_id": "email-2",
            },
            {
                "status": "no_briefs",
            },
        ]

        with (
            patch.object(
                digest,
                "list_enabled_digest_preferences",
                return_value=preferences,
            ),
            patch.object(
                digest,
                "send_weekly_digest",
                side_effect=outcomes,
            ) as send_weekly_digest,
        ):
            result = (
                digest.send_all_weekly_digests()
            )

        self.assertEqual(
            send_weekly_digest.call_count,
            3,
        )
        self.assertEqual(
            result["status"],
            "partial_failure",
        )
        self.assertEqual(
            result["preference_count"],
            3,
        )
        self.assertEqual(
            result["sent_count"],
            1,
        )
        self.assertEqual(
            result["no_briefs_count"],
            1,
        )
        self.assertEqual(
            result["failure_count"],
            1,
        )

    def test_no_enabled_users_is_safe(self):
        with patch.object(
            digest,
            "list_enabled_digest_preferences",
            return_value=[],
        ):
            result = (
                digest.send_all_weekly_digests()
            )

        self.assertEqual(
            result["status"],
            "no_recipients",
        )
        self.assertEqual(
            result["preference_count"],
            0,
        )
        self.assertEqual(
            result["failure_count"],
            0,
        )

    def test_invalid_stored_email_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            digest.validate_recipient_email(
                "invalid-address"
            )


if __name__ == "__main__":
    unittest.main()
