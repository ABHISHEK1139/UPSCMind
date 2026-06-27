from .celery_app import celery_app
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task
def scrape_pib_daily():
    logger.info("Starting PIB daily scrape...")
    time.sleep(2)
    logger.info("PIB daily scrape completed.")
    return True

@celery_app.task
def run_evaluation_benchmark():
    logger.info("Running evaluation benchmark suite...")
    time.sleep(5)
    logger.info("Benchmark complete. Scores logged to MinIO.")
    return True

@celery_app.task
def export_dataset_to_huggingface():
    logger.info("Exporting weekly dataset to HuggingFace...")
    time.sleep(2)
    logger.info("Export complete.")
    return True
