"""
General website monitor.

Fetches a competitor homepage with Playwright, extracts meaningful
text, and stores the result in the Supabase snapshots table.

Run from the repository root:

    python -m workers.scrapers.general --competitor-id <UUID>
"""

import argparse
import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from api.utils.supabase_client import get_supabase_client


def extract_meaningful_text(html: str) -> str:
    """Remove non-content elements and return normalized page text."""
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "template",
            "iframe",
            "canvas",
        ]
    ):
        element.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Normalize excessive spaces and blank lines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


async def fetch_homepage(url: str) -> dict[str, Any]:
    """Fetch a rendered homepage and return its HTML and text."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # Match the user agent to the installed Chromium version.
        chromium_version = browser.version

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chromium_version} Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            extra_http_headers={
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/avif,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        page = await context.new_page()

        await page.add_init_script(
            """
            Object.defineProperty(navigator, "webdriver", {
                get: () => undefined
            });

            Object.defineProperty(navigator, "languages", {
                get: () => ["en-US", "en"]
            });

            Object.defineProperty(navigator, "plugins", {
                get: () => [1, 2, 3, 4, 5]
            });

            window.chrome = {
                runtime: {}
            };
            """
        )

        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            # Some sites continuously make background requests,
            # so networkidle timing out is not necessarily a failure.
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=15_000,
                )
            except PlaywrightTimeoutError:
                pass

            # Allow JavaScript-rendered content to appear.
            await page.wait_for_timeout(2_000)

            html = await page.content()
            title = await page.title()
            final_url = page.url
            status_code = response.status if response else None
            text = extract_meaningful_text(html)

            blocked_markers = (
                "just a moment",
                "verify you are human",
                "access denied",
                "attention required",
                "cf-chl",
                "cloudflare",
            )

            page_check = f"{title}\n{text[:2000]}".lower()
            appears_blocked = any(
                marker in page_check for marker in blocked_markers
            )

            if status_code and status_code >= 400:
                raise RuntimeError(
                    f"Homepage returned HTTP status {status_code}. "
                    f"Page title: {title!r}"
                )

            if appears_blocked:
                raise RuntimeError(
                    "The website returned a bot-protection page "
                    f"instead of its homepage. Page title: {title!r}"
                )

            if not text:
                raise RuntimeError(
                    "The scraper did not extract any page text"
                )

            return {
                "requested_url": url,
                "final_url": final_url,
                "title": title,
                "status_code": status_code,
                "html": html,
                "text": text,
                "html_character_count": len(html),
                "text_character_count": len(text),
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            await context.close()
            await browser.close()


async def scrape_competitor(competitor_id: str) -> dict[str, Any]:
    """Load a competitor, scrape its homepage, and save a snapshot."""
    supabase = get_supabase_client()

    competitor_result = (
        supabase.table("competitors")
        .select("id,name,website_url")
        .eq("id", competitor_id)
        .limit(1)
        .execute()
    )

    if not competitor_result.data:
        raise ValueError(
            f"No competitor found with id: {competitor_id}"
        )

    competitor = competitor_result.data[0]

    print(f"Scraping: {competitor['name']}")
    print(f"URL: {competitor['website_url']}")

    raw_content = await fetch_homepage(
        competitor["website_url"]
    )

    snapshot_row = {
        "competitor_id": competitor["id"],
        "signal_type": "general",
        "raw_content": raw_content,
    }

    snapshot_result = (
        supabase.table("snapshots")
        .insert(snapshot_row)
        .execute()
    )

    if not snapshot_result.data:
        raise RuntimeError(
            "Supabase did not return the inserted snapshot"
        )

    snapshot = snapshot_result.data[0]

    print("\nSnapshot stored successfully")
    print(f"Snapshot ID: {snapshot['id']}")
    print(f"Competitor ID: {snapshot['competitor_id']}")
    print(
        "HTML characters: "
        f"{raw_content['html_character_count']}"
    )
    print(
        "Text characters: "
        f"{raw_content['text_character_count']}"
    )
    print(f"Page title: {raw_content['title']}")

    return snapshot


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Scrape and store a competitor homepage snapshot"
        )
    )
    parser.add_argument(
        "--competitor-id",
        required=True,
        help="UUID of the competitor in Supabase",
    )

    return parser.parse_args()


def main() -> None:
    """Run the general website scraper."""
    args = parse_arguments()

    try:
        asyncio.run(
            scrape_competitor(args.competitor_id)
        )
    except KeyboardInterrupt:
        print("\nScrape cancelled")
        raise SystemExit(130)
    except Exception as error:
        print(f"\nScrape failed: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()