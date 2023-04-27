#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

import dotenv


def main() -> None:
    """Run administrative tasks."""
    _var = "DJANGO_SETTINGS_MODULE"
    if os.getenv(_var, ""):
        module = os.getenv(_var) or ""
        os.environ[_var] = module
    else:
        error = f"The environment variable {_var} does not exist."
        raise RuntimeError(error)
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


dotenv.load_dotenv(Path(__file__).parent / ".env", verbose=True)

if __name__ == "__main__":
    main()
