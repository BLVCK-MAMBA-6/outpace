"""
Structured pricing-page scraper.

Run:

    python -m workers.scrapers.pricing --competitor-id <UUID>
"""

import argparse
import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from api.utils.supabase_client import get_supabase_client


KNOWN_PLAN_NAMES = {
    "free",
    "basic",
    "starter",
    "plus",
    "pro",
    "professional",
    "premium",
    "team",
    "business",
    "business plus",
    "growth",
    "scale",
    "enterprise",
    "custom",
}

FEATURE_LABELS = {
    "ai tasks",
    "ai tasks✨",
    "data tables",
    "integrations",
    "spreadsheets",
    "cell enrichment",
    "file import size",
    "guest members",
    "embeds",
    "version history",
    "rows api calls",
    "support",
}


def valid_uuid(value: str) -> str:
    """Validate a competitor UUID before querying Supabase."""
    try:
        return str(UUID(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid competitor UUID: {value}"
        ) from error


def normalize_lines(text: str) -> list[str]:
    """Convert visible page text into clean, non-empty lines."""
    lines = []

    for line in text.splitlines():
        normalized = re.sub(r"\s+", " ", line).strip()

        if normalized:
            lines.append(normalized)

    return lines


def detect_block_page(title: str, text: str) -> None:
    """Reject Cloudflare and other bot-challenge pages."""
    title_lower = title.lower()
    sample = text[:5000].lower()

    indicators = [
        "verify you are human",
        "checking your browser",
        "performing security verification",
        "enable javascript and cookies to continue",
        "attention required",
    ]

    if "just a moment" in title_lower:
        raise RuntimeError(
            "Pricing page was blocked by a challenge page"
        )

    if any(indicator in sample for indicator in indicators):
        raise RuntimeError(
            "Pricing page was blocked by bot protection"
        )


def is_price_line(line: str) -> bool:
    """Return True when a line contains a displayed price."""
    return bool(
        re.search(
            r"[$€£]\s?\d[\d,.]*",
            line,
            flags=re.IGNORECASE,
        )
    )


def parse_price(price_display: str) -> dict[str, Any]:
    """Extract numeric and billing details from a price string."""
    currency_symbols = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    currency = None
    amount = None

    for symbol, code in currency_symbols.items():
        if symbol in price_display:
            currency = code
            break

    amount_match = re.search(
        r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)",
        price_display,
    )

    if amount_match:
        amount = float(
            amount_match.group(1).replace(",", "")
        )

    lower = price_display.lower()

    if "/month" in lower or "/mo" in lower or "per month" in lower:
        billing_period = "monthly"
    elif "/year" in lower or "/yr" in lower or "per year" in lower:
        billing_period = "yearly"
    elif amount == 0:
        billing_period = "free"
    elif "contact" in lower or "custom" in lower:
        billing_period = "custom"
    else:
        billing_period = "unknown"

    return {
        "price_display": price_display,
        "amount": amount,
        "currency": currency,
        "billing_period": billing_period,
    }


def should_ignore_feature(line: str) -> bool:
    """Remove buttons, badges, and unrelated page text."""
    lower = line.lower()

    ignored_prefixes = [
        "get started",
        "start free",
        "try for free",
        "choose ",
        "select ",
        "contact us",
        "contact sales",
        "learn more",
        "buy now",
    ]

    noise_prefixes = [
        "prices shown are",
        "you’re in great company",
        "you're in great company",
    ]

    ignored_exact = {
        "popular",
        "most popular",
        "recommended",
        "monthly",
        "annually",
        "annual",
    }

    if lower in ignored_exact:
        return True

    if any(
        lower.startswith(prefix)
        for prefix in ignored_prefixes
    ):
        return True

    if any(
        lower.startswith(prefix)
        for prefix in noise_prefixes
    ):
        return True

    if "has joined superhuman" in lower:
        return True

    return False


def combine_feature_lines(features: list[str]) -> list[str]:
    """Combine feature labels with their following values."""
    combined = []
    index = 0

    while index < len(features):
        current = features[index]
        current_lower = current.lower()

        if current_lower in FEATURE_LABELS and index + 1 < len(features):
            following = features[index + 1]
            following_lower = following.lower()

            if following_lower not in FEATURE_LABELS:
                combined.append(f"{current}: {following}")
                index += 2
                continue

        combined.append(current)
        index += 1

    return combined


def extract_plans(text: str) -> list[dict[str, Any]]:
    """Extract primary plan cards from pricing-page text."""
    lines = normalize_lines(text)

    # Exclude comparison tables and FAQs from primary plan extraction.
    cutoff_markers = [
        "compare plans",
        "compare features",
        "questions and answers",
        "frequently asked questions",
    ]

    cutoff = len(lines)

    for index, line in enumerate(lines):
        lower = line.lower()

        if any(
            lower.startswith(marker)
            for marker in cutoff_markers
        ):
            cutoff = index
            break

    primary_lines = lines[:cutoff]

    starts = []
    seen_names = set()

    for index, line in enumerate(primary_lines):
        normalized_name = line.lower()

        if (
            normalized_name in KNOWN_PLAN_NAMES
            and normalized_name not in seen_names
        ):
            starts.append((index, line))
            seen_names.add(normalized_name)

    plans = []

    for position, (start_index, plan_name) in enumerate(starts):
        if position + 1 < len(starts):
            end_index = starts[position + 1][0]
        else:
            end_index = len(primary_lines)

        block = primary_lines[start_index + 1:end_index]

        price_index = None
        price_display = None

        for index, line in enumerate(block):
            if is_price_line(line):
                price_index = index
                price_display = line
                break

        if price_display is None:
            for index, line in enumerate(block):
                lower = line.lower()

                if (
                    "contact us" in lower
                    or "contact sales" in lower
                ):
                    price_index = index
                    price_display = "Contact sales"
                    break

        if (
            price_display is None
            and plan_name.lower() == "enterprise"
        ):
            price_display = "Contact sales"
            price_index = -1

        if price_index is not None and price_index >= 0:
            description_end = price_index
        else:
            description_end = len(block)

        description = None

        for line in block[:description_end]:
            if should_ignore_feature(line):
                continue

            if is_price_line(line) or line == "-":
                continue

            description = line
            break

        if price_index is not None and price_index >= 0:
            feature_start = price_index + 1
        else:
            feature_start = 0

        features = []

        for line in block[feature_start:]:
            if should_ignore_feature(line):
                continue

            if line == "-" or line == description:
                continue

            if is_price_line(line):
                continue

            if line not in features:
                features.append(line)

        cleaned_features = combine_feature_lines(features)

        plans.append(
            {
                "name": plan_name,
                "description": description,
                **parse_price(price_display or "Unknown"),
                "features": cleaned_features[:30],
            }
        )

    if len(plans) < 2:
        raise RuntimeError(
            "Could not reliably identify at least two pricing plans"
        )

    return plans


async def fetch_pricing_page(url: str) -> dict[str, Any]:
    """Render a pricing page and return structured pricing data."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1440,
                "height": 1000,
            },
            locale="en-US",
        )

        page = await context.new_page()

        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=15_000,
                )
            except PlaywrightTimeoutError:
                # Some sites continuously make network requests.
                pass

            await page.wait_for_timeout(2_000)

            title = await page.title()
            final_url = page.url
            visible_text = await page.locator("body").inner_text()
            html = await page.content()

            status_code = (
                response.status
                if response
                else None
            )

            if status_code and status_code >= 400:
                raise RuntimeError(
                    f"Pricing page returned HTTP {status_code}"
                )

            detect_block_page(title, visible_text)

            plans = extract_plans(visible_text)

            normalized_plans = json.dumps(
                plans,
                sort_keys=True,
                ensure_ascii=False,
            )

            billing_options = []

            if re.search(
                r"\bmonthly\b",
                visible_text,
                re.IGNORECASE,
            ):
                billing_options.append("monthly")

            if re.search(
                r"\bannual(?:ly)?\b",
                visible_text,
                re.IGNORECASE,
            ):
                billing_options.append("annually")

            return {
                "requested_url": url,
                "final_url": final_url,
                "title": title,
                "status_code": status_code,
                "extractor_version": "pricing-v1.1",
                "billing_options": billing_options,
                "plans": plans,
                "plan_count": len(plans),
                "structure_hash": hashlib.sha256(
                    normalized_plans.encode("utf-8")
                ).hexdigest(),
                "source_html_hash": hashlib.sha256(
                    html.encode("utf-8")
                ).hexdigest(),
                "captured_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

        finally:
            await context.close()
            await browser.close()


async def scrape_pricing(
    competitor_id: str,
) -> dict[str, Any]:
    """Fetch a competitor pricing page and store its snapshot."""
    supabase = get_supabase_client()

    result = (
        supabase.table("competitors")
        .select("id,name,pricing_url")
        .eq("id", competitor_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(
            f"No competitor found with id: {competitor_id}"
        )

    competitor = result.data[0]
    pricing_url = competitor.get("pricing_url")

    if not pricing_url:
        raise ValueError(
            f"{competitor['name']} does not have a pricing URL"
        )

    print(f"Scraping pricing: {competitor['name']}")
    print(f"URL: {pricing_url}")

    raw_content = await fetch_pricing_page(pricing_url)

    snapshot_result = (
        supabase.table("snapshots")
        .insert(
            {
                "competitor_id": competitor["id"],
                "signal_type": "pricing",
                "raw_content": raw_content,
            }
        )
        .execute()
    )

    if not snapshot_result.data:
        raise RuntimeError(
            "Supabase did not return the pricing snapshot"
        )

    snapshot = snapshot_result.data[0]

    print("\nPricing snapshot stored successfully")
    print(f"Snapshot ID: {snapshot['id']}")
    print(f"Plans found: {raw_content['plan_count']}")

    for plan in raw_content["plans"]:
        print(
            f"- {plan['name']}: "
            f"{plan['price_display']}"
        )

    return snapshot


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape a structured competitor pricing snapshot"
        )
    )

    parser.add_argument(
        "--competitor-id",
        required=True,
        type=valid_uuid,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        asyncio.run(
            scrape_pricing(args.competitor_id)
        )
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"\nPricing scrape failed: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()