#!/bin/bash

cd "$(dirname "$0")"
(
    trap "kill 0" SIGINT;
    celery -A controller worker -l INFO &
    python manage.py runserver
)
