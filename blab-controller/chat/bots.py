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
from .models import Message


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
        sleep(1)
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
    if not bot_names_or_participants_ids:
        return ""
    return "TO:" + ",".join(bot_names_or_participants_ids)


def manager_approval() -> str:
    return "OK"


class TransparentManagerBot(Bot):
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
    @overrides
    def receive_message(self, message: Message) -> None:
        if not message.sent_by_human():
            return
        if message.type != Message.MessageType.TEXT:
            return
        if re.match(r"^[0-9+\-*/ ()]+$", message.text):
            result = manager_redirection("Calculator")
        else:
            result = manager_redirection("ECHO")
        self.conversation_info.send_function(
            {
                "type": Message.MessageType.TEXT,
                "text": result,
                "quoted_message_id": str(message.m_id),
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
