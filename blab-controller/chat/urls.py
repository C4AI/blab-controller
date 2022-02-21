"""Maps request URLs to views."""
from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r'conversations', views.ConversationViewSet)
router.register(r'conversations/(?P<conversation_id>[\w-]+)/participants',
                views.ConversationParticipantsViewSet,
                basename='Participant')
router.register(r'conversations/(?P<conversation_id>[\w-]+)/messages',
                views.ConversationMessagesViewSet,
                basename='Message')

urlpatterns = [
    path('', include(router.urls)),
]
