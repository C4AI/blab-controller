"""
WSGI config for controller project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

from pathlib import Path

from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / '.env')

application = get_wsgi_application()
