"""Contains code that controls the events in a chat."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings

from . import blab_logger as logger
from .models import Conversation, Message, Participant
from .serializers import MessageSerializer


class Chat:
    """Represents a conversation.

    Note that the Conversation represents a database entity, whereas
    Chat contains methods that manage the events that occur in a conversation.
    """

    _all_chats = {}

    def __init__(self, conversation: Conversation):
        """
        .

        Args:
            conversation: Conversation instance
        """
        self.conversation: Conversation = conversation

        conversation_id = str(self.conversation.id)
        if str(conversation_id) in self.__class__._all_chats:
            raise ValueError("Chat instance already created for this conversation")
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

        Return:
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

        Return:
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
                conversation=self.conversation, type=Participant.BOT, name=b
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

        Return:
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
        """Create a Participant instance when a human user joins an existing conversation.

        This method creates the participant instance and generates a system message
        indicating that it have joined the conversation.

        Args:
            nickname: name of the user who joined the conversation

        Returns:
            the new participant instance corresponding to the participant who joined
        """
        self.log.debug("creating participant for user", nickname=nickname)
        participant = self._create_human_participant(nickname)
        return participant

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
            raise ValueError("This participant belongs to another conversation")
        if participant.type == Participant.HUMAN or not settings.get(
            "CHAT_BOT_MANAGER", None
        ):
            approval_status = Message.ApprovalStatus.AUTOMATICALLY_APPROVED
        else:
            approval_status = Message.ApprovalStatus.NO
        overridden_data = {
            "conversation_id": str(self.conversation.id),
            "sender_id": str(participant.id),
            "approval_status": approval_status,
        }
        return MessageSerializer.create_message({**message_data, **overridden_data})

    @classmethod
    def get_chat(cls, conversation_id: str | UUID) -> Chat | None:
        """Obtain a Chat instance for a given conversation.

        Args:
            conversation_id: id of the conversation

        Return:
            a Chat instance if it exists for the given conversation id,
            of None if it does not exist
        """
        return cls._all_chats.get(str(conversation_id))
