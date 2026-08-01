"""
Render and send Outpace weekly competitive-intelligence digests.

Test without changing database rows:

    python -m workers.email.digest --test
"""

import argparse
import html
import os
from datetime import datetime, timezone
from typing import Any

import resend
from dotenv import load_dotenv

from api.utils.supabase_client import get_supabase_client


load_dotenv(".env")


PRIORITY_COLORS = {
    "urgent": "#dc2626",
    "high": "#ea580c",
    "normal": "#2563eb",
    "low": "#64748b",
}


def safe(value: Any) -> str:
    """Escape untrusted values before placing them in HTML."""
    return html.escape(
        str(value or ""),
        quote=True,
    )


def signal_label(signal_type: str) -> str:
    labels = {
        "general": "Website",
        "pricing": "Pricing",
        "reviews": "Reviews",
        "jobs": "Jobs",
        "news": "News & Press",
    }

    return labels.get(
        signal_type,
        signal_type.title(),
    )


def render_brief_card(
    brief: dict[str, Any],
) -> str:
    """Render one brief as an email-safe HTML card."""
    synthesis = brief.get("synthesis") or {}
    priority = str(
        brief.get("priority") or "normal"
    ).lower()

    color = PRIORITY_COLORS.get(
        priority,
        PRIORITY_COLORS["normal"],
    )

    evidence = synthesis.get("evidence") or []

    evidence_html = "".join(
        f"<li style='margin:6px 0'>{safe(item)}</li>"
        for item in evidence[:4]
    )

    if not evidence_html:
        evidence_html = (
            "<li style='margin:6px 0'>"
            "No additional evidence supplied."
            "</li>"
        )

    return f"""
    <div style="
        background:#ffffff;
        border:1px solid #e2e8f0;
        border-radius:12px;
        margin:0 0 18px;
        overflow:hidden;
    ">
      <div style="
          border-left:5px solid {color};
          padding:20px 22px;
      ">
        <div style="
            color:#64748b;
            font-size:12px;
            font-weight:700;
            letter-spacing:.06em;
            margin-bottom:8px;
            text-transform:uppercase;
        ">
          {safe(brief.get("competitor_name", "Competitor"))}
          &nbsp;•&nbsp;
          {safe(signal_label(brief.get("signal_type", "")))}
          &nbsp;•&nbsp;
          {safe(priority)} priority
        </div>

        <h2 style="
            color:#0f172a;
            font-size:20px;
            line-height:1.3;
            margin:0 0 12px;
        ">
          {safe(synthesis.get("headline", "Competitor change"))}
        </h2>

        <p style="
            color:#334155;
            font-size:15px;
            line-height:1.65;
            margin:0 0 16px;
        ">
          {safe(synthesis.get("summary"))}
        </p>

        <h3 style="
            color:#0f172a;
            font-size:14px;
            margin:18px 0 6px;
        ">
          Why it matters
        </h3>

        <p style="
            color:#475569;
            font-size:14px;
            line-height:1.6;
            margin:0;
        ">
          {safe(synthesis.get("why_it_matters"))}
        </p>

        <h3 style="
            color:#0f172a;
            font-size:14px;
            margin:18px 0 6px;
        ">
          Recommended action
        </h3>

        <p style="
            color:#475569;
            font-size:14px;
            line-height:1.6;
            margin:0;
        ">
          {safe(synthesis.get("recommended_action"))}
        </p>

        <h3 style="
            color:#0f172a;
            font-size:14px;
            margin:18px 0 6px;
        ">
          Evidence
        </h3>

        <ul style="
            color:#475569;
            font-size:13px;
            line-height:1.5;
            margin:0;
            padding-left:20px;
        ">
          {evidence_html}
        </ul>
      </div>
    </div>
    """


def render_digest_html(
    briefs: list[dict[str, Any]],
    test_mode: bool = False,
) -> str:
    """Render a complete weekly digest."""
    cards = "".join(
        render_brief_card(brief)
        for brief in briefs
    )

    test_banner = ""

    if test_mode:
        test_banner = """
        <div style="
            background:#fef3c7;
            border:1px solid #f59e0b;
            border-radius:8px;
            color:#92400e;
            font-size:13px;
            margin:0 0 20px;
            padding:12px 14px;
        ">
          Controlled email-template test. This does not represent
          real competitor activity.
        </div>
        """

    generated_date = datetime.now(
        timezone.utc
    ).strftime("%d %B %Y")

    return f"""<!doctype html>
<html>
  <body style="
      background:#f1f5f9;
      font-family:Arial,Helvetica,sans-serif;
      margin:0;
      padding:0;
  ">
    <div style="
        margin:0 auto;
        max-width:680px;
        padding:32px 18px;
    ">
      <div style="margin-bottom:24px">
        <div style="
            color:#2563eb;
            font-size:14px;
            font-weight:800;
            letter-spacing:.12em;
            text-transform:uppercase;
        ">
          Outpace
        </div>

        <h1 style="
            color:#0f172a;
            font-size:30px;
            margin:8px 0;
        ">
          Weekly Competitive Brief
        </h1>

        <p style="
            color:#64748b;
            font-size:14px;
            margin:0;
        ">
          {safe(generated_date)} · {len(briefs)} actionable
          {"signal" if len(briefs) == 1 else "signals"}
        </p>
      </div>

      {test_banner}
      {cards}

      <p style="
          color:#94a3b8;
          font-size:12px;
          line-height:1.5;
          margin:24px 0 0;
          text-align:center;
      ">
        Generated by Outpace competitive intelligence.
      </p>
    </div>
  </body>
</html>
"""


def render_digest_text(
    briefs: list[dict[str, Any]],
    test_mode: bool = False,
) -> str:
    """Render a plain-text email alternative."""
    lines = [
        "OUTPACE — WEEKLY COMPETITIVE BRIEF",
        "",
    ]

    if test_mode:
        lines.extend(
            [
                "CONTROLLED EMAIL TEMPLATE TEST",
                "This is not real competitor activity.",
                "",
            ]
        )

    for brief in briefs:
        synthesis = brief.get("synthesis") or {}

        lines.extend(
            [
                (
                    f"{brief.get('competitor_name', 'Competitor')} "
                    f"— {signal_label(brief.get('signal_type', ''))}"
                ),
                str(synthesis.get("headline", "")),
                "",
                str(synthesis.get("summary", "")),
                "",
                "Why it matters:",
                str(synthesis.get("why_it_matters", "")),
                "",
                "Recommended action:",
                str(synthesis.get("recommended_action", "")),
                "",
                "-" * 60,
                "",
            ]
        )

    return "\n".join(lines)


def send_email(
    briefs: list[dict[str, Any]],
    test_mode: bool = False,
    recipient_email: str | None = None,
) -> dict[str, Any]:
    """Send one rendered digest through Resend."""
    if not test_mode and not recipient_email:
        raise ValueError(
            "Production digest delivery requires "
            "an explicit recipient"
        )

    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL")
    to_email = (
        recipient_email
        or os.getenv("DIGEST_TEST_EMAIL")
        or ""
    ).strip().lower()

    missing = [
        key
        for key, value in {
            "RESEND_API_KEY": api_key,
            "RESEND_FROM_EMAIL": from_email,
            "DIGEST_RECIPIENT": to_email,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing email configuration: "
            + ", ".join(missing)
        )

    resend.api_key = api_key

    subject = "Outpace Weekly Competitive Brief"

    if test_mode:
        subject = "[TEST] " + subject

    response = resend.Emails.send(
        {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": render_digest_html(
                briefs,
                test_mode=test_mode,
            ),
            "text": render_digest_text(
                briefs,
                test_mode=test_mode,
            ),
            "tags": [
                {
                    "name": "email_type",
                    "value": (
                        "digest_test"
                        if test_mode
                        else "weekly_digest"
                    ),
                }
            ],
        }
    )

    email_id = (
        response.get("id")
        if isinstance(response, dict)
        else getattr(response, "id", None)
    )

    return {
        "status": "sent",
        "email_id": email_id,
        "recipient": to_email,
        "brief_count": len(briefs),
        "test_mode": test_mode,
    }


def get_undelivered_briefs(
    user_id: str,
) -> list[dict[str, Any]]:
    """Retrieve undelivered real briefs for one MVP user."""
    db = get_supabase_client()

    brief_result = (
        db.table("briefs")
        .select(
            "id,competitor_id,signal_type,synthesis,"
            "priority,delivered,created_at,raw_diff"
        )
        .eq("user_id", user_id)
        .eq("delivered", False)
        .order("created_at", desc=False)
        .limit(100)
        .execute()
    )

    competitor_result = (
        db.table("competitors")
        .select("id,name")
        .eq("user_id", user_id)
        .execute()
    )

    names = {
        competitor["id"]: competitor["name"]
        for competitor in competitor_result.data or []
    }

    briefs = []

    for brief in brief_result.data or []:
        raw_diff = brief.get("raw_diff") or {}

        if raw_diff.get("test_fixture"):
            continue

        briefs.append(
            {
                **brief,
                "competitor_name": names.get(
                    brief["competitor_id"],
                    "Competitor",
                ),
            }
        )

    return briefs


def mark_delivered(
    user_id: str,
    brief_ids: list[str],
) -> None:
    """Mark one user's successfully emailed briefs as delivered."""
    if not brief_ids:
        return

    db = get_supabase_client()

    (
        db.table("briefs")
        .update({"delivered": True})
        .eq("user_id", user_id)
        .in_("id", brief_ids)
        .execute()
    )


def mark_digest_sent(
    user_id: str,
) -> None:
    """Record the latest successful digest delivery."""
    db = get_supabase_client()

    (
        db.table("digest_preferences")
        .update(
            {
                "last_sent_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )
        .eq("user_id", user_id)
        .execute()
    )


def list_enabled_digest_preferences(
) -> list[dict[str, Any]]:
    """Return every user who opted into weekly delivery."""
    db = get_supabase_client()

    result = (
        db.table("digest_preferences")
        .select(
            "user_id,delivery_email,"
            "frequency,last_sent_at"
        )
        .eq("enabled", True)
        .eq("frequency", "weekly")
        .execute()
    )

    return result.data or []


def validate_recipient_email(
    recipient_email: str,
) -> str:
    """Defensively validate one stored delivery address."""
    email = recipient_email.strip().lower()

    if (
        "@" not in email
        or email.startswith("@")
        or email.endswith("@")
        or " " in email
    ):
        raise ValueError(
            "Digest preference has an invalid "
            "delivery email"
        )

    return email


def send_weekly_digest(
    user_id: str,
    recipient_email: str,
) -> dict[str, Any]:
    """Send one user's real briefs and mark successful delivery."""
    email = validate_recipient_email(
        recipient_email
    )
    briefs = get_undelivered_briefs(
        user_id
    )

    if not briefs:
        return {
            "status": "no_briefs",
            "user_id": user_id,
            "message": (
                "No undelivered real briefs were available. "
                "Test fixtures were excluded."
            ),
        }

    result = send_email(
        briefs=briefs,
        test_mode=False,
        recipient_email=email,
    )
    brief_ids = [
        brief["id"]
        for brief in briefs
    ]

    mark_delivered(
        user_id,
        brief_ids,
    )
    mark_digest_sent(
        user_id
    )

    return {
        **result,
        "user_id": user_id,
        "brief_ids": brief_ids,
    }


def send_all_weekly_digests(
) -> dict[str, Any]:
    """Process every opted-in user without stopping at one failure."""
    preferences = (
        list_enabled_digest_preferences()
    )
    results: list[dict[str, Any]] = []

    for preference in preferences:
        user_id = str(
            preference.get("user_id") or ""
        )
        recipient_email = str(
            preference.get("delivery_email") or ""
        )

        try:
            result = send_weekly_digest(
                user_id=user_id,
                recipient_email=recipient_email,
            )
            results.append(
                {
                    "user_id": user_id,
                    "status": result["status"],
                    "brief_count": result.get(
                        "brief_count",
                        0,
                    ),
                    "email_id": result.get(
                        "email_id"
                    ),
                }
            )
        except Exception as error:
            results.append(
                {
                    "user_id": user_id or "unknown",
                    "status": "failed",
                    "error": str(error),
                }
            )

    failures = [
        result
        for result in results
        if result["status"] == "failed"
    ]
    sent_count = sum(
        result["status"] == "sent"
        for result in results
    )
    no_briefs_count = sum(
        result["status"] == "no_briefs"
        for result in results
    )

    if not preferences:
        overall_status = "no_recipients"
    elif failures and len(failures) < len(results):
        overall_status = "partial_failure"
    elif failures:
        overall_status = "failure"
    else:
        overall_status = "success"

    return {
        "status": overall_status,
        "preference_count": len(preferences),
        "sent_count": sent_count,
        "no_briefs_count": no_briefs_count,
        "failure_count": len(failures),
        "results": results,
    }


def demo_briefs() -> list[dict[str, Any]]:
    """Return clearly synthetic email-template data."""
    return [
        {
            "competitor_name": (
                "Demo Analytics Company — Test Fixture"
            ),
            "signal_type": "news",
            "priority": "low",
            "synthesis": {
                "headline": (
                    "[TEST DATA] New enterprise AI "
                    "announcement detected"
                ),
                "summary": (
                    "This is synthetic content used only to verify "
                    "the Outpace weekly email template."
                ),
                "why_it_matters": (
                    "It confirms that structured briefs render "
                    "correctly in HTML and plain-text email."
                ),
                "recommended_action": (
                    "Check the layout and verify that this message "
                    "arrived in the intended inbox."
                ),
                "evidence": [
                    "Controlled test fixture",
                    "No real competitor event occurred",
                ],
            },
        }
    ]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send an Outpace weekly digest"
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--test",
        action="store_true",
        help="Send a synthetic test digest",
    )

    mode.add_argument(
        "--send",
        action="store_true",
        help="Send real briefs to all opted-in users",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.test:
        result = send_email(
            briefs=demo_briefs(),
            test_mode=True,
        )
    else:
        result = send_all_weekly_digests()

    print(result)


if __name__ == "__main__":
    main()
