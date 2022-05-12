"""Chat app configuration."""
from django.apps import AppConfig
from overrides import overrides


class ChatConfig(AppConfig):
    """Chat configuration."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    @overrides
    def ready(self) -> None:
        super().ready()
        # noinspection PyUnresolvedReferences
        from . import signals  # noqa: F401
