"""
Hermes V2 — Celery Application
═══════════════════════════════════════════════════════════════
Celery app configured with Redis broker for background task
processing: scraping, indexing, evaluation, dataset export.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

redis_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery(
    "hermes_workers",
    broker=redis_url,
    backend=backend_url,
    include=[
        "workers.tasks_scraping",
        "workers.tasks_indexing",
        "workers.tasks_evaluation",
        "workers.tasks_dataset",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    # Beat schedule
    beat_schedule={
        "scrape-pib-daily": {
            "task": "workers.tasks_scraping.scrape_pib_daily",
            "schedule": crontab(hour=6, minute=0),
        },
        "scrape-prs-daily": {
            "task": "workers.tasks_scraping.scrape_prs_daily",
            "schedule": crontab(hour=7, minute=0),
        },
        "run-benchmark-weekly": {
            "task": "workers.tasks_evaluation.run_evaluation_benchmark",
            "schedule": crontab(day_of_week=0, hour=2, minute=0),  # Sunday 2AM
        },
        "export-dataset-weekly": {
            "task": "workers.tasks_dataset.export_training_dataset",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 4AM
        },
        "cleanup-storage-weekly": {
            "task": "workers.tasks_dataset.cleanup_old_data",
            "schedule": crontab(day_of_week=1, hour=3, minute=0),  # Monday 3AM
        },
    },
)
