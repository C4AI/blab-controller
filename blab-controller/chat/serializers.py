"""Contains serialising routines."""
from typing import Any, OrderedDict, cast

from overrides import overrides
from rest_framework.fields import CharField, SerializerMethodField
from rest_framework.serializers import BaseSerializer, ModelSerializer

from .models import Conversation, Message, Participant


class ConversationOnListSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participant_count = SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_participant_count(self, conversation: Conversation) -> int:
        """Count the number of participants in the conversation.

        Args:
            conversation: the conversation

        Returns:
            how many participants there are in the conversation
        """
        return cast(int, conversation.participants.count())

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participant_count')


class ParticipantSerializer(ModelSerializer):
    """Serialises a Participant instance."""

    class Meta:
        model = Participant
        fields = ('id', 'name', 'type')


class ConversationSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participants = ParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participants')
        read_only_fields = ['participants']


class SystemMessageSerializer(ModelSerializer):
    """Serialises system messages."""

    id = CharField(source='m_id')
    event = CharField(source='text')

    class Meta:
        model = Message
        fields = ('type', 'time', 'id', 'event', 'additional_metadata')


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

    @overrides
    def to_representation(self,
                          instance: Message) -> OrderedDict[Any, Any | None]:
        serializer = self._get_serializer_for_instance(instance)
        return cast(OrderedDict[Any, Any | None],
                    serializer.to_representation(instance))
