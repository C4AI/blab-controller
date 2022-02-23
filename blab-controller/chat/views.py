"""Views for conversations, messages and other related entities."""

from datetime import datetime, timezone
from typing import Any, Iterable

from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.utils.dateparse import parse_datetime
from overrides import overrides
from rest_framework.decorators import action
from rest_framework.exceptions import (ParseError, PermissionDenied,
                                       ValidationError)
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin, UpdateModelMixin)
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer
from rest_framework.viewsets import GenericViewSet

from .bots import all_bots
from .models import Conversation, Message, Participant
from .serializers import (ConversationOnListSerializer, ConversationSerializer,
                          MessageSerializer, ParticipantSerializer)


class ConversationViewSet(CreateModelMixin, RetrieveModelMixin, ListModelMixin,
                          GenericViewSet):
    """API endpoint that allows access to conversations."""

    queryset = Conversation.objects.all().order_by('name')

    class Meta:
        read_only_fields = ['participants']

    @overrides
    def get_serializer_class(self) -> type:
        a = getattr(self, 'action', None)
        if a == 'list':
            return ConversationOnListSerializer
        else:
            return ConversationSerializer

    @overrides
    def list(self, request: HttpRequest, *args: Any,
             **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @overrides
    def perform_create(self, serializer: Serializer) -> None:
        nick_key = 'nickname'
        nickname = (self.request.data.get(nick_key, None)
                    or self.request.session.get(nick_key, None) or '')
        if not isinstance(nickname, str):
            raise ValidationError('nickname must be a string')

        bots_key = 'bots'
        bots = self.request.data.get(bots_key, [])
        if not isinstance(bots, list) or any(
                b for b in bots if not isinstance(b, str)):
            raise ValidationError('Invalid bot array:' + str(bots))
        available_bots = all_bots()
        missing_bots = [b for b in bots if b not in available_bots]
        if missing_bots:
            raise ValidationError('Bot(s) not found: ' + str(missing_bots))

        conversation = serializer.save()
        conversation_created_msg = Message(
            conversation=conversation,
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.CREATED,
        )
        conversation_created_msg.save()

        participant = Participant.objects.create(conversation=conversation,
                                                 type=Participant.HUMAN,
                                                 name=nickname)

        self.request.session[nick_key] = nickname
        self.request.session.setdefault('participation_in_conversation',
                                        {})[str(conversation.id)] = str(
                                            participant.id)
        self.request.session.save()

        if not nickname:
            nickname = 'ANON_' + str(participant.id)
            participant.name = nickname
        participant.save()

        for b in bots:
            bot_participant = Participant.objects.create(
                conversation=conversation, type=Participant.BOT, name=b)
            bot_joined_msg = Message(
                conversation=conversation,
                type=Message.MessageType.SYSTEM,
                text=Message.SystemEvent.JOINED,
                additional_metadata={
                    'participant_id': str(bot_participant.id),
                },
            )
            bot_joined_msg.save()

    @action(detail=True, methods=['post'])
    def join(self, request: HttpRequest, pk: Any | None = None) -> Response:
        """Join a conversation.

        Raises:
            ValidationError: if some validation fails

        Args:
            request: the HTTP request
            pk: not used

        Returns:
            the HTTP response
        """
        nick_key = 'nickname'
        nickname = (request.data.get(nick_key or None)
                    or request.session.get(nick_key, None) or '')
        if not isinstance(nickname, str):
            raise ValidationError('nickname must be a string')
        conversation_id = str(self.get_object().id)
        existing = self.request.session.setdefault(
            'participation_in_conversation', {}).get(conversation_id, None)
        p = None
        if existing:
            try:
                p = Participant.objects.get(pk=existing)
            except Model.DoesNotExist:
                pass
        if not p:
            p = Participant.objects.create(conversation=self.get_object(),
                                           type=Participant.HUMAN,
                                           name=nickname)
            p.save()
        participant_id = str(p.id)
        self.request.session['participation_in_conversation'][
            conversation_id] = participant_id
        self.request.session.save()
        cs = ConversationSerializer(self.get_object(),
                                    context={'request': request})
        return Response(cs.data)


class ConversationParticipantsViewSet(ListModelMixin, UpdateModelMixin,
                                      RetrieveModelMixin, GenericViewSet):
    """API endpoint that allows access to conversation participants."""

    serializer_class = ParticipantSerializer

    @overrides
    def get_queryset(self) -> QuerySet:
        return Participant.objects.filter(
            conversation=self.kwargs.get('conversation_id'))


class ConversationMessagesViewSet(ListModelMixin, GenericViewSet):
    """API endpoint that allows access to conversation messages."""

    serializer_class = MessageSerializer

    @overrides
    def get_queryset(self) -> Iterable[Message]:
        conversation_id = str(self.kwargs['conversation_id'])
        existing = self.request.session.setdefault(
            'participation_in_conversation', {}).get(conversation_id, None)
        p = None
        if existing:
            try:
                p = Participant.objects.get(pk=existing)
            except Model.DoesNotExist:
                pass
        if not p:
            raise PermissionDenied('You are not in this conversation.')
        q = Message.objects.filter(conversation_id=conversation_id)
        now = datetime.now(timezone.utc)
        if (until_str := self.request.query_params.get('until')) is not None:
            try:
                until = parse_datetime(until_str)
            except ValueError:
                until = None
            if until is None:
                if until_str == 'now':
                    until = now
                else:
                    raise ParseError('Invalid date-time string: ' + until_str)
            q = q.exclude(time__gt=until)
        if (since_str := self.request.query_params.get('since')) is not None:
            try:
                since = parse_datetime(since_str)
            except ValueError:
                since = None
            if since is None:
                if since_str == 'now':
                    since = now
                else:
                    raise ParseError('Invalid date-time string: ' + since_str)
            q = q.exclude(time__lt=since)
        q = q.order_by('-time')
        if (limit_str := self.request.query_params.get('limit')) is not None:
            if limit_str.isdigit():
                q = q[:int(limit_str)]
            else:
                raise ParseError('Invalid limit: ' + limit_str)
        return list(reversed(q))


class BotsViewSet(ListModelMixin, GenericViewSet):
    """API endpoint that allows access to the list of available bots."""

    # noinspection PyAbstractClass
    class Identity(BaseSerializer):

        @overrides
        def to_representation(self, instance: str) -> str:
            return instance

    serializer_class = Identity

    queryset = list(all_bots().keys())
