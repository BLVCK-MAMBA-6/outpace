"""Privacy-conscious Sentry error reporting for Outpace."""

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk


SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "apikey",
    }
)

SENSITIVE_DATA_KEYS = frozenset(
    {
        "access_token",
        "body",
        "code",
        "cookies",
        "data",
        "email",
        "password",
        "query",
        "query_string",
        "refresh_token",
        "token",
    }
)

_initialized = False


def _strip_url(value: Any) -> Any:
    """Remove query strings and fragments from captured URLs."""
    if not isinstance(value, str):
        return value

    try:
        parsed = urlsplit(value)
    except ValueError:
        return value.split("?", 1)[0].split("#", 1)[0]

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
        )
    )


def _scrub_headers(headers: Any) -> dict[str, Any]:
    """Filter credentials from captured request headers."""
    if not isinstance(headers, Mapping):
        return {}

    return {
        str(name): (
            "[Filtered]"
            if str(name).casefold() in SENSITIVE_HEADERS
            else value
        )
        for name, value in headers.items()
    }


def scrub_event(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any]:
    """Remove user identity, request bodies, and credentials."""
    del hint

    event.pop("user", None)

    request = event.get("request")

    if isinstance(request, dict):
        if "url" in request:
            request["url"] = _strip_url(
                request["url"]
            )

        if "headers" in request:
            request["headers"] = _scrub_headers(
                request["headers"]
            )

        for key in (
            "cookies",
            "data",
            "env",
            "query_string",
        ):
            request.pop(key, None)

    breadcrumbs = event.get("breadcrumbs")

    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")

        if isinstance(values, list):
            for breadcrumb in values:
                if not isinstance(breadcrumb, dict):
                    continue

                data = breadcrumb.get("data")

                if not isinstance(data, Mapping):
                    continue

                sanitized: dict[str, Any] = {}

                for key, value in data.items():
                    normalized = str(key).casefold()

                    if normalized == "url":
                        sanitized[str(key)] = (
                            _strip_url(value)
                        )
                    elif normalized == "headers":
                        sanitized[str(key)] = (
                            _scrub_headers(value)
                        )
                    elif (
                        normalized in SENSITIVE_DATA_KEYS
                        or normalized in SENSITIVE_HEADERS
                    ):
                        sanitized[str(key)] = "[Filtered]"
                    else:
                        sanitized[str(key)] = value

                breadcrumb["data"] = sanitized

    return event


def _environment() -> str:
    """Return the configured deployment environment."""
    return (
        os.getenv("SENTRY_ENVIRONMENT")
        or os.getenv("ENVIRONMENT")
        or "development"
    ).strip()


def _release() -> str | None:
    """Return one release identifier from CI or Render."""
    value = (
        os.getenv("SENTRY_RELEASE")
        or os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or ""
    ).strip()

    if not value:
        return None

    if value.startswith("outpace@"):
        return value

    return f"outpace@{value}"


def initialize_sentry(
    service: str,
    *,
    include_fastapi: bool = False,
) -> bool:
    """Initialize error-only monitoring when a DSN exists."""
    global _initialized

    dsn = os.getenv("SENTRY_DSN", "").strip()

    if not dsn:
        _initialized = False
        return False

    options: dict[str, Any] = {
        "dsn": dsn,
        "environment": _environment(),
        "release": _release(),
        "send_default_pii": False,
        "include_local_variables": False,
        "max_request_body_size": "never",
        "traces_sample_rate": 0.0,
        "profiles_sample_rate": 0.0,
        "before_send": scrub_event,
    }

    if include_fastapi:
        from sentry_sdk.integrations.fastapi import (
            FastApiIntegration,
        )

        options["integrations"] = [
            FastApiIntegration()
        ]

    try:
        sentry_sdk.init(**options)
        sentry_sdk.set_tag("service", service)
    except Exception:
        _initialized = False
        print(
            "Sentry initialization failed; continuing "
            "without remote error reporting.",
            flush=True,
        )
        return False

    _initialized = True
    return True


def report_exception(
    error: BaseException,
    *,
    tags: Mapping[str, Any] | None = None,
) -> str | None:
    """Report one fatal exception with safe diagnostic tags."""
    if not _initialized:
        return None

    try:
        with sentry_sdk.new_scope() as scope:
            for name, value in (tags or {}).items():
                scope.set_tag(
                    str(name),
                    str(value),
                )

            return sentry_sdk.capture_exception(
                error
            )
    except Exception:
        print(
            "Sentry exception reporting failed.",
            flush=True,
        )
        return None


def report_message(
    message: str,
    *,
    tags: Mapping[str, Any] | None = None,
) -> str | None:
    """Report a sanitized aggregate failure message."""
    if not _initialized:
        return None

    try:
        with sentry_sdk.new_scope() as scope:
            for name, value in (tags or {}).items():
                scope.set_tag(
                    str(name),
                    str(value),
                )

            return sentry_sdk.capture_message(
                message,
                level="error",
            )
    except Exception:
        print(
            "Sentry message reporting failed.",
            flush=True,
        )
        return None


def flush_sentry(
    timeout: float = 2.0,
) -> None:
    """Flush queued events before a short-lived worker exits."""
    if not _initialized:
        return

    try:
        sentry_sdk.flush(timeout=timeout)
    except Exception:
        print(
            "Sentry event flush failed.",
            flush=True,
        )
