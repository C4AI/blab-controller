"""Contains serialising routines."""
from collections.abc import Callable
from typing import Any, cast

from django.conf import settings
from django.db import transaction
from django.db.models import Model
from django.utils.translation import gettext_lazy as gettext
from django.utils.translation import pgettext_lazy as pgettext
from overrides import overrides
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.fields import (
    CharField,
    FileField,
    IntegerField,
    SerializerMethodField,
)
from rest_framework.serializers import ModelSerializer, Serializer

from .models import Conversation, Message, MessageOption, Participant


class ConversationOnListSerializer(ModelSerializer):
    """Conversation representation."""

    participant_count = SerializerMethodField(
        help_text=gettext("the number of participants in the conversation")
    )
    my_participant_id = SerializerMethodField(
        help_text=gettext(
            "the participant id that belongs to the requesting user "
            "in the conversation, if any"
        )
    )

    # noinspection PyMethodMayBeStatic
    def get_participant_count(self, conversation: Conversation) -> int:
        """Count the number of participants in the conversation.

        Args:
        ----
            conversation: the conversation

        Returns:
        -------
            how many participants there are in the conversation
        """
        return cast(int, conversation.participants.count())

    def get_my_participant_id(self, conversation: Conversation) -> str | None:
        """Return the participant id of the user in the conversation.

        Args:
        ----
            conversation: the conversation

        Returns:
        -------
            the participant id in the conversation, or `None` if the
            session is not connected to the conversation
        """
        return (
            self.context["request"]
            .session.setdefault("participation_in_conversation", {})
            .get(str(conversation.id))
        )

    class Meta:
        model = Conversation
        fields = ("id", "name", "created_at", "participant_count", "my_participant_id")


class ParticipantSerializer(ModelSerializer):
    """Participant representation."""

    class Meta:
        model = Participant
        fields = ("id", "name", "type")
        read_only_fields = ("id", "type")


class ConversationSerializer(ModelSerializer):
    """Serialises a Conversation instance."""

    participants = ParticipantSerializer(
        many=True, read_only=True, help_text=gettext("participants in the conversation")
    )

    my_participant_id = SerializerMethodField(
        help_text=gettext(
            "the participant id that belongs to the requesting user "
            "in the conversation, if any"
        )
    )

    def get_my_participant_id(self, conversation: Conversation) -> str | None:
        """Return the participant id of the user in the conversation.

        Args:
        ----
            conversation: the conversation

        Returns:
        -------
            the participant id in the conversation, or `None` if the
            session is not connected to the conversation
        """
        return (
            self.context["request"]
            .session.setdefault("participation_in_conversation", {})
            .get(str(conversation.id))
        )

    class Meta:
        model = Conversation
        fields = ("id", "name", "created_at", "participants", "my_participant_id")
        read_only_fields = ["participants"]


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
        ----
            field_name: name of the field
            condition: function that returns whether the field should be used
                for a given instance
        """
        self._conditions[field_name] = condition

    def __getitem__(
        self, field_name: str
    ) -> Callable[[Message | dict[str, Any]], bool]:
        return self._conditions.get(field_name, lambda _m: True)


def _only_type(t: str) -> Callable[[Message | dict[str, Any]], bool]:
    return lambda m: (
        isinstance(m, Message)
        and m.type == t
        or isinstance(m, dict)
        and m.get("type", None) == t
    )


def _only_not_type(t: str) -> Callable[[Message | dict[str, Any]], bool]:
    return lambda m: (
        isinstance(m, Message)
        and m.type != t
        or isinstance(m, dict)
        and m.get("type", None) != t
    )


_only_system = _only_type(Message.MessageType.SYSTEM)
_only_non_system = _only_not_type(Message.MessageType.SYSTEM)


def _only_with_options(m: Message | dict[str, Any]) -> bool:
    return (
        isinstance(m, Message)
        and m.options
        or isinstance(m, dict)
        and bool(m.get("options", []))
    )


def _only_with_file(m: Message | dict[str, Any]) -> bool:
    t = (
        m.type
        if isinstance(m, Message)
        else m.get("type", None)
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


class MessageOptionSerializer(ModelSerializer):
    """Message option representation."""

    @overrides
    def to_internal_value(self, data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, str):
            return {"option_text": data, "position": 0}
        return data

    class Meta:
        model = MessageOption
        fields = ("option_text", "position")


# noinspection PyAbstractClass,PyMethodMayBeStatic
class MessageSerializer(ModelSerializer):
    """Message representation."""

    conditional = ConditionalFields()

    id = CharField(
        source="m_id", read_only=True, help_text=Message.m_id.field.help_text
    )

    sent_by_human = SerializerMethodField(
        read_only=True,
        help_text=gettext("whether the message was sent by a human user"),
    )

    additional_metadata = SerializerMethodField(
        help_text=Message.additional_metadata.field.help_text
    )
    conditional("additional_metadata", _only_system)

    event = CharField(
        source="text",
        read_only=True,
        help_text=gettext("event type (for system messages)"),
    )
    conditional("event", _only_system)

    quoted_message_id = CharField(
        source="quoted_message.m_id",
        allow_null=True,
        allow_blank=True,
        required=False,
        help_text=(
            pgettext("message", "id of %s") % Message.quoted_message.field.help_text
        ),
    )
    conditional("quoted_message_id", _only_non_system)

    sender_id = CharField(
        read_only=True,
        help_text=(
            pgettext("sender", "id of %s") % Message.quoted_message.field.help_text
        ),
    )
    conditional("sender_id", _only_non_system)

    conditional("local_id", _only_non_system)
    conditional("text", _only_non_system)

    file_url = SerializerMethodField(
        help_text=(
            gettext("the address from which the attached file can be downloaded")
        ),
    )
    conditional("file_url", _only_with_file)

    file_size = IntegerField(
        read_only=True,
        help_text=(
            gettext(
                "the size of the attached file "
                "(it may not be set for externally-hosted files)"
            )
        ),
    )
    conditional("file_size", _only_with_file)

    file_name = SerializerMethodField(
        help_text=(
            gettext(
                "the original name of the file "
                "(it may not be set for externally-hosted files)"
            )
        ),
    )
    conditional("file_name", _only_with_file)

    file = FileField(
        write_only=True,
        allow_null=True,
        required=False,
        help_text=gettext("the file attached to the message"),
    )
    conditional("file", _only_with_file)

    options = MessageOptionSerializer(many=True, required=False)
    conditional("options", _only_with_options)

    def get_file_url(self, message: Message) -> str | None:
        """Return the URL to download the attached file.

        Args:
        ----
            message: the instance being serialised

        Returns:
        -------
            the attachment URL, or ``None``
            if this message does not have an attached file
        """
        if not _only_with_file(message):
            return None
        if message.file:
            return message.file.url
        return message.external_file_url or None

    def get_sent_by_human(self, message: Message) -> bool:
        """Return True if the message sender is human.

        Returns
        -------
            True if the message was sent by a person, False otherwise
        """
        return message.sent_by_human()

    def get_file_name(self, message: Message) -> str | None:
        """Return the original name of the attached file.

        Args:
        ----
            message: the instance being serialised

        Returns:
        -------
            the attachment name, or ``None``
            if this message does not have an attached file
        """
        if not _only_with_file(message):
            return None
        if message.file:
            return message.original_file_name
        if message.external_file_url:
            return message.external_file_url.rsplit("?", 1)[0].rsplit("/", 1)[-1]
        return None

    def get_additional_metadata(self, message: Message) -> dict[str, Any] | None:
        """Return additional metadata (only for system messages).

        Args:
        ----
            message: the instance being serialised

        Returns:
        -------
            the additional metadata of the system message, or ``None``
            if this is not a system message
        """
        if message.type == Message.MessageType.SYSTEM:
            return message.additional_metadata
        return None

    @overrides
    def create(self, validated_data: dict[str, Any]) -> Model:
        message_type = validated_data.get("type", None)
        if message_type == Message.MessageType.SYSTEM:
            raise ValidationError({"type": ["You cannot create system messages."]})
        options = validated_data.pop("options", None) or []

        limits = getattr(settings, "CHAT_LIMITS", {})
        if f := validated_data.get("file", None):
            match message_type:
                case Message.MessageType.ATTACHMENT:
                    limit = limits.get("MAX_ATTACHMENT_SIZE", 0)
                case Message.MessageType.AUDIO:
                    limit = limits.get("MAX_AUDIO_SIZE", 0)
                case Message.MessageType.VIDEO:
                    limit = limits.get("MAX_VIDEO_SIZE", 0)
                case Message.MessageType.IMAGE:
                    limit = limits.get("MAX_IMAGE_SIZE", 0)
                case Message.MessageType.VOICE:
                    limit = limits.get("MAX_VOICE_SIZE", 0)
                case _:
                    limit = 0
            if f.size > limit:
                error = f"MAX = {limit}"
                raise APIException(error, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        with transaction.atomic():
            message = Message.objects.create(**validated_data)
            for option in options:
                MessageOption.objects.create(message=message, **option)
            message.refresh_from_db()
        return message

    @overrides
    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        delete = [f for f in data if not MessageSerializer.conditional[f](data)]
        for f in delete:
            data.pop(f, None)
        d = super().to_internal_value(data)

        quoted_message_m_id = d.pop("quoted_message", {}).get("m_id", None)
        quoted_message = None
        if quoted_message_m_id:
            try:
                quoted_message = Message.objects.get(m_id=quoted_message_m_id)
            except Message.DoesNotExist as e:
                raise ValidationError(
                    {"quoted_message_id": ["The quoted message does not exist."]}
                ) from e
        d["quoted_message_id"] = quoted_message.id if quoted_message else None

        if _only_with_file(data):
            if attachment := data.get("file", None):
                d["file_size"] = attachment.size
                d["mime_type"] = attachment.content_type
                d["original_file_name"] = attachment.name
            if external_url := data.get("external_file_url", None):
                d["external_file_url"] = external_url

        # these fields are filled by the controller's code
        d["conversation_id"] = data["conversation_id"]
        d["sender_id"] = data["sender_id"]
        d["options"] = []
        d["approval_status"] = data.get("approval_status", Message.ApprovalStatus.NO)
        for i, o in enumerate(data.get("options", None) or []):
            d["options"].append({"option_text": str(o), "position": i + 1})
        return d

    @overrides
    def to_representation(self, instance: Message) -> dict[str, Any]:
        result = super().to_representation(instance)
        delete = [f for f in result if not MessageSerializer.conditional[f](instance)]
        for f in delete:
            result.pop(f, None)
        if "options" in result:
            result["options"] = [o["option_text"] for o in result["options"]]
        return result

    class Meta:
        model = Message
        fields = (
            # all messages
            "type",
            "time",
            "id",
            "sent_by_human",
            # system messages
            "event",
            "additional_metadata",
            # non-system messages
            "quoted_message_id",
            "sender_id",
            "local_id",
            "text",
            # messages with included files
            "file",
            "file_url",
            "file_size",
            "file_name",
            # options
            "options",
        )

    @classmethod
    def create_message(cls, message_data: dict[str, Any]) -> Message | None:
        """Create a message and save it to the database.

        Args:
        ----
            message_data: message parameters and data

        Raises:
        ------
            ValidationError: if validation fails

        Returns:
        -------
            the new instance of :cls:`Message` if it was saved successfully,
            or ``None`` if it was not saved because it is duplicate (same
            ``local_id`` and sender as an existing message).
        """
        try:
            serializer = MessageSerializer(data=message_data)
            serializer.is_valid(raise_exception=True)
            message = serializer.save()
        except ValidationError as e:
            err = getattr(e, "error_dict", {}).get("__all__", [])
            if len(err) == 1 and getattr(err[0], "code", None) == "unique_together":
                chk = getattr(err[0], "params", {}).get("unique_check", ())
                if set(chk) == {"conversation", "sender", "local_id"}:
                    # Ignore duplicate message
                    return None
            raise
        return cast(Message, message)


# noinspection PyAbstractClass
class ChatLimitsSerializer(Serializer):
    """Chat limits representation."""

    MAX_ATTACHMENT_SIZE = IntegerField(
        required=False,
        default=0,
        help_text=gettext("maximum size of an attached file (in bytes)"),
    )

    MAX_IMAGE_SIZE = IntegerField(
        required=False,
        default=0,
        help_text=gettext("maximum size of an image file (in bytes)"),
    )

    MAX_VIDEO_SIZE = IntegerField(
        required=False,
        default=0,
        help_text=gettext("maximum size of a video file (in bytes)"),
    )

    MAX_AUDIO_SIZE = IntegerField(
        required=False,
        default=0,
        help_text=gettext("maximum size of an audio file (in bytes)"),
    )

    MAX_VOICE_SIZE = IntegerField(
        required=False,
        default=0,
        help_text=gettext("maximum size of a voice recording file (in bytes)"),
    )
