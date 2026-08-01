import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from api.models.schemas import (
    AuthenticatedUser,
    DigestPreferenceResponse,
    DigestPreferenceUpdate,
)
from api.routers import digest_preferences


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeDigestQuery:
    def __init__(self, database):
        self.database = database
        self.filters = {}
        self.mode = "select"
        self.result_data = []

    def select(self, _columns):
        self.mode = "select"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _limit):
        return self

    def upsert(
        self,
        record,
        on_conflict=None,
    ):
        self.mode = "upsert"
        self.database.on_conflict = on_conflict

        user_id = record["user_id"]
        existing = self.database.records.get(
            user_id,
            {},
        )
        now = datetime.now(
            timezone.utc
        ).isoformat()

        stored = {
            **existing,
            **record,
        }
        stored.setdefault(
            "last_sent_at",
            None,
        )
        stored.setdefault(
            "created_at",
            now,
        )
        stored.setdefault(
            "updated_at",
            now,
        )

        self.database.records[user_id] = stored
        self.result_data = [stored]

        return self

    def execute(self):
        if self.mode == "upsert":
            return FakeResult(
                self.result_data
            )

        user_id = self.filters.get(
            "user_id"
        )
        preference = self.database.records.get(
            user_id
        )

        return FakeResult(
            [preference]
            if preference is not None
            else []
        )


class FakeDigestDatabase:
    def __init__(self):
        self.records = {}
        self.on_conflict = None

    def table(self, table_name):
        if table_name != "digest_preferences":
            raise AssertionError(
                f"Unexpected table: {table_name}"
            )

        return FakeDigestQuery(self)


class DigestPreferenceTests(
    unittest.TestCase
):
    def make_user(
        self,
        email="Founder@Outpace.Test",
    ):
        return AuthenticatedUser(
            id=uuid4(),
            email=email,
        )

    def test_missing_row_returns_disabled_default(self):
        database = FakeDigestDatabase()
        user = self.make_user()

        with patch.object(
            digest_preferences,
            "get_supabase_client",
            return_value=database,
        ):
            result = (
                digest_preferences
                .get_digest_preference(user)
            )

        response = (
            DigestPreferenceResponse
            .model_validate(result)
        )

        self.assertFalse(response.enabled)
        self.assertEqual(
            response.delivery_email,
            "founder@outpace.test",
        )
        self.assertEqual(
            response.frequency,
            "weekly",
        )
        self.assertIsNone(
            response.last_sent_at
        )

    def test_update_uses_verified_login_email(self):
        database = FakeDigestDatabase()
        user = self.make_user(
            "  Founder@Outpace.Test  "
        )
        request = DigestPreferenceUpdate(
            enabled=True
        )

        with patch.object(
            digest_preferences,
            "get_supabase_client",
            return_value=database,
        ):
            result = (
                digest_preferences
                .update_digest_preference(
                    request,
                    user,
                )
            )

        response = (
            DigestPreferenceResponse
            .model_validate(result)
        )
        stored = database.records[
            str(user.id)
        ]

        self.assertTrue(response.enabled)
        self.assertEqual(
            stored["delivery_email"],
            "founder@outpace.test",
        )
        self.assertEqual(
            database.on_conflict,
            "user_id",
        )

    def test_arbitrary_delivery_email_is_rejected(self):
        with self.assertRaises(
            ValidationError
        ):
            DigestPreferenceUpdate.model_validate(
                {
                    "enabled": True,
                    "delivery_email": (
                        "someone-else@example.com"
                    ),
                }
            )

    def test_verified_email_is_required(self):
        user = self.make_user(
            email=None
        )
        request = DigestPreferenceUpdate(
            enabled=True
        )

        with self.assertRaises(
            HTTPException
        ) as raised:
            (
                digest_preferences
                .update_digest_preference(
                    request,
                    user,
                )
            )

        self.assertEqual(
            raised.exception.status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
