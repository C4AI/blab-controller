"""Contains Celery tasks."""

from importlib import import_module
from typing import Any, Callable, NamedTuple, cast

from celery import shared_task

from .bots import Bot
from .chats import Chat
from .models import Message, Participant

# noinspection PyUnresolvedReferences
from .signals import *  # noqa: F40


class ConversationInfo(NamedTuple):
    """Contains basic conversation information available to bots."""

    conversation_id: str
    bot_participant_id: str
    send_function: Callable[[dict[str, Any]], Message]


def _get_bot(
    bot_spec: tuple[str, str, list[Any], dict[Any, Any]],
    bot_participant_id: str,
    conversation_id: str,
) -> Bot:
    (module_name, cls_name, args, kwargs) = bot_spec
    m = import_module(module_name)
    cls = m
    for c in cls_name.split("."):
        cls = getattr(cls, c)
    cls = cast(type, cls)

    def send(message_data: dict[str, Any]) -> Message:
        return Chat.get_chat(conversation_id).save_message(
            Participant.objects.get(id=bot_participant_id), message_data
        )

    conv_info = ConversationInfo(conversation_id, bot_participant_id, send)
    return cls(conv_info, *bot_spec[2], **bot_spec[3])


@shared_task
def send_message_to_bot(
    bot_spec: tuple[str, str, list[Any], dict[Any, Any]],
    bot_participant_id: str,
    message_id: int,
) -> None:
    """Send a message to a bot.

    Args:
        bot_spec: a 4-tuple containing the module, class,
            positional arguments and keywoard arguments
            used to create an instance of the bot
            (note that this does not include the first
            positional argument, which will always be
            a ConversationInfo instance)
        bot_participant_id: id of the participant that
            corresponds to this bot in this conversation
        message_id: id of the message that is being sent
            to the bot
    """
    message = Message.objects.get(id=message_id)
    bot = _get_bot(bot_spec, bot_participant_id, str(message.conversation.id))
    bot.receive_message(message)


@shared_task
def send_status_to_bot(
    bot_spec: tuple[str, str, list[Any], dict[Any, Any]],
    status: dict[str, Any],
    bot_participant_id: str,
    conversation_id: str,
) -> None:
    """Send a message to a bot.

    Args:
        bot_spec: a 4-tuple containing the module, class,
            positional arguments and keywoard arguments
            used to create an instance of the bot
            (note that this does not include the first
            positional argument, which will always be
            a ConversationInfo instance)
        status: the status update to be sent
        bot_participant_id: id of the participant that
            corresponds to this bot in this conversation
        conversation_id: id of the conversation
    """
    bot = _get_bot(bot_spec, bot_participant_id, conversation_id)
    bot.update_status(status)
