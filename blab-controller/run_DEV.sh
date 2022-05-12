#!/bin/bash

cd "$(dirname "$0")"
(
    trap "kill 0" SIGINT;
    redis-server controller/settings/redis.conf &
    celery -A controller worker -l INFO &
    poetry run python manage.py runserver
)
