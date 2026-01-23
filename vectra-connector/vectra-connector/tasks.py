from .celery import app
import os
from datetime import datetime, timedelta
from .vectra_api import VectraAPI
from .logger import logger


@app.task
def get_data_from_audit_api():
    """Celery task for fetch data from audit API.

    Returns:
        dict: Audit Events
    """
    logger.info("Executing Audit API task.")
    URL = f"{str(os.environ.get('BASE_URL')).strip().strip('/')}/api/v3.3/events/audits"
    checkpoint_file_path = "./audit_checkpoint.json"
    params = {}
    if not os.path.exists(checkpoint_file_path):
        current_time = datetime.utcnow()
        # Subtract 24 hours
        new_time = current_time - timedelta(hours=24)
        # Format as "2023-05-31T14:10:00Z"
        formatted_time = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {"event_timestamp_gte": formatted_time}
    total_data = VectraAPI.fetch_data_from_api(url=URL, filename="audit", params=params)
    return total_data


@app.task
def get_data_from_entity_api():
    """Celery task for fetch data from entity_scoring API.

    Returns:
        dict: entity_scoring Events
    """
    URL = f"{str(os.environ.get('BASE_URL')).strip().strip('/')}/api/v3.3/events/entity_scoring"
    types = {
        "account": "./entity_account_checkpoint.json",
        "host": "./entity_host_checkpoint.json",
    }
    for typ, checkpoint_path in types.items():
        logger.info(f"Executing Entity {typ} API task.")
        params = {"type": typ}
        if not os.path.exists(checkpoint_path):
            current_time = datetime.utcnow()
            new_time = current_time - timedelta(hours=24)
            formatted_time = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            params.update({"event_timestamp_gte": formatted_time})
        total_data = VectraAPI.fetch_data_from_api(
            url=URL, params=params, filename=f"entity_{typ}"
        )
    return total_data


@app.task
def get_data_from_detection():
    """Celery task for fetch data from detections API.

    Returns:
        dict: Detections Events
    """
    logger.info("Executing Detection API task.")
    URL = f"{str(os.environ.get('BASE_URL')).strip().strip('/')}/api/v3.3/events/detections"
    checkpoint_file_path = "./detection_checkpoint.json"
    # TM-4540 - do not pull triaged detections
    params = {}
    params.update({"include_triaged": "false"})
    params.update({"include_info_category": "true"})
    if not os.path.exists(checkpoint_file_path):
        current_time = datetime.utcnow()
        new_time = current_time - timedelta(hours=24)
        formatted_time = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        params.update({"event_timestamp_gte": formatted_time})
    total_data = VectraAPI.fetch_data_from_api(
        url=URL, filename="detection", params=params
    )
    return total_data
