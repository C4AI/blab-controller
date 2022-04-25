"""Maps request URLs to views."""
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework import routers
from rest_framework.schemas import get_schema_view

from . import views

router = routers.DefaultRouter()
router.register(r'conversations', views.ConversationViewSet)
router.register(
    r'conversations/(?P<conversation_id>[\w-]+)/participants',
    views.ConversationParticipantsViewSet,
    basename='Participant',
)
router.register(
    r'conversations/(?P<conversation_id>[\w-]+)/messages',
    views.ConversationMessagesViewSet,
    basename='Message',
)

paths_without_model = [
    path('bots/', views.BotsViewSet.as_view({'get': 'list'}), name='bots-view'),
    path(
        'limits/', views.LimitsViewSet.as_view({'get': 'retrieve'}), name='limits-view'
    ),
]

urlpatterns = [
    path(
        r'_docs/',
        TemplateView.as_view(
            template_name='swagger-ui.html',
            extra_context={'schema_url': 'openapi-schema'},
        ),
        name='swagger-ui',
    ),
    path(
        r'_openapi-schema/',
        get_schema_view(
            title="BLAB Controller",
            description="REST API for BLAB Controller",
            version="0.0.1",
            public=True,
        ),
        name='openapi-schema',
    ),
    path('', include(router.urls)),
    path('i18n/', include('django.conf.urls.i18n')),
    *paths_without_model,
]
