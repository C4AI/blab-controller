"""Celery setttings."""

import os
from pathlib import Path

import dotenv
from celery import Celery

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")

_var = "DJANGO_SETTINGS_MODULE"
if os.getenv(_var, ""):
    module = os.getenv(_var) or ""
    os.environ[_var] = module
else:
    error = f"The environment variable {_var} does not exist."
    raise RuntimeError(error)

app = Celery("controller")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
