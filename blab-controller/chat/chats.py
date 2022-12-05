"""Contains code that controls the events in a chat."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings

from . import blab_logger as logger
from .models import Conversation, Message, Participant


class Chat:
    """Represents a conversation.

    Note that the Conversation represents a database entity, whereas
    Chat contains methods that manage the events that occur in a conversation.
    """

    _all_chats = {}

    def __init__(self, conversation_id: str | UUID):
        """
        .

        Args:
            conversation_id: id of the conversation
        """
        if str(conversation_id) in self.__class__._all_chats:
            raise ValueError("Chat instance already created for this conversation")
        self.__class__._all_chats[str(conversation_id)] = self

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
        log = logger.bind(conversation_id=str(conversation.id))

        log.debug("generating 'conversation created' system message")
        conversation_created_msg = Message(
            conversation=conversation,
            type=Message.MessageType.SYSTEM,
            text=Message.SystemEvent.CREATED,
            approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
        )
        conversation_created_msg.save()

        log.debug("creating participant for user")
        participant = Participant.objects.create(
            conversation=conversation, type=Participant.HUMAN, name=nickname
        )
        log = log.bind(conversation_id=str(participant.id))
        participants = [participant]

        if not nickname:  # fix anonymous nickname
            nickname = "ANON_" + str(participant.id)
            participant.name = nickname
        participant.save()
        log = log.bind(participant_name=participant.name)

        log.info("conversation created")

        include_bots = [*bots]  # bots in conversation
        if (manager := getattr(settings, "CHAT_BOT_MANAGER", None)) is not None:
            include_bots.append(manager)
        for b in include_bots:
            log.debug("creating participant for bot", bot_name=b)
            bot_participant = Participant.objects.create(
                conversation=conversation, type=Participant.BOT, name=b
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
                conversation=conversation,
                type=Message.MessageType.SYSTEM,
                text=Message.SystemEvent.JOINED,
                approval_status=Message.ApprovalStatus.AUTOMATICALLY_APPROVED,
                additional_metadata={
                    "participant_id": str(bot_participant.id),
                },
            )
            bot_joined_msg.save()
        Chat(conversation.id)
        return participants

    def join(self, nickname: str) -> Participant:
        """Create a Participant instance when a human user joins an existing conversation.

        Args:
            nickname: name of the user who joined the conversation

        Returns:
            the participant instance corresponding to the participant who joined
        """
        pass

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
