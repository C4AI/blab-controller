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
from .tasks import send_message_to_bot, send_status_to_bot


# noinspection PyUnusedLocal
@receiver(
    [post_save, post_delete],
    sender=Participant,
    dispatch_uid="consumer_participant_watcher",
)
def _participant_watcher(sender: Any, instance: Participant, **kwargs: Any) -> None:
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
    bots = all_bots()
    for p in instance.conversation.participants.all():
        if p.type == Participant.BOT:
            try:
                bot_spec = bots[p.name]
            except KeyError:
                continue
            func = (
                send_status_to_bot.delay
                if settings.CHAT_ENABLE_QUEUE
                else send_status_to_bot
            )
            func(bot_spec, participants, str(p.id), instance.conversation.id)


# noinspection PyUnusedLocal
@receiver([post_save], sender=Message, dispatch_uid="consumer_message_watcher")
def _message_watcher(sender: Any, instance: Message, **kwargs: Any) -> None:
    if not transaction.get_connection().in_atomic_block:
        _message_watcher_function(instance)
    else:
        transaction.on_commit(lambda: _message_watcher_function(instance))


def _message_watcher_function(instance: Message) -> None:
    # bots
    bots = all_bots()
    manager_bot = getattr(settings, "CHAT_BOT_MANAGER", None)

    # if the message is from the manager bot:
    if (
        instance.sender
        and instance.sender.type == Participant.BOT
        and instance.sender.name == manager_bot
        and instance.text.startswith("TO:\n")
    ):
        for part in instance.text.strip().split("\n")[1:]:
            # if bot uses WebSockets
            async_to_sync(ConversationConsumer.send_message_to_bot)(
                str(instance.conversation.id), instance.quoted_message, part
            )
            # if bot is internal
            b = next(
                p
                for p in instance.conversation.participants.all()
                if p.type == Participant.BOT and part in [p.name, str(p.id)]
            )
            try:
                bot_spec = bots[b.name]
            except KeyError:
                pass
            else:
                func = (
                    send_message_to_bot.delay
                    if settings.CHAT_ENABLE_QUEUE
                    else send_message_to_bot
                )
                func(bot_spec, str(b.id), instance.quoted_message.id)

    # if the message was sent by a human user and there is a manager bot,
    # send the message only to human users and the manager bot;
    # if the message was sent by a bot, send it only to the manager bot,
    # so that it can possibly approve it

    avoid_non_manager_bots = manager_bot and instance.sent_by_human()

    if avoid_non_manager_bots:
        async_to_sync(ConversationConsumer.send_message_to_bot_manager)(
            instance.conversation.id, instance
        )
    if int(instance.approval_status):
        async_to_sync(ConversationConsumer.broadcast_message)(
            instance.conversation.id, instance, avoid_non_manager_bots
        )
    else:
        async_to_sync(ConversationConsumer.send_message_to_bot_manager)(
            instance.conversation.id, instance
        )

    for p in instance.conversation.participants.all():
        if p.type == Participant.BOT:
            if manager_bot and avoid_non_manager_bots and p.name != manager_bot:
                continue
            try:
                bot_spec = bots[p.name]
            except KeyError:
                pass
            else:
                func = (
                    send_message_to_bot.delay
                    if settings.CHAT_ENABLE_QUEUE
                    else send_message_to_bot
                )
                func(bot_spec, str(p.id), instance.id)


__all__ = []
