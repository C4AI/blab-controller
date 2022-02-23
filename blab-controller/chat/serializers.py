"""Contains serialising routines."""
from typing import Any, Callable, cast

from overrides import overrides
from rest_framework.fields import CharField, SerializerMethodField
from rest_framework.serializers import ModelSerializer

from .models import Conversation, Message, Participant


class ConversationOnListSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participant_count = SerializerMethodField()
    my_participant_id = SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_participant_count(self, conversation: Conversation) -> int:
        """Count the number of participants in the conversation.

        Args:
            conversation: the conversation

        Returns:
            how many participants there are in the conversation
        """
        return cast(int, conversation.participants.count())

    def get_my_participant_id(self, conversation: Conversation) -> str | None:
        """Return the participant id of the user in the conversation.

        Args:
            conversation: the conversation

        Returns:
            the participant id in the conversation, or `None` if the
            session is not connected to the conversation
        """
        return self.context['request'].session.setdefault(
            'participation_in_conversation', {}).get(str(conversation.id))

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participant_count',
                  'my_participant_id')


class ParticipantSerializer(ModelSerializer):
    """Serialises a Participant instance."""

    class Meta:
        model = Participant
        fields = ('id', 'name', 'type')
        read_only_fields = ('id', 'type')


class ConversationSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participants = ParticipantSerializer(many=True, read_only=True)
    my_participant_id = SerializerMethodField()

    def get_my_participant_id(self, conversation: Conversation) -> str | None:
        """Return the participant id of the user in the conversation.

        Args:
            conversation: the conversation

        Returns:
            the participant id in the conversation, or `None` if the
            session is not connected to the conversation
        """
        return self.context['request'].session.setdefault(
            'participation_in_conversation', {}).get(str(conversation.id))

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participants',
                  'my_participant_id')
        read_only_fields = ['participants']


class ConditionalFields:
    """Maps field names to conditions."""

    def __init__(self):
        """Create an empty map of field names to conditions."""
        self._conditions = {}

    def __call__(self, field_name: str, condition: Callable[[Message],
                                                            bool]) -> None:
        """Add a field name and its condition."""
        self._conditions[field_name] = condition

    def __getitem__(self, field_name: str) -> Callable[[Message], bool]:
        return self._conditions.get(field_name, lambda m: True)


def _only_type(t: str) -> Callable[[Message], bool]:
    return lambda m: isinstance(m, Message) and m.type == t


def _only_not_type(t: str) -> Callable[[Message], bool]:
    return lambda m: isinstance(m, Message) and m.type != t


_only_system = _only_type(Message.MessageType.SYSTEM)
_only_non_system = _only_not_type(Message.MessageType.SYSTEM)


# noinspection PyAbstractClass
class MessageSerializer(ModelSerializer):
    """Serialises messages."""

    conditional = ConditionalFields()

    id = CharField(source='m_id')

    additional_metadata = SerializerMethodField()
    conditional('additional_metadata', _only_system)

    event = CharField(source='text', read_only=True)
    conditional('event', _only_system)

    quoted_message_id = CharField(source='quoted_message.m_id',
                                  allow_null=True)
    conditional('quoted_message_id', _only_non_system)

    sender = ParticipantSerializer()
    conditional('sender', _only_non_system)

    conditional('local_id', _only_non_system)
    conditional('text', _only_non_system)

    def get_additional_metadata(self,
                                message: Message) -> dict[str, Any] | None:
        """Return additional metadata (only for system messages).

        Args:
            message: the instance being serialised

        Returns:
            the additional metadata of the system message, or ``None``
            if this is not a system message
        """
        if message.type == Message.MessageType.SYSTEM:
            return message.additional_metadata
        return None

    @overrides
    def to_representation(self, instance: Message) -> dict[str, Any]:
        result = super().to_representation(instance)
        delete = [
            f for f in result if not MessageSerializer.conditional[f](instance)
        ]
        for f in delete:
            result.pop(f, None)
        return result

    class Meta:
        model = Message
        fields = (
            # all messages
            'type',
            'time',
            'id',
            # system messages
            'event',
            'additional_metadata',
            # non-system messages
            'quoted_message_id',
            'sender',
            'local_id',
            'text',
        )
