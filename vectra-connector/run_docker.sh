#!/bin/bash

# Run Celery worker
celery -A vectra-connector worker --concurrency=8 -l info &

# Run Celery beat
celery -A vectra-connector beat
