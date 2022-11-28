"""Contains Websocket consumers."""
import json
from typing import Any

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from overrides import overrides

from .models import Conversation, Message, Participant
from .serializers import MessageSerializer, ParticipantSerializer


def _conversation_id_to_group_name(
    conversation_id: str,
    only_participant: str | None = None,
    without_bots: bool = False,
) -> str:
    """Return the Websocket group name correspondent to a conversation.

    Args:
        conversation_id: id of the conversation
        only_participant: if True, return the name of a group that contains
            only the specified participant
        without_bots: if True, return the name of a group that does not contain bots

    Returns:
        the group name
    """
    assert only_participant is None or not without_bots
    suffix = ""
    if only_participant:
        suffix = "_" + only_participant
    elif without_bots:
        suffix = "__NO_BOTS"
    return "conversation_" + str(conversation_id) + suffix


# noinspection PyAttributeOutsideInit
class ConversationConsumer(AsyncWebsocketConsumer):
    """Websocket consumer for conversations and messages."""

    @overrides
    async def connect(self) -> None:
        self.joined_at = None
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        session = await sync_to_async(lambda: dict(self.scope["session"]))()
        participant_id = session.get("participation_in_conversation", {}).get(
            self.conversation_id
        )
        self.participant = await database_sync_to_async(
            lambda: Participant.objects.get(pk=participant_id)
        )()
        self.conversation = await database_sync_to_async(
            lambda: Conversation.objects.get(pk=self.conversation_id)
        )()
        self.conversation_group_name = _conversation_id_to_group_name(
            self.conversation_id
        )
        await self.channel_layer.group_add(
            self.conversation_group_name, self.channel_name
        )

        # Bots have a specific channel for them;
        # human users share a separate channel without bots
        await self.channel_layer.group_add(
            _conversation_id_to_group_name(
                self.conversation_id,
                str(self.participant.id)
                if self.participant.type == Participant.BOT
                else None,
                self.participant.type != Participant.BOT,
            ),
            self.channel_name,
        )

        await self.accept()

        if self.participant.type != Participant.BOT:
            msg = await database_sync_to_async(Message.objects.create)(
                type=Message.MessageType.SYSTEM,
                text=Message.SystemEvent.JOINED,
                additional_metadata={
                    "participant_id": str(self.participant.id),
                },
                conversation_id=self.conversation_id,
                approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
            )
            database_sync_to_async(msg.save)()

        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(
                self.conversation.participants.all(), many=True
            ).data
        )()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {"participants": participants}
        )

    async def send_message(self, event: dict[str, Any]) -> None:
        """Send message to this participant.

        Args:
            event: message represented as a dictionary
        """
        await self.send(text_data=json.dumps({"message": event["message"]}))

    async def send_state(self, event: dict[str, Any]) -> None:
        """Send state data to this participant.

        Args:
            event: state represented as a dictionary
        """
        await self.send(text_data=json.dumps({"state": event["state"]}))

    @classmethod
    async def broadcast_state(cls, conversation_id: str, state: dict[str, Any]) -> None:
        """Send state data to all participants.

        Args:
            conversation_id: id of the conversation
            state: state represented as a dictionary
        """
        await get_channel_layer().group_send(
            _conversation_id_to_group_name(conversation_id),
            {"type": "send_state", "state": state},
        )

    @classmethod
    async def broadcast_message(cls, conversation_id: str, message: Message) -> None:
        """Send a message to all participants.

        Args:
            conversation_id: id of the conversation
            message: message to be sent
        """
        data = await database_sync_to_async(lambda: MessageSerializer(message).data)()
        await get_channel_layer().group_send(
            _conversation_id_to_group_name(conversation_id),
            {"type": "send_message", "message": data},
        )

    @classmethod
    async def send_message_to_bot_manager(
        cls, conversation_id: str, message: Message
    ) -> None:
        """Send a message to the bot manager.

        Args:
            conversation_id: id of the conversation
            message: message to be sent
        """
        data = await database_sync_to_async(lambda: MessageSerializer(message).data)()
        await get_channel_layer().group_send(
            _conversation_id_to_group_name(conversation_id, settings.CHAT_BOT_MANAGER),
            {"type": "send_message", "message": data},
        )

    @overrides
    async def disconnect(self, code: int) -> None:
        msg = await database_sync_to_async(Message.objects.create)(
            type=Message.MessageType.SYSTEM,
            conversation_id=self.conversation_id,
            text=Message.SystemEvent.LEFT,
            additional_metadata={
                "participant_id": str(self.participant.id),
            },
            approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
        )
        await database_sync_to_async(msg.save)()

        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(
                self.conversation.participants.all(), many=True
            ).data
        )()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {"participants": participants}
        )
        await self.channel_layer.group_discard(
            self.conversation_group_name, self.channel_name
        )

    @overrides
    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ) -> None:
        if text_data:
            if self.participant.type == Participant.HUMAN:
                approval_status = Message.ApprovalStatus.AUTOMATICALLY_APPROVED
            else:
                approval_status = Message.ApprovalStatus.NO

            m = json.loads(text_data)
            await self.create_message(
                {
                    **m,
                    "conversation_id": self.conversation_id,
                    "sender_id": self.participant.id,
                    "approval_status": approval_status,
                }
            )

    @classmethod
    @database_sync_to_async
    def create_message(cls, message_data: dict[str, Any]) -> Message | None:
        """Create a message and save it to the database.

        Args:
            message_data: message parameters and data

        Raises:
            ValidationError: if validation fails

        Returns:
            the new instance of :cls:`Message` if it was saved successfully,
            or ``None`` if it was not saved because it is duplicate (same
            ``local_id`` and sender as an existing message).
        """  # noqa: DAR402
        return MessageSerializer.create_message(message_data)


__all__ = [ConversationConsumer]
