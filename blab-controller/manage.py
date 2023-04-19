#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

import dotenv


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controller.settings.prod")
    if os.getenv("DJANGO_SETTINGS_MODULE"):
        module = os.getenv("DJANGO_SETTINGS_MODULE") or ""
        os.environ["DJANGO_SETTINGS_MODULE"] = module
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        error = (
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
        raise ImportError(error) from exc
    execute_from_command_line(sys.argv)


dotenv.load_dotenv(Path(__file__).parent / ".env")

if __name__ == "__main__":
    main()
