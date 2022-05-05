"""Package that deals with the conversation tasks."""

from typing import Any

import structlog
from django.dispatch import receiver
from django_structlog.signals import bind_extra_request_metadata
from rest_framework.request import Request

blab_logger = structlog.get_logger('blab_controller')


@receiver(bind_extra_request_metadata)
def _bind_session_key(request: Request, logger: Any, **kwargs: Any) -> None:
    logger.bind(session_key=request.session.session_key)
