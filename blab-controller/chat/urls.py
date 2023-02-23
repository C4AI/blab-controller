"""Maps request URLs to views."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
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
    path("bots/", views.BotsViewSet.as_view({"get": "list"}), name="bots-view"),
    path(
        "limits/", views.LimitsViewSet.as_view({"get": "retrieve"}), name="limits-view"
    ),
]

urlpatterns = [
    # YOUR PATTERNS
    path("_docs/schema", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path(
        "_docs/schema/swagger-ui",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("", include(router.urls)),
    path("i18n/", include("django.conf.urls.i18n")),
    *paths_without_model,
]
