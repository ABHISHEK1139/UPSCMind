"""
Hermes V2 — Evaluation Routes
═══════════════════════════════════════════════════════════════
API endpoints for running benchmarks, viewing metrics, and
comparing V1 vs V2 performance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/benchmark/status")
async def benchmark_status() -> Dict[str, Any]:
    """Get the status of the latest benchmark run."""
    return {
        "status": "idle",
        "last_run": None,
        "total_questions": 0,
        "avg_score": 0.0,
    }


@router.post("/benchmark/run")
async def run_benchmark(
    background_tasks: BackgroundTasks,
    n_questions: int = Query(default=500, ge=1, le=5000),
    dataset_path: str = "dataset/mains_gs_all.jsonl",
) -> Dict[str, Any]:
    """Trigger a benchmark run in the background."""
    try:
        from workers.tasks_evaluation import run_evaluation_benchmark

        task = run_evaluation_benchmark.delay(n_questions=n_questions, dataset_path=dataset_path)
        logger.info("[API] Benchmark triggered: task_id=%s n=%d", task.id, n_questions)
        return {
            "status": "started",
            "task_id": task.id,
            "n_questions": n_questions,
        }
    except Exception as exc:
        logger.error("[API] Benchmark trigger failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


@router.get("/benchmark/results/{task_id}")
async def benchmark_results(task_id: str) -> Dict[str, Any]:
    """Get results of a benchmark run by task ID."""
    try:
        from celery.result import AsyncResult
        from workers.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }
    except Exception as exc:
        return {"task_id": task_id, "status": "error", "detail": str(exc)}


@router.get("/regression/v1-v2")
async def v1_v2_regression() -> Dict[str, Any]:
    """Run V1 vs V2 regression comparison."""
    try:
        from workers.tasks_evaluation import run_v1_v2_regression

        task = run_v1_v2_regression.delay()
        return {"status": "started", "task_id": task.id}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/dataset/statistics")
async def dataset_statistics() -> Dict[str, Any]:
    """Get statistics about the collected training data."""
    try:
        from domain.dataset.exporter import DatasetExporter

        exporter = DatasetExporter()
        stats = {}
        for data_file in exporter._data_dir.glob("*.jsonl"):
            stats[data_file.name] = exporter.compute_statistics(data_file)
        return {"status": "ok", "statistics": stats}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/dataset/export")
async def trigger_dataset_export(
    background_tasks: BackgroundTasks,
    min_score: float = Query(default=0.9, ge=0.0, le=1.0),
    upload_to_minio: bool = True,
) -> Dict[str, Any]:
    """Trigger a dataset export."""
    try:
        from workers.tasks_dataset import export_training_dataset

        task = export_training_dataset.delay(
            min_score=min_score,
            upload_to_minio=upload_to_minio,
        )
        return {"status": "started", "task_id": task.id, "min_score": min_score}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
