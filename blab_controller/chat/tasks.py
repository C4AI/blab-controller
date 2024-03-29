"""Contains Celery tasks."""

from collections.abc import Callable
from typing import Any, NamedTuple

from celery import shared_task

from .chats import Chat
from .models import Message, Participant


class ConversationInfo(NamedTuple):
    """Contains basic conversation information available to bots."""

    conversation_id: str
    bot_participant_id: str
    send_function: Callable[[dict[str, Any]], Message]


@shared_task
def deliver_message_to_bot(
    bot_participant_id: str,
    message_id: int,
    field_overrides: dict[str, Any] | None = None,
) -> None:
    """Send a message to a bot.

    Args:
        bot_participant_id: id of the participant that
            corresponds to this bot in this conversation
        message_id: id of the message that is being sent
            to the bot
        field_overrides: dict from field names to the values
            that should replace the actual values
    """
    message = Message.objects.get(id=message_id)
    bot_participant = Participant.objects.get(pk=bot_participant_id)
    Chat.get_chat(message.conversation.id).deliver_message_to_bot(
        message, bot_participant, field_overrides=field_overrides
    )


@shared_task
def deliver_status_to_bot(status: dict[str, Any], bot_participant_id: str) -> None:
    """Send status information to a bot.

    Args:
        status: the status update to be sent
        bot_participant_id: id of the participant that
            corresponds to this bot in this conversation
    """
    bot_participant = Participant.objects.get(pk=bot_participant_id)
    Chat.get_chat(bot_participant.conversation.id).deliver_status_to_bot(
        status, bot_participant
    )
