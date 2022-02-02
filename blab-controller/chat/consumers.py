import json
from datetime import datetime
from sys import maxsize
from typing import Any

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation, Message, Participant
from .serializers import MessageSerializer, ParticipantSerializer


class ConversationConsumer(AsyncWebsocketConsumer):

    async def connect(self) -> None:
        self.joined_at = None
        send_old_messages = True  # this may be changed later
        self.conversation_id = self.scope['url_route']['kwargs'][
            'conversation_id']
        session = await sync_to_async(lambda: dict(self.scope['session']))()
        participant_id = session.get('participation_in_conversation',
                                     {}).get(self.conversation_id)
        self.participant = await database_sync_to_async(
            lambda: Participant.objects.get(pk=participant_id))()
        self.conversation = await database_sync_to_async(
            lambda: Conversation.objects.get(pk=self.conversation_id))()
        self.conversation_group_name = 'conversation_' + self.conversation_id
        await self.channel_layer.group_add(self.conversation_group_name,
                                           self.channel_name)
        await self.accept()

        self.participant.is_present = True
        await database_sync_to_async(self.participant.save)()

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
        await self.broadcast_state({'participants': participants})
        await self.send_state({
            'state': {
                'conversation_name': self.conversation.name,
                'my_participant_id': str(self.participant.id)
            }
        })

        if send_old_messages:
            await self.send_last_messages(500, msg.time)

    async def send_last_messages(self,
                                 limit: int = maxsize,
                                 until: datetime = datetime.max) -> None:
        last_messages = await database_sync_to_async(lambda: list(
            map(
                lambda msg: MessageSerializer(msg).data,  # type: ignore
                Message.objects.filter(conversation_id=self.conversation_id).
                exclude(time__gt=until).order_by('-time')[:limit])))()
        for m in reversed(last_messages):
            data = json.dumps({'message': m})
            await self.send(text_data=data)

    async def send_message(self, event: dict[str, Any]) -> None:
        await self.send(text_data=json.dumps({'message': event['message']}))

    async def send_state(self, event: dict[str, Any]) -> None:
        await self.send(text_data=json.dumps({'state': event['state']}))

    async def broadcast_state(self, state: dict[str, Any]) -> None:
        await self.channel_layer.group_send(self.conversation_group_name, {
            'type': 'send_state',
            'state': state
        })

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
        p = self.participant
        p.is_present = False
        await database_sync_to_async(p.save)()
        await self.channel_layer.group_send(
            self.conversation_group_name, {
                'type': 'send_message',
                'message': MessageSerializer(msg).data
            })
        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(self.conversation.participants.all(),
                                          many=True).data)()
        await self.broadcast_state({'participants': participants})
        await self.channel_layer.group_discard(self.conversation_group_name,
                                               self.channel_name)

    async def receive(self,
                      text_data: str | None = None,
                      bytes_data: bytes | None = None) -> None:
        message_data = {}
        message_class = None
        t = None
        if text_data:
            m = json.loads(text_data)
            t = m.get('type', None)
            if t == Message.MessageType.TEXT:
                text = m.get('text', '')
                if not text or not isinstance(text, str):
                    return
                message_class = Message
                message_data['text'] = text
                if 'local_id' in m:
                    message_data['local_id'] = m['local_id']

        if message_class:
            msg = await database_sync_to_async(
                message_class.objects.create
            )(**message_data,
              type=t,
              conversation_id=self.conversation_id,
              sender=self.participant)
            database_sync_to_async(msg.save)()
            await self.channel_layer.group_send(
                self.conversation_group_name, {
                    'type': 'send_message',
                    'message': MessageSerializer(msg).data
                })
