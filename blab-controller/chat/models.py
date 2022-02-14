"""Conversation - data models."""

import shlex
import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as gettext
from django.utils.translation import pgettext_lazy as pgettext
from overrides import overrides


class Conversation(models.Model):
    """Represents a chat conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    "Conversation ID (32 characters)"

    name = models.CharField(pgettext('conversation name', 'name'),
                            max_length=50,
                            blank=True,
                            null=True)
    """Conversation name"""

    created_at = models.DateTimeField(gettext('time'), auto_now_add=True)
    """When the conversation started"""

    class Meta:
        verbose_name = gettext('conversation')
        verbose_name_plural = gettext('conversations')


class Participant(models.Model):
    """Represents a chat participant (person or bot)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    "Participant ID (32 characters)"

    name = models.CharField(
        gettext('participant'),
        max_length=50,
    )
    """Participant name"""

    is_present = models.BooleanField(gettext('is present'))
    """Whether the participant is still in the conversation"""

    HUMAN = 'H'
    BOT = 'B'
    TYPE_CHOICES = [
        (HUMAN, gettext('human')),
        (BOT, gettext('bot')),
    ]
    type = models.CharField(
        gettext('type'),
        max_length=1,
        choices=TYPE_CHOICES,
        default=None,
    )
    """Participant type (human, bot)"""

    conversation = models.ForeignKey(Conversation,
                                     on_delete=models.PROTECT,
                                     verbose_name=pgettext(
                                         'conversation', 'participants'),
                                     related_name='participants')

    class Meta:
        verbose_name = gettext('participant')
        verbose_name_plural = gettext('participants')

    def __repr__(self) -> str:
        # noinspection PyTypeChecker
        return f'Participant({self.id}, name={shlex.quote(self.name)})'

    __str__ = __repr__


class Message(models.Model):
    """Represents a message in a conversation."""

    m_id = models.UUIDField(unique=True,
                            default=uuid.uuid4,
                            editable=False,
                            db_index=True)
    """Message ID (32 characters)

    A numerical ID is still used internally as a primary key,
    but it is not exposed to the users.
    """

    class MessageType(models.TextChoices):
        SYSTEM = ('S', gettext('System'))
        TEXT = ('T', gettext('Text'))
        VOICE = ('V', gettext('Voice'))
        MEDIA = ('M', gettext('Media'))
        ATTACHMENT = ('A', gettext('Attachment'))

    type = models.CharField(
        max_length=1,
        choices=MessageType.choices,
    )
    """The message type"""

    conversation = models.ForeignKey(Conversation,
                                     related_name='messages',
                                     on_delete=models.CASCADE,
                                     verbose_name=gettext('message'))
    """The conversation to which the message belongs"""

    time = models.DateTimeField(gettext('time'), auto_now_add=True)
    """When the message was sent or the event occurred"""

    quoted_message = models.ForeignKey('self',
                                       null=True,
                                       blank=True,
                                       on_delete=models.SET_NULL,
                                       verbose_name=gettext('quoted message'))
    """The message quoted by this message, if any"""

    sender = models.ForeignKey(Participant,
                               on_delete=models.PROTECT,
                               null=True,
                               blank=True,
                               verbose_name=gettext('sender'))
    """Who sent the message

    This field is NULL if and only if the message is a system message.
    """

    class SystemEvent:
        CREATED = 'conversation-created'
        JOINED = 'participant-joined'
        LEFT = 'participant-left'
        ENDED = 'conversation-ended'

    text = models.CharField(gettext('text'), max_length=4000, blank=True)
    """The text contents of the message

    For attachment and media messages, this field stores an optional
    caption typed by the user.

    For voice messages (recorder on the browser), which do not have a caption,
    this field optionally stores the automatically generated transcription.

    For system messages, this field stores a string indicating the event type.
    """

    additional_metadata = models.JSONField(gettext('additional metadata'),
                                           default=dict,
                                           blank=True)
    """Additional metadata about the message.

    System messages can use this field to store information about the event.
    """

    original_file_name = models.CharField(gettext('original file name'),
                                          max_length=100,
                                          blank=True,
                                          null=True)
    """Original name of the file attached to the message.

    Only applicable for media and attachment messages.
    """

    mime_type = models.CharField(gettext('original file name'),
                                 max_length=256,
                                 blank=True,
                                 null=True)
    """MIME type of the file attached to the message.

    Only applicable for media, voice and attachment messages.
    """

    local_id = models.CharField(gettext('local message id'),
                                blank=True,
                                null=True,
                                max_length=32)
    """Local message id, defined by the sender.

    Subsequent attempts to send a message with the same local id from the
    same sender are ignored.
    The sender should include a unique local_id per message, and it can be used
    to identify each message when it is returned by the server.
    """

    @overrides
    def clean(self) -> None:
        super().clean()
        # hasattr check is necessary, otherwise Django throws an exception
        # if the member does not exist
        sender = getattr(self, 'sender', None) if hasattr(self,
                                                          'sender') else None
        if self.type == Message.MessageType.SYSTEM:
            if sender:
                raise ValidationError('system message must not have a sender')
        else:
            if not sender:
                raise ValidationError('non-system message must have a sender')
            if sender not in self.conversation.participants.all():
                raise ValidationError(
                    'sender is a participant in the conversation')

    @overrides
    def save(self, *args: Any, **kwargs: Any) -> Any:
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = gettext('message')
        verbose_name_plural = gettext('messages')
        constraints = [
            models.UniqueConstraint(
                fields=['conversation', 'sender', 'local_id'],
                name='local_id_unique')
        ]
