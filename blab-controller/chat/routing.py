from django.urls import re_path

from . import consumers

websockets_urlpatterns = [
    re_path(r'ws/chat/(?P<conversation_id>[a-zA-Z0-9_-]+)/$',
            consumers.ConversationConsumer.as_asgi()),
]
