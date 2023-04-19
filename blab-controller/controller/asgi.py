"""ASGI config for controller project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

from pathlib import Path

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

asgi_app = get_asgi_application()

if asgi_app:  # we cannot import before get_asgi_application()
    import chat.routing

    application = ProtocolTypeRouter(
        {
            "http": asgi_app,
            "websocket": AuthMiddlewareStack(
                URLRouter(chat.routing.websockets_urlpatterns)
            ),
        }
    )
else:
    application = None
