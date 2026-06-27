"""
Hermes V2 — Dataset Export Tasks
═══════════════════════════════════════════════════════════════
Background tasks for exporting, cleaning, and uploading
training datasets.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def export_training_dataset(
    self,
    min_score: float = 0.9,
    deduplicate: bool = True,
    upload_to_minio: bool = True,
) -> Dict[str, Any]:
    """
    Weekly task: export high-quality training data.
    Runs every Sunday at 4AM via Celery beat.
    """
    try:
        logger.info("[DATASET] Starting weekly export (min_score=%.2f)...", min_score)
        from domain.dataset.exporter import DatasetExporter

        exporter = DatasetExporter()
        manifest = exporter.export_all(
            min_score=min_score,
            deduplicate=deduplicate,
            upload_to_minio=upload_to_minio,
        )
        logger.info(
            "[DATASET] Export complete: %d records, avg_score=%.3f",
            manifest.total_records,
            manifest.avg_score,
        )
        return manifest.model_dump(mode="json")
    except Exception as exc:
        logger.error("[DATASET] Export failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def cleanup_old_data(self, max_age_days: int = 30) -> Dict[str, Any]:
    """Clean up old training data files."""
    try:
        logger.info("[DATASET] Cleaning up data older than %d days...", max_age_days)
        from domain.dataset.storage import DatasetStorage

        storage = DatasetStorage()
        removed = storage.cleanup_old_files(max_age_days=max_age_days)
        stats = storage.get_storage_stats()
        logger.info("[DATASET] Cleanup complete: removed=%d, stats=%s", removed, stats)
        return {"removed": removed, "stats": stats}
    except Exception as exc:
        logger.error("[DATASET] Cleanup failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=900)
def sync_to_minio(self, prefix: str = "training_data/") -> Dict[str, Any]:
    """Sync training data to MinIO object storage."""
    try:
        logger.info("[DATASET] Syncing to MinIO...")
        from domain.dataset.storage import DatasetStorage

        storage = DatasetStorage()
        uploaded = storage.sync_to_minio(prefix=prefix)
        logger.info("[DATASET] Synced %d files to MinIO.", uploaded)
        return {"uploaded": uploaded}
    except Exception as exc:
        logger.error("[DATASET] MinIO sync failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def generate_dataset_statistics(self) -> Dict[str, Any]:
    """Generate statistics about the collected training data."""
    try:
        from domain.dataset.exporter import DatasetExporter

        exporter = DatasetExporter()
        stats = {}
        for data_file in exporter._data_dir.glob("*.jsonl"):
            stats[data_file.name] = exporter.compute_statistics(data_file)
        logger.info("[DATASET] Statistics: %s", stats)
        return stats
    except Exception as exc:
        logger.error("[DATASET] Statistics generation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
