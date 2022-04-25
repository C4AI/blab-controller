"""Contains a basic class that implements a chat bot."""
from typing import Any

from overrides import overrides

from .models import Message, Participant


class Bot:
    """Represents a chat bot."""

    my_participant_id: str

    def __init__(self, conversation_id: str, my_participant_id: str):
        """.

        Args:
            conversation_id: conversation id
            my_participant_id: bot's participant id
        """
        self.conversation_id = conversation_id
        self.my_participant_id = my_participant_id

    def receive_message(self, message: Message) -> None:
        """Receive a message.

        In order to avoid bots that answer to each other,
        implementations should ignore messages sent by
        themselves or other bots.

        Args:
            message: the received message
        """
        ...

    def _send_message(self, conversation_id: str, message_data: dict[str, Any]) -> None:
        """Send a message from the bot.

        Usually this method should only be called internally.

        Args:
            conversation_id: id of the conversation
            message_data: message data (type, text, etc.)
        """
        Message.objects.create(
            **message_data,
            conversation_id=conversation_id,
            sender_id=self.my_participant_id,
        )

    @classmethod
    def _from_human(cls, message: Message) -> bool:
        """Check if the sender of a message is human.

        Args:
            message: the message sent by the desired sender

        Returns:
            True if the message has been sent by a human participant
        """
        return (
            message.type != Message.MessageType.SYSTEM
            and message.sender.type == Participant.HUMAN
        )


class UpperCaseEchoBot(Bot):
    """Bot example - echoes text messages in upper-case letters."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not Bot._from_human(message):
            return
        if message.type != Message.MessageType.TEXT:
            result = '?'
        else:
            result = message.text.upper()
        self._send_message(
            message.conversation_id,
            {
                'type': Message.MessageType.TEXT,
                'text': result,
                'quoted_message_id': str(message.id),
            },
        )


class CalculatorBot(Bot):
    """Bot example - evaluates simple mathematical expressions."""

    @overrides
    def receive_message(self, message: Message) -> None:
        if not Bot._from_human(message):
            return
        if message.type != Message.MessageType.TEXT:
            result = '?'
        else:
            result = self.evaluate(message.text)
        self._send_message(
            message.conversation_id,
            {
                'type': Message.MessageType.TEXT,
                'text': result,
                'quoted_message_id': str(message.id),
            },
        )

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
