"""Regression tests for provider-specific pricing extraction."""

import unittest

from workers.scrapers.pricing import (
    extract_deel_plans,
    is_deel_pricing_url,
)


DEEL_PRICING_TEXT = """
Pricing
Transparent and fair pricing that grows with your business
Hire
Manage
Pay
Equip
Find talent
Best for
Best for sourcing, screening, and hiring in one place.
$14
per worker per month
Book a demo
Job posting and full pipeline visibility by stage
AI-powered screening
Hire contractors
Best for
Best for engaging global contractors.
$49
per contractor per month
$325
per contractor of record per month
Book a demo
Centralized contractor management
Payments in 120+ currencies
Hire full-time employees
Best for
Best for employing full-time workers globally.
$125
per US PEO employee per month
$599
per EOR employee per month
Book a demo
EOR: Full legal employment in 130+ countries globally
US PEO: Co-employment across all 50 US states
Which solution is right for my business?
$20B+
compliantly processed global payroll
"""


class PricingProviderParserTests(unittest.TestCase):
    def test_recognizes_official_deel_pricing_urls(self) -> None:
        self.assertTrue(
            is_deel_pricing_url(
                "https://www.deel.com/pricing/"
            )
        )
        self.assertTrue(
            is_deel_pricing_url(
                "https://deel.com/pricing"
            )
        )
        self.assertFalse(
            is_deel_pricing_url(
                "https://www.deel.com/careers/"
            )
        )
        self.assertFalse(
            is_deel_pricing_url(
                "https://example.com/pricing/"
            )
        )

    def test_extracts_each_displayed_deel_price_point(self) -> None:
        plans = extract_deel_plans(DEEL_PRICING_TEXT)
        by_name = {
            plan["name"]: plan
            for plan in plans
        }

        self.assertEqual(
            list(by_name),
            [
                "Find talent",
                "Contractor",
                "Contractor of Record",
                "US PEO",
                "Employer of Record",
            ],
        )
        self.assertEqual(by_name["Find talent"]["amount"], 14.0)
        self.assertEqual(by_name["Contractor"]["amount"], 49.0)
        self.assertEqual(
            by_name["Contractor of Record"]["amount"],
            325.0,
        )
        self.assertEqual(by_name["US PEO"]["amount"], 125.0)
        self.assertEqual(
            by_name["Employer of Record"]["amount"],
            599.0,
        )

        for plan in plans:
            self.assertEqual(plan["currency"], "USD")
            self.assertEqual(
                plan["billing_period"],
                "monthly",
            )

    def test_preserves_features_from_parent_card(self) -> None:
        plans = extract_deel_plans(DEEL_PRICING_TEXT)
        contractor = next(
            plan
            for plan in plans
            if plan["name"] == "Contractor"
        )
        contractor_of_record = next(
            plan
            for plan in plans
            if plan["name"] == "Contractor of Record"
        )

        expected = [
            "Centralized contractor management",
            "Payments in 120+ currencies",
        ]
        self.assertEqual(contractor["features"], expected)
        self.assertEqual(
            contractor_of_record["features"],
            expected,
        )

    def test_accepts_price_and_unit_on_one_line(self) -> None:
        combined = DEEL_PRICING_TEXT.replace(
            "$14\nper worker per month",
            "$14 per worker per month",
        )
        plans = extract_deel_plans(combined)

        self.assertEqual(plans[0]["name"], "Find talent")
        self.assertEqual(plans[0]["amount"], 14.0)
        self.assertEqual(
            plans[0]["billing_period"],
            "monthly",
        )

    def test_ignores_marketing_amount_after_primary_cards(self) -> None:
        plans = extract_deel_plans(DEEL_PRICING_TEXT)

        self.assertNotIn(
            20.0,
            {
                plan["amount"]
                for plan in plans
            },
        )

    def test_rejects_incomplete_deel_card_set(self) -> None:
        incomplete = DEEL_PRICING_TEXT.replace(
            "Hire full-time employees",
            "Employ globally",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Could not identify Deel pricing card",
        ):
            extract_deel_plans(incomplete)

    def test_rejects_missing_secondary_price(self) -> None:
        incomplete = DEEL_PRICING_TEXT.replace(
            "$325\nper contractor of record per month\n",
            "",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "incomplete or ambiguous",
        ):
            extract_deel_plans(incomplete)


if __name__ == "__main__":
    unittest.main()
