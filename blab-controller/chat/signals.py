"""Contains signal actions."""

from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .consumers import ConversationConsumer
from .models import Message, Participant
from .serializers import ParticipantSerializer
from .tasks import deliver_message_to_bot, deliver_status_to_bot


# noinspection PyUnusedLocal
@receiver(
    [post_save, post_delete],
    sender=Participant,
    dispatch_uid="consumer_participant_watcher",
)
def _participant_watcher(
    sender: Any, instance: Participant, **kwargs: Any  # noqa: ARG001
) -> None:
    participants = {
        "participants": ParticipantSerializer(
            instance.conversation.participants.all(), many=True
        ).data
    }
    async_to_sync(ConversationConsumer.broadcast_state)(
        instance.conversation.id,
        participants,
    )

    # for internal bots that don't use WebSockets:
    for p in instance.conversation.participants.all():
        if p.type == Participant.BOT:
            func = (
                deliver_status_to_bot.delay
                if settings.CHAT_ENABLE_QUEUE
                else deliver_status_to_bot
            )
            func(participants, str(p.id))


# noinspection PyUnusedLocal
@receiver([post_save], sender=Message, dispatch_uid="consumer_message_watcher")
def _message_watcher(
    sender: Any, instance: Message, **kwargs: Any  # noqa: ARG001
) -> None:
    if not transaction.get_connection().in_atomic_block:
        _message_watcher_function(instance)
    else:
        transaction.on_commit(lambda: _message_watcher_function(instance))


def _message_watcher_function(instance: Message) -> None:
    manager_bot = getattr(settings, "CHAT_BOT_MANAGER", None)

    # if the message was sent by a human user and there is a manager bot,
    # send the message only to human users and the manager bot;
    # if the message was sent by a bot, send it only to the manager bot,
    # so that it can possibly approve it

    avoid_non_manager_bots = manager_bot and instance.type != Message.MessageType.SYSTEM

    if avoid_non_manager_bots:
        async_to_sync(ConversationConsumer.deliver_message_to_bot_manager)(instance)
    if int(instance.approval_status):
        async_to_sync(ConversationConsumer.broadcast_message)(
            instance, avoid_non_manager_bots
        )

    for p in instance.conversation.participants.all():
        if p.type != Participant.BOT:
            continue
        if manager_bot and avoid_non_manager_bots and p.name != manager_bot:
            continue
        func = (
            deliver_message_to_bot.delay
            if settings.CHAT_ENABLE_QUEUE
            else deliver_message_to_bot
        )
        func(str(p.id), instance.id)


__all__ = []
