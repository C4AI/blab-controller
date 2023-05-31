"""Views for conversations, messages and other related entities."""
from collections import namedtuple
from collections.abc import Iterable, Mapping
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from django.conf import settings
from django.db.models import Model
from django.http import QueryDict
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_serializer,
)
from overrides import overrides
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError, PermissionDenied, ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from . import blab_logger as logger
from .bots import all_bots
from .chats import Chat
from .models import Conversation, Message, Participant
from .serializers import (
    ChatLimitsSerializer,
    ConversationOnListSerializer,
    ConversationSerializer,
    MessageSerializer,
)


class ConversationViewSet(
    CreateModelMixin, RetrieveModelMixin, ListModelMixin, GenericViewSet
):
    """API endpoint that allows access to conversations."""

    queryset = Conversation.objects.all().order_by("name")

    class Meta:
        read_only_fields = ["participants"]

    @overrides
    def get_serializer_class(self) -> type:
        a = getattr(self, "action", None)
        if a == "list":
            return ConversationOnListSerializer
        return ConversationSerializer

    @overrides
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if not getattr(settings, "CHAT_ENABLE_ROOMS", False):
            raise PermissionDenied
        return super().list(request, *args, **kwargs)

    @overrides
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if not getattr(settings, "CHAT_ENABLE_ROOMS", False):
            conversation_id = str(self.get_object().id)
            existing = self.request.session.get(
                "participation_in_conversation", {}
            ).get(conversation_id, None)
            if existing:
                try:
                    Participant.objects.get(pk=existing)
                except Model.DoesNotExist as e:
                    raise PermissionDenied from e
            else:
                raise PermissionDenied

        return super().retrieve(request, *args, **kwargs)

    @overrides
    def perform_create(self, serializer: Serializer, **kwargs: Any) -> None:
        nick_key = "nickname"
        nickname = (
            self.request.data.get(nick_key, None)
            or self.request.session.get(nick_key, None)
            or ""
        )
        if not isinstance(nickname, str):
            error = "nickname must be a string"
            raise ValidationError(error)

        bots_key = "bots"
        bots = self.request.data.get(bots_key, [])
        if not isinstance(bots, list) or any(b for b in bots if not isinstance(b, str)):
            raise ValidationError("Invalid bot array:" + str(bots))

        available_bots = all_bots()
        missing_bots = [b for b in bots if b not in available_bots]
        if missing_bots:
            raise ValidationError("Bot(s) not found: " + str(missing_bots))

        conversation = serializer.save()

        participants = Chat.on_create_conversation(nickname, bots, conversation)

        self.request.session[nick_key] = nickname
        self.request.session.setdefault("participation_in_conversation", {})[
            str(conversation.id)
        ] = str(participants[0].id)
        self.request.session.save()

    @action(detail=True, methods=["post"])
    def join(self, request: Request, pk: Any | None = None) -> Response:
        """Join a conversation.

        Raises:
            ValidationError: if some validation fails
            PermissionDenied: if the user tries to join someone else's conversation

        Args:
            request: the HTTP request
            pk: not used

        Returns:
            the HTTP response
        """
        conversation_id = str(self.get_object().id)
        log = logger.bind(conversation_id=conversation_id)
        log.info("trying to join conversation")
        nick_key = "nickname"
        nickname = (
            request.data.get(nick_key or None)
            or request.session.get(nick_key, None)
            or ""
        )
        if not isinstance(nickname, str):
            error = "nickname must be a string"
            raise ValidationError(error)

        existing = self.request.session.setdefault(
            "participation_in_conversation", {}
        ).get(conversation_id, None)
        p = None
        if existing:
            with suppress(Model.DoesNotExist):
                p = Participant.objects.get(pk=existing)
        if not p:
            if not getattr(settings, "CHAT_ENABLE_ROOMS", False):
                raise PermissionDenied
            p = Chat.get_chat(self.get_object().id).join(nickname)
        participant_id = str(p.id)
        log = log.bind(participant_id=participant_id)
        log.info("joined conversation")
        self.request.session["participation_in_conversation"][
            conversation_id
        ] = participant_id
        self.request.session.save()
        cs = ConversationSerializer(self.get_object(), context={"request": request})
        return Response(cs.data)


class ConversationMessagesViewSet(CreateModelMixin, ListModelMixin, GenericViewSet):
    """API endpoint that allows access to conversation messages."""

    serializer_class = MessageSerializer
    parser_classes = [MultiPartParser, JSONParser]

    @overrides
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Model:
        conversation_id = str(self.kwargs["conversation_id"])
        log = logger.bind(conversation_id=conversation_id)
        log.info("trying to register sent message")
        participant = self._get_participant()
        if not participant:
            raise PermissionDenied

        data: Mapping[str, Any] = request.data
        if isinstance(data, QueryDict):
            data = data.dict()

        return super().create(
            namedtuple("Request", ["data"])(
                {
                    **data,
                    "conversation_id": conversation_id,
                    "sender_id": str(participant.id),
                    "approval_status": Message.ApprovalStatus.AUTOMATICALLY_APPROVED
                    if participant.type == Participant.HUMAN
                    else Message.ApprovalStatus.NO,
                }
            ),
            *args,
            **kwargs,
        )

    def _get_participant(self) -> Participant | None:
        conversation_id = str(self.kwargs["conversation_id"])
        existing = self.request.session.setdefault(
            "participation_in_conversation", {}
        ).get(conversation_id, None)
        if existing:
            try:
                return Participant.objects.get(pk=existing)
            except Participant.DoesNotExist:
                return None
        return None

    @overrides
    def get_queryset(self) -> Iterable[Message]:
        conversation_id = str(self.kwargs["conversation_id"])
        if not self._get_participant():
            raise PermissionDenied
        q = Message.objects.filter(conversation_id=conversation_id).filter(
            approval_status__gt=0
        )
        now = datetime.now(timezone.utc)
        if (until_str := self.request.query_params.get("until")) is not None:
            try:
                until = parse_datetime(until_str)
            except ValueError:
                until = None
            if until is None:
                if until_str == "now":
                    until = now
                else:
                    raise ParseError("Invalid date-time string: " + until_str)
            q = q.exclude(time__gt=until)
        if (since_str := self.request.query_params.get("since")) is not None:
            try:
                since = parse_datetime(since_str)
            except ValueError:
                since = None
            if since is None:
                if since_str == "now":
                    since = now
                else:
                    raise ParseError("Invalid date-time string: " + since_str)
            q = q.exclude(time__lt=since)
        q = q.order_by("-time")
        if (limit_str := self.request.query_params.get("limit")) is not None:
            if limit_str.isdigit():
                q = q[: int(limit_str)]
            else:
                raise ParseError("Invalid limit: " + limit_str)
        return list(reversed(q))


# noinspection PyAbstractClass


@extend_schema_serializer(many=True)
class BotListSerializer(Serializer):
    """Bot list representation."""

    results = SerializerMethodField(
        read_only=True,
    )

    def get_results(self, bots: list[str]) -> list[str]:
        """Return the list of bots given in the argument.

        Args:
            bots: list of bots

        Returns:
            the same list (this is an identity function)
        """
        return bots


class BotsViewSet(APIView):
    """API endpoint that allows access to the list of available bots."""

    serializer_class = BotListSerializer
    action = "list"

    @extend_schema(
        examples=[OpenApiExample("ex1", value={"results": ["Bot1", "Bot2", "Bot3"]})]
    )
    # noinspection PyUnusedLocal
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return the list of bots.

        Args:
            request: ignored
            args: ignored
            kwargs: ignored

        Returns:
            a list of bot names
        """
        return Response(BotListSerializer(list(all_bots().keys())).data)


class LimitsViewSet(APIView):
    """API endpoint that allows access to the chat limits."""

    serializer_class = ChatLimitsSerializer
    action = "list"

    # noinspection PyUnusedLocal, PyMethodMayBeStatic
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return the chat limits.

        Args:
            request: ignored
            args: ignored
            kwargs: ignored

        Returns:
            a dictionary mapping file types to the maximum number of bytes
        """
        data = ChatLimitsSerializer(settings.CHAT_LIMITS).data
        return Response(data)
