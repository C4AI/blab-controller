"""Contains Websocket consumers."""
import json
from importlib import import_module
from typing import Any, Callable, NamedTuple, cast

from asgiref.sync import async_to_sync, sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from overrides import overrides

from .bots import all_bots
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
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        session = await sync_to_async(lambda: dict(self.scope['session']))()
        participant_id = session.get('participation_in_conversation', {}).get(
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
        await self.accept()

        msg = await database_sync_to_async(Message.objects.create)(
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.JOINED,
            additional_metadata={
                'participant_id': str(self.participant.id),
            },
            conversation_id=self.conversation_id,
        )
        database_sync_to_async(msg.save)()

        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(
                self.conversation.participants.all(), many=True
            ).data
        )()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {'participants': participants}
        )

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
    async def broadcast_state(cls, conversation_id: str, state: dict[str, Any]) -> None:
        """Send state data to all participants.

        Args:
            conversation_id: id of the conversation
            state: state represented as a dictionary
        """
        await get_channel_layer().group_send(
            _conversation_id_to_group_name(conversation_id),
            {'type': 'send_state', 'state': state},
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
            {'type': 'send_message', 'message': data},
        )

    @overrides
    async def disconnect(self, code: int) -> None:
        msg = await database_sync_to_async(Message.objects.create)(
            type=Message.MessageType.SYSTEM,
            conversation_id=self.conversation_id,
            text=Message.SystemEvent.LEFT,
            additional_metadata={
                'participant_id': str(self.participant.id),
            },
        )
        await database_sync_to_async(msg.save)()

        participants = await database_sync_to_async(
            lambda: ParticipantSerializer(
                self.conversation.participants.all(), many=True
            ).data
        )()
        await ConversationConsumer.broadcast_state(
            self.conversation_id, {'participants': participants}
        )
        await self.channel_layer.group_discard(
            self.conversation_group_name, self.channel_name
        )

    @overrides
    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ) -> None:
        if text_data:
            m = json.loads(text_data)
            await self.create_message(
                {
                    **m,
                    'conversation_id': self.conversation_id,
                    'sender_id': self.participant.id,
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
        """
        try:
            serializer = MessageSerializer(data=message_data)
            serializer.is_valid(raise_exception=True)
            message = serializer.save()
        except ValidationError as e:
            err = getattr(e, 'error_dict', {}).get('__all__', [])
            if len(err) == 1 and getattr(err[0], 'code', None) == 'unique_together':
                chk = getattr(err[0], 'params', {}).get('unique_check', tuple())
                if set(chk) == {'conversation', 'sender', 'local_id'}:
                    # Ignore duplicate message
                    return None
            raise
        return cast(Message, message)


# noinspection PyUnusedLocal
@receiver(
    [post_save, post_delete],
    sender=Participant,
    dispatch_uid='consumer_participant_watcher',
)
def _participant_watcher(sender: Any, instance: Participant, **kwargs: Any) -> None:
    async_to_sync(ConversationConsumer.broadcast_state)(
        instance.conversation.id,
        {
            'participants': ParticipantSerializer(
                instance.conversation.participants.all(), many=True
            ).data
        },
    )


class ConversationInfo(NamedTuple):
    """Contains basic conversation information available to bots."""

    conversation_id: str
    bot_participant_id: str
    send_function: Callable[[dict[str, Any]], Message]


# noinspection PyUnusedLocal
@receiver([post_save], sender=Message, dispatch_uid='consumer_message_watcher')
def _message_watcher(sender: Any, instance: Message, **kwargs: Any) -> None:
    async_to_sync(ConversationConsumer.broadcast_message)(
        instance.conversation.id, instance
    )

    # bots
    bots = all_bots()
    use_bots = []
    for p in instance.conversation.participants.all():
        if p.type == Participant.BOT:
            try:
                bot_spec = bots[p.name]
            except KeyError:
                pass
            else:
                use_bots.append((bot_spec, p.id))
    for (module_name, cls_name, *a), bot_participant_id in use_bots:
        m = import_module(module_name)
        cls = m
        for c in cls_name.split('.'):
            cls = getattr(cls, c)
        args = a[0] if len(a) >= 1 else []
        kwargs = a[1] if len(a) >= 2 else {}

        def send(message_data: dict[str, Any]) -> Message:
            return async_to_sync(ConversationConsumer.create_message)(
                dict(
                    **message_data,
                    conversation_id=instance.conversation.id,
                    sender_id=bot_participant_id,
                )
            )

        conv_info = ConversationInfo(instance.conversation.id, bot_participant_id, send)
        # noinspection PyCallingNonCallable
        bot_instance = cls(conv_info, *args, **kwargs)
        bot_instance.receive_message(instance)


__all__ = [ConversationConsumer]
