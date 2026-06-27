"""
Hermes V2 — Dataset Storage Manager
═══════════════════════════════════════════════════════════════
Manages local and remote (MinIO) storage for training datasets.
Provides rotation, cleanup, and versioning.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import get_settings

logger = logging.getLogger(__name__)


class DatasetStorage:
    """Manages dataset file storage with rotation and MinIO sync."""

    def __init__(
        self,
        local_dir: str | Path = "dataset/training_data",
        max_local_gb: float = 10.0,
    ) -> None:
        self._local_dir = Path(local_dir)
        self._local_dir.mkdir(parents=True, exist_ok=True)
        self._max_local_bytes = int(max_local_gb * 1024 ** 3)

    def get_file_path(self, name: str) -> Path:
        """Get the full path for a training data file."""
        return self._local_dir / name

    def rotate_file(self, name: str, max_size_mb: float = 500.0) -> Optional[Path]:
        """
        Rotate a file if it exceeds max_size_mb.
        Returns the archived path or None.
        """
        file_path = self._local_dir / name
        if not file_path.exists():
            return None

        size_mb = file_path.stat().st_size / (1024 ** 2)
        if size_mb < max_size_mb:
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        stem = file_path.stem
        suffix = file_path.suffix
        archive_name = f"{stem}_{timestamp}{suffix}"
        archive_path = self._local_dir / "archive" / archive_name
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(file_path), str(archive_path))
        logger.info("[STORAGE] Rotated %s → %s (%.1f MB)", name, archive_name, size_mb)
        return archive_path

    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """Remove archive files older than max_age_days. Returns count removed."""
        archive_dir = self._local_dir / "archive"
        if not archive_dir.exists():
            return 0

        now = datetime.now(timezone.utc).timestamp()
        removed = 0
        for f in archive_dir.glob("*"):
            if f.is_file():
                age_days = (now - f.stat().st_mtime) / 86400
                if age_days > max_age_days:
                    f.unlink()
                    removed += 1

        if removed:
            logger.info("[STORAGE] Cleaned up %d old files.", removed)
        return removed

    def sync_to_minio(self, prefix: str = "") -> int:
        """Sync all training data files to MinIO. Returns count uploaded."""
        try:
            from minio import Minio

            settings = get_settings()
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,
            )

            bucket = settings.MINIO_BUCKET_DATASETS
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)

            uploaded = 0
            for f in self._local_dir.glob("*.jsonl"):
                object_name = f"{prefix}{f.name}" if prefix else f.name
                client.fput_object(bucket, object_name, str(f))
                uploaded += 1

            logger.info("[STORAGE] Synced %d files to MinIO.", uploaded)
            return uploaded

        except Exception as exc:
            logger.error("[STORAGE] MinIO sync failed: %s", exc)
            return 0

    def get_storage_stats(self) -> dict:
        """Return storage usage statistics."""
        total_size = 0
        file_count = 0
        for f in self._local_dir.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1

        return {
            "total_files": file_count,
            "total_size_mb": round(total_size / (1024 ** 2), 2),
            "total_size_gb": round(total_size / (1024 ** 3), 4),
            "max_size_gb": round(self._max_local_bytes / (1024 ** 3), 2),
            "usage_percent": round(
                total_size / self._max_local_bytes * 100, 2
            ) if self._max_local_bytes > 0 else 0,
        }
