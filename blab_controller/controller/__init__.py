"""BLAB Controller - core package."""

from .celery import app as celery_app

__all__ = ("celery_app",)
