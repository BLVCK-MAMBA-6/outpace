"""Validate Outpace's zero-cost production deployment contract."""

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = ROOT / "render.yaml"
DOCKERFILE_PATH = ROOT / "Dockerfile"
FRONTEND_ENV_PATH = ROOT / "frontend" / ".env.example"


def fail(message: str) -> None:
    raise SystemExit(f"Deployment configuration invalid: {message}")


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

    services = blueprint.get("services")

    if not isinstance(services, list):
        fail("render.yaml must contain a services list")

    service_map = {
        service["name"]: service
        for service in services
        if isinstance(service, dict) and "name" in service
    }

    expected_names = {"outpace-api", "outpace-web"}

    if set(service_map) != expected_names:
        fail(
            "free deployment must contain only "
            "outpace-api and outpace-web"
        )

    api = service_map["outpace-api"]
    frontend = service_map["outpace-web"]

    if api.get("type") != "web":
        fail("outpace-api must be a web service")

    if api.get("runtime") != "docker":
        fail("outpace-api must use the Docker runtime")

    if api.get("plan") != "free":
        fail("outpace-api must use the free plan")

    if frontend.get("type") != "web":
        fail("outpace-web must be a web service")

    if frontend.get("runtime") != "static":
        fail("outpace-web must use the static runtime")

    api_required = {
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_AUTH_REDIRECT_URL",
        "FRONTEND_URL",
        "GEMINI_API_KEY",
    }

    frontend_required = {
        "VITE_SUPABASE_URL",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_API_URL",
    }

    for name, service, required in (
        ("outpace-api", api, api_required),
        ("outpace-web", frontend, frontend_required),
    ):
        missing = required - env_keys(service)

        if missing:
            fail(f"{name} is missing {sorted(missing)}")

    blueprint_text = BLUEPRINT_PATH.read_text(encoding="utf-8")

    forbidden = (
        "outpace-queue",
        "outpace-worker",
        "outpace-beat",
        "type: worker",
        "type: keyvalue",
        "plan: starter",
        "plan: standard",
    )

    for value in forbidden:
        if value in blueprint_text:
            fail(f"paid or persistent resource remains: {value}")

    frontend_text = FRONTEND_ENV_PATH.read_text(encoding="utf-8")

    if "SERVICE_ROLE" in frontend_text:
        fail("frontend example exposes a service-role variable")

    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    if "python:3.12-slim-bookworm" not in dockerfile:
        fail("Dockerfile must pin the Python base image")

    if "playwright install --with-deps chromium" not in dockerfile:
        fail("Dockerfile must install Chromium")

    print("Free deployment configuration passed")
    print("Services:", ", ".join(sorted(service_map)))


if __name__ == "__main__":
    main()
