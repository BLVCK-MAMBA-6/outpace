"""
Celery application and recurring Outpace monitoring schedules.

Start a worker:

    celery -A workers.celery_app:celery_app worker --loglevel=info

Start the scheduler:

    celery -A workers.celery_app:celery_app beat --loglevel=info
"""

import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


load_dotenv()

redis_url = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

result_backend = os.getenv(
    "CELERY_RESULT_BACKEND",
    redis_url,
)

celery_app = Celery(
    "outpace",
    broker=redis_url,
    backend=result_backend,
    include=[
        "workers.tasks",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    result_expires=86400,
    beat_schedule={
        "general-monitoring-weekly": {
            "task": (
                "outpace.schedule_general_monitoring"
            ),
            "schedule": crontab(
                minute=0,
                hour=6,
                day_of_week="monday",
            ),
        },
        "weekly-digest-monday": {
            "task": "outpace.send_weekly_digest",
            "schedule": crontab(
                minute=0,
                hour=8,
                day_of_week="monday",
            ),
        },
        "pricing-monitoring-every-48-hours": {
            "task": (
                "outpace.schedule_pricing_monitoring"
            ),
            "schedule": timedelta(hours=48),
        },
        "review-monitoring-daily": {
            "task": (
                "outpace.schedule_review_monitoring"
            ),
            "schedule": crontab(
                minute=0,
                hour=7,
            ),
        },
        "job-monitoring-every-12-hours": {
            "task": (
                "outpace.schedule_job_monitoring"
            ),
            "schedule": timedelta(hours=12),
        },
        "news-monitoring-every-6-hours": {
            "task": (
                "outpace.schedule_news_monitoring"
            ),
            "schedule": timedelta(hours=6),
        },
    },
)
