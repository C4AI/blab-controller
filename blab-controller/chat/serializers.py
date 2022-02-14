from typing import Any, OrderedDict, cast

from rest_framework.fields import CharField, JSONField, SerializerMethodField
from rest_framework.serializers import BaseSerializer, ModelSerializer

from .models import Conversation, Message, Participant


class ConversationOnListSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participant_count = SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_participant_count(self, obj: Conversation) -> int:
        return cast(int, obj.participants.count())

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participant_count')


class ConversationSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participants')
        read_only_fields = ['participants']


class ParticipantSerializer(ModelSerializer):
    """Serialises a Participant instance."""

    class Meta:
        model = Participant
        fields = ('id', 'name', 'is_present', 'type')


class SystemMessageSerializer(ModelSerializer):
    """Serialises system messages."""

    id = CharField(source='m_id')
    event = CharField(source='text')
    data = JSONField(source='additional_metadata')

    class Meta:
        model = Message
        fields = ('type', 'time', 'id', 'event', 'data')


class TextMessageSerializer(ModelSerializer):
    """Serialises text messages."""

    id = CharField(source='m_id')
    quoted_message_id = CharField(source='quoted_message.m_id',
                                  allow_null=True)

    sender = ParticipantSerializer()

    class Meta:
        model = Message
        fields = ('type', 'time', 'local_id', 'id', 'sender', 'text',
                  'quoted_message_id')


# noinspection PyAbstractClass
class MessageSerializer(BaseSerializer):
    """Serialises messages."""

    @classmethod
    def _get_serializer_for_instance(cls, instance: Any) -> BaseSerializer:
        if instance.type == Message.MessageType.SYSTEM:
            return SystemMessageSerializer(instance)
        if instance.type == Message.MessageType.TEXT:
            return TextMessageSerializer(instance)
        raise NotImplementedError

    def to_representation(self,
                          instance: Message) -> OrderedDict[Any, Any | None]:
        serializer = self._get_serializer_for_instance(instance)
        return cast(OrderedDict[Any, Any | None],
                    serializer.to_representation(instance))
