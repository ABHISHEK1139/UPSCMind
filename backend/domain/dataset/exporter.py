"""
Hermes V2 — Dataset Exporter
═══════════════════════════════════════════════════════════════
Exports collected training data in various formats for
fine-tuning frameworks (Unsloth, Axolotl, LLaMA-Factory, TRL).

Supports:
  - ChatML / ShareGPT (SFT)
  - DPO pairs
  - ORPO pairs
  - Reward model data
  - Full trajectory data
  - Deduplication and cleaning
  - MinIO upload
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from domain.dataset.schemas import ExportFormat, ExportManifest

logger = logging.getLogger(__name__)

DEFAULT_EXPORT_DIR = Path("dataset/exports")


class DatasetExporter:
    """
    Cleans, deduplicates, and exports training datasets.
    Can be triggered manually or via Celery beat (weekly).
    """

    def __init__(
        self,
        data_dir: str | Path = "dataset/training_data",
        export_dir: str | Path = DEFAULT_EXPORT_DIR,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._export_dir = Path(export_dir)
        try:
            self._export_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.warning("[EXPORT] Cannot create export dir %s (permission denied). Will create on first write.", self._export_dir)

    # ── Deduplication ─────────────────────────────────────────

    @staticmethod
    def deduplicate_jsonl(
        input_path: Path,
        output_path: Path,
        key_field: str = "question",
    ) -> tuple[int, int]:
        """
        Remove duplicate records from a JSONL file based on a key field.

        Returns (kept_count, removed_count).
        """
        if not input_path.exists():
            logger.warning("[EXPORT] File not found: %s", input_path)
            return 0, 0

        seen: Set[str] = set()
        kept = 0
        removed = 0

        with open(input_path, "r", encoding="utf-8") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    removed += 1
                    continue

                # Extract the dedup key
                if key_field == "question" and "messages" in record:
                    # ChatML format — key is the user message
                    user_msgs = [m for m in record["messages"] if m.get("role") == "user"]
                    key = user_msgs[0]["content"] if user_msgs else line
                elif key_field in record:
                    key = str(record[key_field])
                else:
                    key = line

                dedup_hash = hashlib.md5(key.encode()).hexdigest()
                if dedup_hash not in seen:
                    seen.add(dedup_hash)
                    fout.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    kept += 1
                else:
                    removed += 1

        logger.info(
            "[EXPORT] Deduplicated %s: kept=%d removed=%d",
            input_path.name, kept, removed,
        )
        return kept, removed

    # ── Statistics ────────────────────────────────────────────

    def compute_statistics(self, jsonl_path: Path) -> Dict[str, Any]:
        """Compute statistics for a training data file."""
        if not jsonl_path.exists():
            return {"total": 0}

        total = 0
        scores = []
        domains: Dict[str, int] = {}

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1

                # Collect scores
                meta = record.get("metadata", {})
                score = meta.get("critique_score") or record.get("critique_score")
                if score is not None:
                    scores.append(float(score))

                # Collect domains
                domain = meta.get("domain") or record.get("domain", "unknown")
                domains[domain] = domains.get(domain, 0) + 1

        stats: Dict[str, Any] = {"total": total, "domains": domains}
        if scores:
            stats["min_score"] = min(scores)
            stats["max_score"] = max(scores)
            stats["avg_score"] = sum(scores) / len(scores)

        return stats

    # ── Export Pipeline ───────────────────────────────────────

    def export_all(
        self,
        min_score: float = 0.9,
        deduplicate: bool = True,
        upload_to_minio: bool = False,
    ) -> ExportManifest:
        """
        Run the full export pipeline:
          1. Deduplicate all training data files
          2. Filter by minimum quality score
          3. Compute statistics
          4. Optionally upload to MinIO
          5. Generate manifest
        """
        timestamp = datetime.now(timezone.utc)
        export_id = hashlib.md5(str(timestamp).encode()).hexdigest()[:12]
        export_subdir = self._export_dir / f"export_{export_id}"
        export_subdir.mkdir(parents=True, exist_ok=True)

        total_records = 0
        rejected_count = 0
        all_domains: Dict[str, int] = {}
        min_s = 1.0
        max_s = 0.0
        sum_s = 0.0
        score_count = 0

        # Process each training data file
        for data_file in self._data_dir.glob("*.jsonl"):
            if data_file.name == "rejected.jsonl":
                # Count rejected
                with open(data_file, "r") as f:
                    rejected_count = sum(1 for line in f if line.strip())
                continue

            # Step 1: Deduplicate
            if deduplicate:
                deduped_path = export_subdir / f"deduped_{data_file.name}"
                kept, _ = self.deduplicate_jsonl(data_file, deduped_path)
            else:
                deduped_path = data_file
                kept = sum(1 for _ in open(data_file, "r") if _.strip())

            # Step 2: Filter by score
            filtered_path = export_subdir / data_file.name
            filtered_count = self._filter_by_score(deduped_path, filtered_path, min_score)

            # Step 3: Stats
            stats = self.compute_statistics(filtered_path)
            total_records += stats.get("total", 0)
            for dom, cnt in stats.get("domains", {}).items():
                all_domains[dom] = all_domains.get(dom, 0) + cnt
            if "min_score" in stats:
                min_s = min(min_s, stats["min_score"])
                max_s = max(max_s, stats["max_score"])
                sum_s += stats["avg_score"] * stats.get("total", 0)
                score_count += stats.get("total", 0)

        avg_score = sum_s / score_count if score_count > 0 else 0.0

        # Data versioning metadata
        version_info = {
            "dataset_version": export_id,
            "prompt_version": _get_current_prompt_version(),
            "retriever_version": "hybrid_v2",
            "planner_version": "dspy_v2",
            "model_versions": {
                "drafting": "owl-alpha",
                "critique": "owl-alpha",
                "topic_detection": "owl-alpha",
            },
            "created_at": timestamp.isoformat(),
            "created_by": "hermes-v2-exporter",
        }

        # Create manifest
        manifest = ExportManifest(
            format=ExportFormat.CHATML,
            total_records=total_records,
            quality_threshold=min_score,
            output_path=str(export_subdir),
            min_score=min_s if score_count > 0 else 0.0,
            max_score=max_s,
            avg_score=avg_score,
            domains=all_domains,
            rejected_count=rejected_count,
        )

        manifest_path = export_subdir / "manifest.json"
        manifest_data = manifest.model_dump(mode="json")
        manifest_data["version_info"] = version_info
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, default=str)

        logger.info(
            "[EXPORT] Complete: %d records exported, %d rejected, avg_score=%.3f",
            total_records, rejected_count, avg_score,
        )

        # Upload to MinIO if requested
        if upload_to_minio:
            self._upload_to_minio(export_subdir, export_id)

        return manifest

    def _filter_by_score(
        self, input_path: Path, output_path: Path, min_score: float
    ) -> int:
        """Filter records by minimum quality score."""
        count = 0
        with open(input_path, "r", encoding="utf-8") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Check score in various locations
                score = None
                meta = record.get("metadata", {})
                if "critique_score" in meta:
                    score = float(meta["critique_score"])
                elif "critique_score" in record:
                    score = float(record["critique_score"])
                elif "score" in record:
                    score = float(record["score"])

                if score is not None and score < min_score:
                    continue

                fout.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                count += 1

        return count

    def _upload_to_minio(self, export_dir: Path, export_id: str) -> None:
        """Upload export directory to MinIO."""
        try:
            from minio import Minio
            from core.config import get_settings

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

            for file_path in export_dir.glob("*"):
                if file_path.is_file():
                    object_name = f"exports/{export_id}/{file_path.name}"
                    client.fput_object(bucket, object_name, str(file_path))
                    logger.info("[EXPORT] Uploaded %s to MinIO.", object_name)

        except Exception as exc:
            logger.error("[EXPORT] MinIO upload failed: %s", exc)


def _get_current_prompt_version() -> str:
    """Get the current prompt version from the prompt registry."""
    try:
        from prompts.registry import PromptRegistry
        registry = PromptRegistry()
        versions = {}
        for name in registry.list_all():
            prompt = registry.get(name)
            if prompt:
                versions[name] = f"v{prompt.version}"
        return str(versions) if versions else "unknown"
    except Exception:
        return "unknown"
