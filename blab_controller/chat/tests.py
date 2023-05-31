from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Conversation, Message, Participant
from .serializers import MessageSerializer


class ConversationTest(TestCase):
    def setUp(self) -> None:
        self.c = Conversation.objects.create()
        self.p1 = Participant.objects.create(name="P1", type="H", conversation=self.c)
        self.p2 = Participant.objects.create(name="P2", type="H", conversation=self.c)
        self.psys = Participant.objects.create(
            name="SYS", type="S", conversation=self.c
        )
        self.c_other = Conversation.objects.create()
        self.p3 = Participant.objects.create(
            name="P3", type="H", conversation=self.c_other
        )

    def test_empty_conversation(self) -> None:
        c = Conversation.objects.create()
        assert list(c.participants.all()) == []
        assert list(c.messages.all()) == []

    def test_message_from_non_existing_sender(self) -> None:
        self.c.participants.set([self.p1])
        m1 = Message.objects.create(
            type=Message.MessageType.TEXT,
            text="Hi",
            conversation=self.c,
            sender=self.p1,
        )
        with self.assertRaises(ValidationError):
            Message.objects.create(
                type=Message.MessageType.TEXT,
                text="Hello",
                conversation=self.c,
                sender=self.p3,
            )
        assert list(self.c.messages.all()) == [m1]

    def test_message_from_system(self) -> None:
        m1 = Message.objects.create(
            type=Message.MessageType.TEXT,
            text="Hi",
            conversation=self.c,
            sender=self.p1,
        )

        m2 = Message.objects.create(
            type=Message.MessageType.TEXT,
            text="System message",
            conversation=self.c,
            sender=self.psys,
        )
        assert list(self.c.messages.all()) == [m1, m2]

    def test_simple_conversation(self) -> None:
        m1 = Message.objects.create(
            type=Message.MessageType.TEXT,
            text="Hi",
            conversation=self.c,
            sender=self.p1,
        )
        m2 = Message.objects.create(
            type=Message.MessageType.TEXT,
            text="Hello",
            conversation=self.c,
            sender=self.p2,
        )
        assert list(self.c.messages.all()) == [m1, m2]

    def test_simple_conversation_2(self) -> None:
        texts = ["Hi", "Hello"]
        s1 = MessageSerializer(
            data={
                "type": Message.MessageType.TEXT,
                "text": texts[0],
                "conversation_id": self.c.id,
                "sender_id": self.p1.id,
            }
        )
        s1.is_valid(raise_exception=True)
        s1.save()
        s2 = MessageSerializer(
            data={
                "type": Message.MessageType.TEXT,
                "text": texts[1],
                "conversation_id": self.c.id,
                "sender_id": self.p2.id,
            }
        )
        s2.is_valid(raise_exception=True)
        s2.save()
        messages = self.c.messages.all()
        assert len(messages) == len(texts)
        assert texts[0] == messages[0].text
        assert texts[1] == messages[1].text
