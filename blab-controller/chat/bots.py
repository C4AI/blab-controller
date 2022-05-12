"""Contains a basic class that implements a chat bot."""
from time import sleep
from typing import Any, Callable, Protocol

from overrides import overrides

from .models import Message


class ConversationInfo(Protocol):
    """Conversation interface available to bots."""

    conversation_id: str
    my_participant_id: str
    send_function: Callable[[dict[str, Any]], Message]


class Bot:
    """Represents a chat bot."""

    my_participant_id: str

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
        ...


class UpperCaseEchoBot(Bot):
    """Bot example - echoes text messages in upper-case letters."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not message.sent_by_human():
            return
        if message.type != Message.MessageType.TEXT:
            result = '?'
        else:
            result = message.text.upper()
        sleep(1)
        self.conversation_info.send_function(
            {
                'type': Message.MessageType.TEXT,
                'text': result,
                'quoted_message_id': str(message.m_id),
            },
        )


class CalculatorBot(Bot):
    """Bot example - evaluates simple mathematical expressions."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not message.sent_by_human():
            return
        if message.type != Message.MessageType.TEXT:
            result = '?'
        else:
            result = self.evaluate(message.text)
        sleep(1)
        self.conversation_info.send_function(
            {
                'type': Message.MessageType.TEXT,
                'text': result,
                'quoted_message_id': str(message.m_id),
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
        invalid_output = '?'
        try:
            import ast

            parsed_tree = ast.parse(expression, mode='eval')
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
            result = eval(compile(parsed_tree, filename='', mode='eval'))
        except ArithmeticError:
            return invalid_output
        else:
            return str(result)


def all_bots() -> dict[str, list[str, Any, ...]]:
    """Return all installed bots.

    Returns:
        list of installed bots
    """
    from django.conf import settings

    return settings.INSTALLED_BOTS
