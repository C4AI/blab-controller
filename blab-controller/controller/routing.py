import chat.routing
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.sessions import SessionMiddlewareStack

application = ProtocolTypeRouter({
    'websocket':
    SessionMiddlewareStack(URLRouter(chat.routing.websockets_urlpatterns)),
})
