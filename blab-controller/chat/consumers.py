"""Contains Websocket consumers."""
import json
from typing import Any, cast

from asgiref.sync import async_to_sync, sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from overrides import overrides

from .models import Conversation, Message, Participant
from .serializers import MessageSerializer, ParticipantSerializer


def _conversation_id_to_group_name(conversation_id: str) -> str:
    """Return the Websocket group name correspondent to a conversation.

    Args:
        conversation_id: id of the conversation

    Returns:
        the group name
    """
    return 'conversation_' + str(conversation_id)


class ConversationConsumer(AsyncWebsocketConsumer):
    """Websocket consumer for conversations and messages."""

    @overrides
    async def connect(self) -> None:
        self.joined_at = None
        self.conversation_id = self.scope['url_route']['kwargs'][
            'conversation_id']
        session = await sync_to_async(lambda: dict(self.scope['session']))()
        participant_id = session.get('participation_in_conversation',
                                     {}).get(self.conversation_id)
        self.participant = await database_sync_to_async(
            lambda: Participant.objects.get(pk=participant_id))()
        self.conversation = await database_sync_to_async(
            lambda: Conversation.objects.get(pk=self.conversation_id))()
        self.conversation_group_name = _conversation_id_to_group_name(
            self.conversation_id)
        await self.channel_layer.group_add(self.conversation_group_name,
                                           self.channel_name)
        await self.accept()

        msg = await database_sync_to_async(Message.objects.create)(
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.JOINED,
            additional_metadata={
                'participant_id': str(self.participant.id),
                'participant_name': self.participant.name
            },
            conversation_id=self.conversation_id)
        database_sync_to_async(msg.save)()

        await self.channel_layer.group_send(
            self.conversation_group_name, {
                'type': 'send_message',
                'message': MessageSerializer(msg).data,
            })

        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(self.conversation.participants.all(),
                                          many=True).data)()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {'participants': participants})

    async def send_message(self, event: dict[str, Any]) -> None:
        """Send message to this participant.

        Args:
            event: message represented as a dictionary
        """
        await self.send(text_data=json.dumps({'message': event['message']}))

    async def send_state(self, event: dict[str, Any]) -> None:
        """Send state data to this participant.

        Args:
            event: state represented as a dictionary
        """
        await self.send(text_data=json.dumps({'state': event['state']}))

    @classmethod
    async def broadcast_state(cls, conversation_id: str,
                              state: dict[str, Any]) -> None:
        """Send state data to all participants.

        Args:
            conversation_id: id of the conversation
            state: state represented as a dictionary
        """
        await get_channel_layer().group_send(
            _conversation_id_to_group_name(conversation_id), {
                'type': 'send_state',
                'state': state
            })

    @overrides
    async def disconnect(self, code: int) -> None:
        msg = await database_sync_to_async(Message.objects.create)(
            type=Message.MessageType.SYSTEM,
            conversation_id=self.conversation_id,
            text=Message.SystemEvent.LEFT,
            additional_metadata={
                'participant_id': str(self.participant.id),
                'participant_name': self.participant.name,
            })
        await database_sync_to_async(msg.save)()
        await self.channel_layer.group_send(
            self.conversation_group_name, {
                'type': 'send_message',
                'message': MessageSerializer(msg).data
            })
        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(self.conversation.participants.all(),
                                          many=True).data)()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {'participants': participants})
        await self.channel_layer.group_discard(self.conversation_group_name,
                                               self.channel_name)

    @overrides
    async def receive(self,
                      text_data: str | None = None,
                      bytes_data: bytes | None = None) -> None:
        message_data = {}
        t = None
        if text_data:
            m = json.loads(text_data)
            quoted_message_id = m.get('quoted_message_id', None)

            if quoted_message_id:
                quoted_message = await database_sync_to_async(
                    lambda: Message.objects.filter(m_id=quoted_message_id
                                                   ).first())()
                quoted_message_conversation_id = await database_sync_to_async(
                    lambda: str(quoted_message.conversation.id)
                    if quoted_message else None)()
                if (quoted_message_conversation_id == self.conversation_id):
                    message_data['quoted_message'] = quoted_message

            t = m.get('type', None)
            if t == Message.MessageType.TEXT:
                text = m.get('text', '')
                if not text or not isinstance(text, str):
                    return
                message_data['text'] = text
                if 'local_id' in m:
                    message_data['local_id'] = m['local_id']
            else:
                raise Exception('UNSUPPORTED TYPE')

        msg = await self.create_message({
            **message_data, 'type': t,
            'conversation_id': self.conversation_id,
            'sender': self.participant
        })
        if msg:
            await self.channel_layer.group_send(
                self.conversation_group_name, {
                    'type': 'send_message',
                    'message': MessageSerializer(msg).data
                })

    @database_sync_to_async
    def create_message(self, message_data: dict[str, Any]) -> Message | None:
        """Create a message and save it to the database.

        Args:
            message_data: message parameters and data

        Raises:
            ValidationError: if validation fails

        Returns:
            the new instance of :cls:`Message` if it was saved successfully,
            or ``None`` if it was not saved because it is duplicate (same
            ``local_id`` and sender as an existing message).
        """
        try:
            message = Message.objects.create(**message_data)
            message.save()
        except ValidationError as e:
            err = getattr(e, 'error_dict', {}).get('__all__', [])
            if len(err) == 1 and getattr(err[0], 'code',
                                         None) == 'unique_together':
                chk = getattr(err[0], 'params',
                              {}).get('unique_check', tuple())
                if set(chk) == {'conversation', 'sender', 'local_id'}:
                    # Ignore duplicate message
                    return None
            raise
        message.save()
        return cast(Message, message)


@receiver([post_save, post_delete],
          sender=Participant,
          dispatch_uid='participant_watcher')
def _participant_watcher(_sender: Any, instance: Participant,
                         **_kwargs: Any) -> None:
    async_to_sync(ConversationConsumer.broadcast_state)(
        instance.conversation.id, {
            'participants':
            ParticipantSerializer(instance.conversation.participants.all(),
                                  many=True).data
        })


__all__ = [ConversationConsumer]
