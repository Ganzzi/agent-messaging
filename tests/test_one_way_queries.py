"""Tests for OneWayMessenger query methods."""

import pytest
from datetime import datetime, timedelta
from uuid import UUID

from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.exceptions import AgentNotFoundError


@pytest.mark.asyncio
class TestOneWayQueryMethods:
    """Test query methods for one-way messages."""

    async def test_get_sent_messages(self, one_way_messenger, mock_agent_repo, mock_message_repo):
        """Test getting sent messages."""
        from agent_messaging.models import Agent, Message, MessageType

        # Setup mocks
        sender = Agent(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            external_id="alice",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Alice",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        recipient = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        message = Message(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            sender_id=sender.id,
            recipient_id=recipient.id,
            session_id=None,  # One-way message
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello"},
            read_at=None,
            created_at=datetime.now(),
            metadata={},
        )

        mock_agent_repo.get_by_external_id.return_value = sender
        mock_agent_repo.get_by_id.return_value = recipient
        mock_message_repo.get_sent_messages.return_value = [message]

        # Call method
        result = await one_way_messenger.get_sent_messages("alice", limit=10, offset=0)

        # Verify
        assert len(result) == 1
        assert result[0]["sender_id"] == "alice"
        assert result[0]["recipient_id"] == "bob"
        assert result[0]["content"] == {"text": "Hello"}
        mock_message_repo.get_sent_messages.assert_called_once()

    async def test_get_sent_messages_sender_not_found(self, one_way_messenger, mock_agent_repo):
        """Test get_sent_messages with non-existent sender."""
        mock_agent_repo.get_by_external_id.return_value = None

        with pytest.raises(AgentNotFoundError, match="Sender agent not found"):
            await one_way_messenger.get_sent_messages("nonexistent")

    async def test_get_received_messages(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test getting received messages."""
        from agent_messaging.models import Agent, Message, MessageType

        sender = Agent(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            external_id="alice",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Alice",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        recipient = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        message = Message(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            sender_id=sender.id,
            recipient_id=recipient.id,
            session_id=None,
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello"},
            read_at=None,
            created_at=datetime.now(),
            metadata={},
        )

        mock_agent_repo.get_by_external_id.return_value = recipient
        mock_agent_repo.get_by_id.return_value = sender
        mock_message_repo.get_received_messages.return_value = [message]

        # Call method
        result = await one_way_messenger.get_received_messages(
            "bob", include_read=True, limit=10, offset=0
        )

        # Verify
        assert len(result) == 1
        assert result[0]["sender_id"] == "alice"
        assert result[0]["recipient_id"] == "bob"
        assert result[0]["content"] == {"text": "Hello"}
        mock_message_repo.get_received_messages.assert_called_once()

    async def test_get_received_messages_unread_only(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test getting only unread messages."""
        from agent_messaging.models import Agent

        recipient = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_agent_repo.get_by_external_id.return_value = recipient
        mock_message_repo.get_received_messages.return_value = []

        # Call method with include_read=False
        result = await one_way_messenger.get_received_messages(
            "bob", include_read=False, limit=10, offset=0
        )

        # Verify include_read parameter was passed
        mock_message_repo.get_received_messages.assert_called_once()
        call_kwargs = mock_message_repo.get_received_messages.call_args[1]
        assert call_kwargs["include_read"] is False

    async def test_mark_messages_read(self, one_way_messenger, mock_agent_repo, mock_message_repo):
        """Test marking messages as read."""
        from agent_messaging.models import Agent

        recipient = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_agent_repo.get_by_external_id.return_value = recipient
        mock_message_repo.mark_messages_read.return_value = 5

        # Call method
        count = await one_way_messenger.mark_messages_read("bob")

        # Verify
        assert count == 5
        mock_message_repo.mark_messages_read.assert_called_once_with(
            recipient_id=recipient.id, sender_id=None
        )

    async def test_mark_messages_read_from_specific_sender(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test marking messages as read from specific sender."""
        from agent_messaging.models import Agent

        sender = Agent(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            external_id="alice",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Alice",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        recipient = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        def get_agent(external_id):
            if external_id == "alice":
                return sender
            elif external_id == "bob":
                return recipient
            return None

        mock_agent_repo.get_by_external_id.side_effect = get_agent
        mock_message_repo.mark_messages_read.return_value = 3

        # Call method with sender filter
        count = await one_way_messenger.mark_messages_read("bob", sender_external_id="alice")

        # Verify
        assert count == 3
        mock_message_repo.mark_messages_read.assert_called_once_with(
            recipient_id=recipient.id, sender_id=sender.id
        )

    async def test_get_message_count_as_recipient(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test getting message count as recipient."""
        from agent_messaging.models import Agent

        agent = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_agent_repo.get_by_external_id.return_value = agent
        mock_message_repo.get_message_count.return_value = 10

        # Call method
        count = await one_way_messenger.get_message_count("bob", role="recipient")

        # Verify
        assert count == 10
        mock_message_repo.get_message_count.assert_called_once_with(
            recipient_id=agent.id, read_status=None
        )

    async def test_get_message_count_as_sender(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test getting message count as sender."""
        from agent_messaging.models import Agent

        agent = Agent(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            external_id="alice",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Alice",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_agent_repo.get_by_external_id.return_value = agent
        mock_message_repo.get_message_count.return_value = 15

        # Call method
        count = await one_way_messenger.get_message_count("alice", role="sender")

        # Verify
        assert count == 15
        mock_message_repo.get_message_count.assert_called_once_with(
            sender_id=agent.id, read_status=None
        )

    async def test_get_message_count_unread_only(
        self, one_way_messenger, mock_agent_repo, mock_message_repo
    ):
        """Test getting count of unread messages."""
        from agent_messaging.models import Agent

        agent = Agent(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            external_id="bob",
            organization_id=UUID("00000000-0000-0000-0000-000000000000"),
            name="Bob",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_agent_repo.get_by_external_id.return_value = agent
        mock_message_repo.get_message_count.return_value = 3

        # Call method with read_status=False
        count = await one_way_messenger.get_message_count(
            "bob", role="recipient", read_status=False
        )

        # Verify
        assert count == 3
        mock_message_repo.get_message_count.assert_called_once_with(
            recipient_id=agent.id, read_status=False
        )

    async def test_get_message_count_invalid_role(self, one_way_messenger):
        """Test get_message_count with invalid role."""
        with pytest.raises(ValueError, match="role must be 'recipient' or 'sender'"):
            await one_way_messenger.get_message_count("bob", role="invalid")
