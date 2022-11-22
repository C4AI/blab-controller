"""Contains signal actions."""

from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .bots import all_bots
from .consumers import ConversationConsumer
from .models import Message, Participant
from .serializers import ParticipantSerializer
from .tasks import send_to_bot


# noinspection PyUnusedLocal
@receiver(
    [post_save, post_delete],
    sender=Participant,
    dispatch_uid="consumer_participant_watcher",
)
def _participant_watcher(sender: Any, instance: Participant, **kwargs: Any) -> None:
    async_to_sync(ConversationConsumer.broadcast_state)(
        instance.conversation.id,
        {
            "participants": ParticipantSerializer(
                instance.conversation.participants.all(), many=True
            ).data
        },
    )


# noinspection PyUnusedLocal
@receiver([post_save], sender=Message, dispatch_uid="consumer_message_watcher")
def _message_watcher(sender: Any, instance: Message, **kwargs: Any) -> None:
    if not transaction.get_connection().in_atomic_block:
        _message_watcher_function(instance)
    else:
        transaction.on_commit(lambda: _message_watcher_function(instance))


def _message_watcher_function(instance: Message) -> None:
    # broadcast to all users
    async_to_sync(
        ConversationConsumer.broadcast_message
        if int(instance.approval_status)
        else ConversationConsumer.send_message_to_bot_manager
    )(instance.conversation.id, instance)

    # bots
    bots = all_bots()
    for p in instance.conversation.participants.all():
        if p.type == Participant.BOT:
            try:
                bot_spec = bots[p.name]
            except KeyError:
                pass
            else:
                func = send_to_bot.delay if settings.CHAT_ENABLE_QUEUE else send_to_bot
                func(bot_spec, str(p.id), instance.id)


__all__ = []
