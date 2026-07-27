"""Validate Outpace's deploy-time contract without reading secret values."""

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = ROOT / "render.yaml"
DOCKERFILE_PATH = ROOT / "Dockerfile"
FRONTEND_ENV_PATH = ROOT / "frontend" / ".env.example"


def fail(message: str) -> None:
    raise SystemExit(f"Deployment configuration invalid: {message}")


def service_map(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    services = blueprint.get("services")

    if not isinstance(services, list):
        fail("render.yaml must contain a services list")

    return {
        service["name"]: service
        for service in services
        if isinstance(service, dict) and "name" in service
    }


def env_keys(service: dict[str, Any]) -> set[str]:
    return {
        item["key"]
        for item in service.get("envVars", [])
        if isinstance(item, dict) and "key" in item
    }


def main() -> None:
    blueprint = yaml.safe_load(
        BLUEPRINT_PATH.read_text(encoding="utf-8")
    )
    services = service_map(blueprint)

    expected_types = {
        "outpace-queue": "keyvalue",
        "outpace-api": "web",
        "outpace-worker": "worker",
        "outpace-beat": "worker",
        "outpace-web": "web",
    }

    for name, expected_type in expected_types.items():
        service = services.get(name)

        if service is None:
            fail(f"missing service {name}")

        if service.get("type") != expected_type:
            fail(f"{name} must have type {expected_type}")

    queue = services["outpace-queue"]

    if queue.get("maxmemoryPolicy") != "noeviction":
        fail("outpace-queue must use noeviction")

    if queue.get("persistenceMode") != "journal-snapshot":
        fail("outpace-queue must use journal-snapshot persistence")

    if queue.get("ipAllowList") != []:
        fail("outpace-queue must reject public network access")

    api_required = {
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_AUTH_REDIRECT_URL",
        "FRONTEND_URL",
        "GEMINI_API_KEY",
        "REDIS_URL",
        "CELERY_RESULT_BACKEND",
    }
    worker_required = {
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GEMINI_API_KEY",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "DIGEST_TO_EMAIL",
        "DIGEST_USER_ID",
        "REDIS_URL",
        "CELERY_RESULT_BACKEND",
    }
    frontend_required = {
        "VITE_SUPABASE_URL",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_API_URL",
    }

    checks = (
        ("outpace-api", api_required),
        ("outpace-worker", worker_required),
        ("outpace-web", frontend_required),
    )

    for name, required in checks:
        missing = required - env_keys(services[name])

        if missing:
            fail(f"{name} is missing {sorted(missing)}")

    frontend_text = FRONTEND_ENV_PATH.read_text(encoding="utf-8")

    if "SERVICE_ROLE" in frontend_text:
        fail("frontend example exposes a service-role variable")

    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    if "python:3.12-slim-bookworm" not in dockerfile:
        fail("Dockerfile must pin the Python base image")

    if "playwright install --with-deps chromium" not in dockerfile:
        fail("Dockerfile must install Chromium and its OS dependencies")

    print("Deployment configuration passed")
    print("Services:", ", ".join(sorted(services)))


if __name__ == "__main__":
    main()
