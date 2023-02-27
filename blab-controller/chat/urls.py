"""Maps request URLs to views."""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"conversations", views.ConversationViewSet)

router.register(
    r"conversations/(?P<conversation_id>[\w-]+)/messages",
    views.ConversationMessagesViewSet,
    basename="Message",
)

paths_without_model = [
    path("bots/", views.BotsViewSet.as_view(), name="bots-view"),
    path("limits/", views.LimitsViewSet.as_view(), name="limits-view"),
]

urlpatterns = [
    path("_docs/schema.yaml", SpectacularAPIView.as_view(), name="schema"),
    path(
        "_docs/schema/swagger-ui",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "_docs/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("", include(router.urls)),
    path("i18n/", include("django.conf.urls.i18n")),
    *paths_without_model,
]
