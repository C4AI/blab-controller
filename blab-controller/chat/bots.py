"""Contains a basic class that implements a chat bot."""
import json
import re
from http.client import HTTPConnection, HTTPSConnection
from time import sleep
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from django.contrib.sessions.backends.db import SessionStore
from overrides import overrides

from . import blab_logger as logger
from .models import Message, Participant


class ConversationInfo(Protocol):
    """Conversation interface available to bots."""

    conversation_id: str
    bot_participant_id: str
    send_function: Callable[[dict[str, Any]], Message]


class Bot:
    """Represents a chat bot."""

    def __init__(self, conversation_info: ConversationInfo):
        """.

        Args:
            conversation_info: conversation data
        """
        self.conversation_info = conversation_info

    def receive_message(self, message: Message) -> None:
        """Receive a message.

        In order to avoid bots that answer to each other,
        implementations should ignore messages sent by
        themselves or other bots.

        Args:
            message: the received message
        """

    def update_status(self, status: dict[str, Any]) -> None:
        """Receive a status update.

        Example: the information that the list of participants has changed.

        Args:
            status: the status update
        """


class UpperCaseEchoBot(Bot):
    """Bot example - echoes text messages in upper-case letters."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not message.sent_by_human():
            return
        if message.type != Message.MessageType.TEXT:
            result = "?"
        else:
            result = message.text.upper()
        sleep(1)
        self.conversation_info.send_function(
            {
                "type": Message.MessageType.TEXT,
                "text": result,
                "quoted_message_id": str(message.m_id),
            },
        )


class CalculatorBot(Bot):
    """Bot example - evaluates simple mathematical expressions."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not message.sent_by_human():
            return
        if message.type != Message.MessageType.TEXT:
            result = "?"
        else:
            result = self.evaluate(message.text)
        sleep(0.3)
        self.conversation_info.send_function(
            {
                "type": Message.MessageType.TEXT,
                "text": result,
                "quoted_message_id": str(message.m_id),
            },
        )

    # noinspection PyMethodMayBeStatic
    def evaluate(self, expression: str) -> str:
        """Compute the result of a simple mathematical expression.

        Args:
            expression: the expression to evaluate

        Returns:
            the calculated result, or "?" if there are errors
        """
        invalid_output = "?"
        try:
            import ast

            parsed_tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            return invalid_output
        if not all(
            isinstance(
                node,
                (
                    ast.Expression,
                    ast.Num,
                    ast.UnaryOp,
                    ast.unaryop,
                    ast.BinOp,
                    ast.operator,
                ),
            )
            for node in ast.walk(parsed_tree)
        ):
            # it would not be safe if nodes of other types were allowed
            return invalid_output
        try:
            result = eval(compile(parsed_tree, filename="", mode="eval"))
        except ArithmeticError:
            return invalid_output
        else:
            return str(result)


def manager_redirection(*bot_names_or_participants_ids: str) -> str:
    r"""Return a string that indicates the bots that will receive a given message.

    Args:
        bot_names_or_participants_ids: the names or ids of the bots

    Returns:
        the string "TO:\n" followed by a '\n'-separated list of bots that will
        receive the message
    """
    if not bot_names_or_participants_ids:
        return ""
    return "TO:\n" + "\n".join(bot_names_or_participants_ids)


def manager_approval() -> str:
    """Return a string that indicates that a message has been appproved.

    Returns:
        the string "OK"
    """
    return "OK"


class TransparentManagerBot(Bot):
    """Transparent bot manager.

    It sends the user's messages to all bots
        and accepts all bots' answers.
    """

    @overrides
    def receive_message(self, message: Message) -> None:
        if (
            message.sent_by_human()
            or message.type == Message.MessageType.SYSTEM
            or str(message.sender.id) == str(self.conversation_info.bot_participant_id)
            or int(message.approval_status)
        ):
            return
        result = manager_approval()
        self.conversation_info.send_function(
            {
                "type": Message.MessageType.TEXT,
                "text": result,
                "quoted_message_id": str(message.m_id),
            },
        )


class CalcOrEchoManagerBot(Bot):
    """Bot manager that selects between calculator and upper-case echo bots."""

    @overrides
    def __init__(self, conversation_info: ConversationInfo):
        super().__init__(conversation_info)

    @overrides
    def receive_message(self, message: Message) -> None:
        target = str(message.m_id)
        if message.type == Message.MessageType.SYSTEM or str(message.sender.id) == str(
            self.conversation_info.bot_participant_id
        ):
            # ignore system and manager's own messages
            return
        if message.type != Message.MessageType.TEXT:
            # ignore unsupported non-text messages
            return
        if not message.sent_by_human():
            # sent by bot
            if message.sender.name == "Calculator" and message.text == "?":
                # probably a malformed expression that resulted in '?',
                # so we send to upper-case ECHO instead
                result = manager_redirection("ECHO")
                target = str(message.quoted_message.m_id)
            elif not int(message.approval_status):
                # something else: just approve it
                result = manager_approval()
            else:
                return
        else:
            # sent by human
            bots_in_conversation = set(
                map(
                    lambda p: p.name,
                    filter(
                        lambda p: p.type == Participant.BOT,
                        message.conversation.participants.all(),
                    ),
                )
            )
            if "Calculator" in bots_in_conversation and re.match(
                r"^[0-9+\-*/ ().]+$", message.text
            ):
                # looks like an expression -> send to calculator
                result = manager_redirection("Calculator")
            elif "ECHO" in bots_in_conversation:
                # not an expression -> send to upper-case ECHO
                result = manager_redirection("ECHO")
            else:
                # should not happen
                return
        self.conversation_info.send_function(
            {
                "type": Message.MessageType.TEXT,
                "text": result,
                "quoted_message_id": target,
            },
        )


class WebSocketExternalBot(Bot):
    """External bot that interacts with the controller via WebSocket."""

    def __init__(self, conversation_info: ConversationInfo, trigger_url: str):
        """.

        Args:
            conversation_info: conversation data
            trigger_url: HTTP URL to be requested for every new conversation
        """
        super().__init__(conversation_info)
        self.trigger_url = trigger_url

    @overrides
    def receive_message(self, message: Message) -> None:
        if (
            message.type == Message.MessageType.SYSTEM
            and message.text == Message.SystemEvent.JOINED
            and message.additional_metadata["participant_id"]
            == self.conversation_info.bot_participant_id
        ):
            self._start_bot()

    def _start_bot(self) -> None:
        session = SessionStore()
        session.cycle_key()
        session["participation_in_conversation"] = {
            str(self.conversation_info.conversation_id): str(
                self.conversation_info.bot_participant_id
            )
        }
        session.save()

        data = {
            "conversation_id": str(self.conversation_info.conversation_id),
            "bot_participant_id": str(self.conversation_info.bot_participant_id),
            "session": session.session_key,
        }

        o = urlparse(self.trigger_url)
        match (o.scheme or "").lower():
            case "http":
                connection = HTTPConnection(o.hostname, o.port or 80)
            case "https":
                connection = HTTPSConnection(o.hostname, o.port or 443)
            case _:
                logger.warn(
                    "bot not started - invalid or missing protocol in its URL",
                    url=self.trigger_url,
                )
                return
        connection.request(
            "POST", o.path, json.dumps(data), {"Content-Type": "application/json"}
        )


def all_bots() -> dict[str, tuple[str, str, list[Any], dict[Any, Any]]]:
    """Return all installed bots.

    Returns:
        list of installed bots
    """
    from django.conf import settings

    return settings.CHAT_INSTALLED_BOTS
