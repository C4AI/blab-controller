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
                                   RetrieveModelMixin)
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

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
        nickname = (self.request.data.get(nick_key or None)
                    or self.request.session.get(nick_key, None) or '')
        if not isinstance(nickname, str):
            raise ValidationError('nickname must be a string')

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

    @overrides
    def create(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        resp = super().create(request, *args, **kwargs)
        participant_id = self.request.session.setdefault(
            'participation_in_conversation', {}).get(resp.data['id'])
        return Response(
            {
                'conversation': resp.data,
                'my_participant_id': participant_id
            },
            status=resp.status_code,
            headers=resp.headers)

    @action(detail=True, methods=['post'])
    def join(self, request: HttpRequest) -> Response:
        """Join a conversation.

        Raises:
            ValidationError: if some validation fails

        Args:
            request: the HTTP request

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
        cs = ConversationSerializer(self.get_object())
        return Response({
            'conversation': cs.data,
            'my_participant_id': participant_id
        })


class ConversationParticipantsViewSet(ListModelMixin, GenericViewSet):
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
