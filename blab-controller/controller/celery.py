"""Celery setttings."""

import os
from pathlib import Path

import dotenv
from celery import Celery

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controller.settings.prod")
if os.getenv("DJANGO_SETTINGS_MODULE"):
    module = os.getenv("DJANGO_SETTINGS_MODULE") or ""
    os.environ["DJANGO_SETTINGS_MODULE"] = module

app = Celery("controller")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
