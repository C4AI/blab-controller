"""Contains serialising routines."""
from typing import Any, Callable, cast

from django.db.models import Model
from overrides import overrides
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (
    CharField,
    FileField,
    IntegerField,
    SerializerMethodField,
)
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
        return (
            self.context['request']
            .session.setdefault('participation_in_conversation', {})
            .get(str(conversation.id))
        )

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participant_count', 'my_participant_id')


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
        return (
            self.context['request']
            .session.setdefault('participation_in_conversation', {})
            .get(str(conversation.id))
        )

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'created_at', 'participants', 'my_participant_id')
        read_only_fields = ['participants']


class ConditionalFields:
    """Maps field names to conditions."""

    def __init__(self):
        """Create an empty map of field names to conditions."""
        self._conditions = {}

    def __call__(
        self, field_name: str, condition: Callable[[Message | dict[str, Any]], bool]
    ) -> None:
        """Add a field name and its condition.

        Args:
            field_name: name of the field
            condition: function that returns whether the field should be used
                for a given instance
        """
        self._conditions[field_name] = condition

    def __getitem__(
        self, field_name: str
    ) -> Callable[[Message | dict[str, Any]], bool]:
        return self._conditions.get(field_name, lambda m: True)


def _only_type(t: str) -> Callable[[Message | dict[str, Any]], bool]:
    return lambda m: (
        isinstance(m, Message)
        and m.type == t
        or isinstance(m, dict)
        and m.get('type', None) == t
    )


def _only_not_type(t: str) -> Callable[[Message | dict[str, Any]], bool]:
    return lambda m: (
        isinstance(m, Message)
        and m.type != t
        or isinstance(m, dict)
        and m.get('type', None) != t
    )


_only_system = _only_type(Message.MessageType.SYSTEM)
_only_non_system = _only_not_type(Message.MessageType.SYSTEM)


def _only_with_file(m: Message | dict[str, Any]) -> bool:
    t = (
        m.type
        if isinstance(m, Message)
        else m.get('type', None)
        if isinstance(m, dict)
        else None
    )
    return t in [
        Message.MessageType.ATTACHMENT,
        Message.MessageType.VOICE,
        Message.MessageType.AUDIO,
        Message.MessageType.VIDEO,
        Message.MessageType.IMAGE,
    ]


# noinspection PyAbstractClass
class MessageSerializer(ModelSerializer):
    """Serialises messages."""

    conditional = ConditionalFields()

    id = CharField(source='m_id', read_only=True)

    additional_metadata = SerializerMethodField()
    conditional('additional_metadata', _only_system)

    event = CharField(source='text', read_only=True)
    conditional('event', _only_system)

    quoted_message_id = CharField(
        source='quoted_message.m_id', allow_null=True, allow_blank=True, required=False
    )
    conditional('quoted_message_id', _only_non_system)

    sender_id = CharField(read_only=True)
    conditional('sender_id', _only_non_system)

    conditional('local_id', _only_non_system)
    conditional('text', _only_non_system)

    file_url = SerializerMethodField()
    conditional('file_url', _only_with_file)

    file_size = IntegerField(read_only=True)
    conditional('file_size', _only_with_file)

    file = FileField(write_only=True, allow_null=True, required=False)
    conditional('file', _only_with_file)

    def get_file_url(self, message: Message) -> str | None:
        """Return the URL to download the attached file.

        Args:
            message: the instance being serialised

        Returns:
            the attachment URL, or ``None``
            if this message does not have an attached file
        """
        if not _only_with_file(message):
            return None
        if message.file:
            return message.file.url
        return message.external_file_url or None

    def get_additional_metadata(self, message: Message) -> dict[str, Any] | None:
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
    def create(self, validated_data: dict[str, Any]) -> Model:
        message_type = validated_data.get('type', None)
        if message_type == Message.MessageType.SYSTEM:
            raise ValidationError({'type': ['You cannot create system messages.']})
        return Message.objects.create(**validated_data)

    @overrides
    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        delete = [f for f in data if not MessageSerializer.conditional[f](data)]
        for f in delete:
            data.pop(f, None)
        d = super().to_internal_value(data)

        quoted_message_m_id = d.pop('quoted_message', {}).get('m_id', None)
        quoted_message = None
        if quoted_message_m_id:
            try:
                quoted_message = Message.objects.get(m_id=quoted_message_m_id)
            except Message.DoesNotExist:
                raise ValidationError(
                    {'quoted_message_id': ['The quoted message does not exist.']}
                )
        d['quoted_message_id'] = quoted_message.id if quoted_message else None

        if _only_with_file(data):
            if attachment := data.get('file', None):
                d['file_size'] = attachment.size
            if external_url := data.get('external_file_url', None):
                d['external_file_url'] = external_url

        # these fields are filled by the controller's code
        d['conversation_id'] = data['conversation_id']
        d['sender_id'] = data['sender_id']
        return d

    @overrides
    def to_representation(self, instance: Message) -> dict[str, Any]:
        result = super().to_representation(instance)
        delete = [f for f in result if not MessageSerializer.conditional[f](instance)]
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
            'sender_id',
            'local_id',
            'text',
            # messages with included files
            'file',
            'file_url',
            'file_size',
        )
