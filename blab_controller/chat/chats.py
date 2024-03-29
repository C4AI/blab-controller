"""Contains code that controls the events in a chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import json
from importlib import import_module
from typing import Any, NamedTuple, TypedDict, cast
from uuid import UUID

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from . import blab_logger as logger
from .bots import Bot, ChatMessage, all_bots
from .models import Conversation, Message, Participant
from .serializers import MessageSerializer


def _get_bot(
    bot_spec: tuple[str, str, bool, list[Any], dict[Any, Any]],
    bot_participant_id: str | UUID,
    conversation_id: str,
) -> Bot:
    (module_name, cls_name, _required, args, kwargs) = bot_spec
    m = import_module(module_name)
    cls = m
    for c in cls_name.split("."):
        cls = getattr(cls, c)
    cls = cast(type, cls)

    def send(message_data: dict[str, Any]) -> Message:
        return Chat.get_chat(conversation_id).save_message(
            Participant.objects.get(id=bot_participant_id), message_data
        )

    class ConversationInfo(NamedTuple):
        """Contains basic conversation information available to bots."""

        conversation_id: str
        bot_participant_id: str
        send_function: Callable[[dict[str, Any]], Message]

    conv_info = ConversationInfo(conversation_id, str(bot_participant_id), send)
    return cls(conv_info, *bot_spec[3], **bot_spec[4])


class Chat:
    """Represents a conversation.

    Note that the Conversation represents a database entity, whereas
    Chat contains methods that manage the events that occur in a conversation.
    """

    _all_chats = {}

    def __init__(self, conversation: Conversation):
        """Create an instance.

        Args:
            conversation: Conversation instance
        """
        self.conversation: Conversation = conversation

        conversation_id = str(self.conversation.id)
        if str(conversation_id) in self.__class__._all_chats:
            error = "Chat instance already created for this conversation"
            raise ValueError(error)
        self.__class__._all_chats[str(conversation_id)] = self
        self.log = logger.bind(conversation_id=conversation_id)

    @classmethod
    def on_create_conversation(
        cls, nickname: str, bots: list[str], conversation: Conversation
    ) -> list[Participant]:
        """Create Participant instances when a conversation is started.

        This method creates the participants for the human user and the bots.
        Also, it generates system messages indicating that the conversation
        has been created and the participants have joined it.

        A new instance of Chat is created and stored.

        Args:
            nickname: name of the user who created the conversation
            bots: list of bot names to invite to the conversation
            conversation: the Conversation instance

        Returns:
            the list of participants in the conversation
            (the human participant is the first entry)
        """
        return Chat(conversation)._on_create(nickname, bots)

    def _on_create(self, nickname: str, bots: list[str]) -> list[Participant]:
        """Create Participant instances when the conversation is started.

        This method creates the participants for the human user and the bots.
        Also, it generates system messages indicating that the conversation
        has been created and the participants have joined it.

        Args:
            nickname: name of the user who created the conversation
            bots: list of bot names to invite to the conversation

        Returns:
            the list of participants in the conversation
            (the human participant is the first entry)
        """
        log = self.log
        log.debug("generating 'conversation created' system message")
        conversation_created_msg = Message(
            conversation=self.conversation,
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.CREATED,
            approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
        )
        conversation_created_msg.save()
        log.info("conversation created")

        log.debug("creating participant for user", nickname=nickname)
        participant = self._create_human_participant(nickname)
        participants = [participant]
        log = log.bind(participant_name=participant.name)

        include_bots = [*bots]  # bots in conversation
        if (manager := getattr(settings, "CHAT_BOT_MANAGER", None)) is not None:
            include_bots.append(manager)
        for b in include_bots:
            log.debug("creating participant for bot", bot_name=b)
            bot_participant = Participant.objects.create(
                conversation=self.conversation,
                type=Participant.BOT,
                name=b,
                is_required=settings.CHAT_INSTALLED_BOTS.get(b)[2],
            )
            log.info(
                "bot joined conversation", bot_participant_id=str(bot_participant.id)
            )
            participants.append(bot_participant)
            log.debug(
                "generating 'participant joined' system message for bot", bot_name=b
            )
            # generate "participant joined" (bot) system message
            bot_joined_msg = Message(
                conversation=self.conversation,
                type=Message.MessageType.SYSTEM,
                text=Message.SystemEvent.JOINED,
                approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
                additional_metadata={
                    "participant_id": str(bot_participant.id),
                },
            )
            bot_joined_msg.save()
        return participants

    def generate_participant_joined_system_message(
        self, participant_id: str | UUID
    ) -> Message:
        """Create a message indicating that a participant has joined the conversation.

        Args:
            participant_id: id of the participant

        Returns:
            the created message
        """
        message = Message.objects.create(
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.JOINED,
            additional_metadata={
                "participant_id": str(participant_id),
            },
            conversation_id=str(self.conversation.id),
            approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
        )
        message.save()
        return message

    def _create_human_participant(self, nickname: str) -> Participant:
        participant = Participant.objects.create(
            conversation=self.conversation, type=Participant.HUMAN, name=nickname
        )
        if not nickname:  # fix anonymous nickname
            nickname = "ANON_" + str(participant.id)
            participant.name = nickname
        participant.save()
        return participant

    def join(self, nickname: str) -> Participant:
        """Create a Participant instance when a human user joins a conversation.

        This method creates the participant instance and generates a system message
        indicating that it have joined the conversation.

        Args:
            nickname: name of the user who joined the conversation

        Returns:
            the new participant instance corresponding to the participant who joined
        """
        self.log.debug("creating participant for user", nickname=nickname)
        return self._create_human_participant(nickname)

    def save_message(
        self, participant: Participant, message_data: dict[str, Any]
    ) -> Message:
        """Store a message sent by a human or bot.

        Args:
            participant: the sender
            message_data: mesesage data as a dictionary

        Returns:
            the created Message instance
        """
        if participant.conversation.id != self.conversation.id:
            error = "This participant belongs to another conversation"
            raise ValueError(error)

        manager = getattr(settings, "CHAT_BOT_MANAGER", None)
        if participant.type == Participant.HUMAN or not manager:
            approval_status = Message.ApprovalStatus.AUTOMATICALLY_APPROVED
        else:
            approval_status = Message.ApprovalStatus.NO

        overridden_data = {
            "conversation_id": str(self.conversation.id),
            "sender_id": str(participant.id),
            "approval_status": approval_status,
        }

        from_manager = (
            participant.type == Participant.BOT and participant.name == manager
        )

        j = {}
        if from_manager:

            command = message_data.get("command", "{}")
            try:
                j = json.loads(command)
            except json.decoder.JSONDecodeError:
                j = None
            if not isinstance(j, dict):
                self.log.warning(
                    "ignoring malformed message from manager bot", command=command
                )
                j = {}

            self_approve = j.get("self_approve", False)
            if isinstance(self_approve, bool) and self_approve:
                overridden_data[
                    "approval_status"
                ] = Message.ApprovalStatus.APPROVED_BY_BOT_MANAGER
                self.log.info(
                    "manager bot self-approved message",
                    local_id=message_data.get("local_id", ""),
                )

            on_behalf_of = j.get("on_behalf_of", None)
            if on_behalf_of:
                try:
                    principal = Participant.objects.get(id=str(on_behalf_of))
                    # here, principal is the inverse of proxy (as in legal language)
                    if principal.conversation.id != self.conversation.id:
                        principal = None
                except Participant.DoesNotExist:
                    principal = None
                if not principal:
                    self.log.warning(
                        "ignoring message that the manager bot tried to send by proxy "
                        "on behalf of another participant",
                        on_behalf_of=on_behalf_of,
                    )
                overridden_data["sender_id"] = str(principal.id)

            action = j.get("action", "")
            quoted_message_id = message_data.get("quoted_message_id", None)
            quoted_message = None
            if quoted_message_id:
                try:
                    quoted_message = Message.objects.get(m_id=quoted_message_id)
                except Message.DoesNotExist:
                    quoted_message = None
                if quoted_message.conversation.id != participant.conversation.id:
                    quoted_message = None

            match action:
                case "approve":

                    if not quoted_message:
                        self.log.warning(
                            "manager bot tried to approve a non-existent message",
                            approved_message_id=quoted_message_id,
                        )
                    else:
                        self.log.info(
                            "manager bot approved message",
                            approved_message_id=quoted_message_id,
                        )
                        quoted_message.approval_status = (
                            Message.ApprovalStatus.APPROVED_BY_BOT_MANAGER
                        )
                        quoted_message.save()
                case "redirect":
                    if not quoted_message:
                        self.log.warning(
                            "manager bot tried to redirect a non-existent message",
                            redirected_message_id=quoted_message_id,
                        )
                    else:
                        targets = j.get("bots", [])
                        field_overrides = j.get("overrides", None)
                        self.log.info(
                            "manager bot redirected message",
                            redirected_message_id=quoted_message_id,
                            bots=targets,
                        )
                        self._redirect_message(quoted_message, targets, field_overrides)
                case _:
                    if action:
                        self.log.warning(
                            "ignoring unknown action from manager bot", action=action
                        )
        else:
            message_data.pop("command", None)

        created_message = MessageSerializer.create_message(
            {**message_data, **overridden_data, "sent_by_manager": from_manager},
        )

        if from_manager:
            self_redirect = j.get("self_redirect", False)
            if isinstance(self_redirect, bool) and self_redirect:
                targets = j.get("bots", [])
                self.log.info(
                    "manager bot self-redirected message",
                    redirected_message_id=str(created_message.m_id),
                    bots=targets,
                )

                transaction.on_commit(
                    lambda: self._redirect_message(
                        created_message, targets, j.get("overrides", None)
                    )
                )
        return created_message

    # noinspection PyMethodMayBeStatic
    def _redirect_message(
        self,
        message: Message,
        targets: list[str],
        field_overrides: dict[str, Any] | None = None,
    ) -> None:
        # importing here to avoid circular imports

        from .consumers import ConversationConsumer
        from .tasks import deliver_message_to_bot

        for part in targets:
            # if bot uses WebSockets
            async_to_sync(ConversationConsumer.deliver_message_to_bot)(
                message,
                part,
                field_overrides=field_overrides,
            )
            # if bot is internal
            q = Q(name=part)
            try:
                u = UUID(part)
            except ValueError:
                pass
            else:
                q |= Q(id=u)
            b = (
                message.conversation.participants.filter(q)
                .filter(type=Participant.BOT)
                .first()
            )

            func = (
                deliver_message_to_bot.delay
                if settings.CHAT_ENABLE_QUEUE
                else deliver_message_to_bot
            )
            func(
                str(b.id),
                message.id,
                field_overrides=field_overrides,
            )

    def deliver_message_to_bot(
        self,
        message: Message,
        bot: Participant,
        field_overrides: dict[str, Any] | None = None,
    ) -> None:
        """Deliver a message only to the specified bot.

        Args:
            message: the message to be delivered
            bot: the bot which will receive the message
            field_overrides: dict from field names to the values that
                should replace the actual values
        """
        if bot.conversation.id != self.conversation.id:
            error = "Participant is not in the conversation"
            raise ValueError(error)
        if message.conversation.id != self.conversation.id:
            error = "Message is not in the conversation"
            raise ValueError(error)
        if bot.type != Participant.BOT:
            error = "Participant is not a bot"
            raise ValueError(error)
        bot = _get_bot(all_bots()[bot.name], bot.id, bot.conversation.id)
        message_data = {
            **MessageSerializer().to_representation(message),
            **(field_overrides or {}),
        }
        bot.receive_message(ChatMessage.from_dict(message_data))

    def deliver_status_to_bot(self, status: dict[str, Any], bot: Participant) -> None:
        """Deliver status only to the specified bot.

        Args:
            status: the status information to be delivered
            bot: the bot which will receive the message
        """
        if bot.conversation.id != self.conversation.id:
            error = "Participant is not in the conversation"
            raise ValueError(error)
        if bot.type != Participant.BOT:
            error = "Participant is not a bot"
            raise ValueError(error)
        bot = _get_bot(all_bots()[bot.name], bot.id, bot.conversation.id)
        bot.update_status(status)

    @classmethod
    def get_chat(cls, conversation_id: str | UUID) -> Chat | None:
        """Obtain a Chat instance for a given conversation.

        Args:
            conversation_id: id of the conversation

        Returns:
            a Chat instance if it exists for the given conversation id,
            of None if it does not exist
        """
        return cls._all_chats.get(str(conversation_id)) or Chat(
            Conversation.objects.get(id=conversation_id)
        )


class ChatLimits(TypedDict):
    """Maximum size of each attachment type."""

    MAX_ATTACHMENT_SIZE: int
    """maximum size of an attached file (in bytes)"""

    MAX_IMAGE_SIZE: int
    """maximum size of an image file (in bytes)"""

    MAX_VIDEO_SIZE: int
    """maximum size of a video file (in bytes)"""

    MAX_AUDIO_SIZE: int
    """maximum size of an audio file (in bytes)"""

    MAX_VOICE_SIZE: int
    """maximum size of a voice recording file (in bytes)"""
