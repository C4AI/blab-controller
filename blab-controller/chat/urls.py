from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r'conversations', views.ConversationViewSet)
router.register(r'conversations/(?P<conversation_id>[\w-]+)/participants',
                views.ConversationParticipantsViewSet,
                basename='Participant')

urlpatterns = [
    path('', include(router.urls)),
]
