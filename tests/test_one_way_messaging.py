"""Unit tests for OneWayMessenger."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.models import Agent, MessageType, MessageContext
from agent_messaging.exceptions import AgentNotFoundError, NoHandlerRegisteredError


@pytest.fixture
def mock_handler_registry():
    """Mock handler registry for testing."""
    registry = MagicMock()
    registry.has_handler.return_value = True
    registry.invoke_handler_async.return_value = MagicMock()
    return registry


@pytest.fixture
def mock_message_repo():
    """Mock message repository for testing."""
    repo = MagicMock()
    repo.create = AsyncMock(return_value=uuid4())
    repo.get_unread_messages_from_sender = AsyncMock(return_value=[])
    repo.mark_as_read = AsyncMock()
    repo.get_unread_messages = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_agent_repo():
    """Mock agent repository for testing."""
    repo = MagicMock()
    repo.get_by_external_id = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def one_way_messenger(mock_handler_registry, mock_message_repo, mock_agent_repo):
    """OneWayMessenger instance for testing."""
    return OneWayMessenger(
        handler_registry=mock_handler_registry,
        message_repo=mock_message_repo,
        agent_repo=mock_agent_repo,
    )


class TestOneWayMessenger:
    """Test cases for OneWayMessenger."""

    @pytest.mark.asyncio
    async def test_send_success(
        self, one_way_messenger, mock_agent_repo, mock_message_repo, mock_handler_registry
    ):
        """Test successful one-way message sending."""
        # Setup mock agents
        sender = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        recipient = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, recipient])
        mock_message_repo.create = AsyncMock(return_value=uuid4())

        # Send message
        message_ids = await one_way_messenger.send("alice", ["bob"], {"text": "Hello!"})

        # Verify message was created
        assert len(message_ids) == 1
        assert message_ids[0] is not None
        mock_message_repo.create.assert_called_once_with(
            sender_id=sender.id,
            recipient_id=recipient.id,
            content={"text": "Hello!"},
            message_type=MessageType.USER_DEFINED,
        )

        # Verify handler was invoked
        mock_handler_registry.invoke_handler_async.assert_called_once()
        call_args = mock_handler_registry.invoke_handler_async.call_args
        assert call_args[0][0] == {"text": "Hello!"}  # message
        assert isinstance(call_args[0][1], MessageContext)  # context

    @pytest.mark.asyncio
    async def test_send_sender_not_found(self, one_way_messenger, mock_agent_repo):
        """Test sending message with non-existent sender."""
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError, match="Sender agent not found: alice"):
            await one_way_messenger.send("alice", ["bob"], {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_send_recipient_not_found(self, one_way_messenger, mock_agent_repo):
        """Test sending message with non-existent recipient."""
        sender = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, None])

        with pytest.raises(AgentNotFoundError, match="Recipient agent not found: bob"):
            await one_way_messenger.send("alice", ["bob"], {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_send_no_handler(self, one_way_messenger, mock_agent_repo, mock_handler_registry):
        """Test sending message when recipient has no handler."""
        sender = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        recipient = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, recipient])
        mock_handler_registry.has_handler.return_value = False

        with pytest.raises(NoHandlerRegisteredError, match="No handler registered"):
            await one_way_messenger.send("alice", ["bob"], {"text": "Hello!"})

    def test_serialize_content_dict(self, one_way_messenger):
        """Test content serialization for dict input."""
        result = one_way_messenger._serialize_content({"text": "Hello!"})
        assert result == {"text": "Hello!"}

    def test_serialize_content_pydantic(self, one_way_messenger):
        """Test content serialization for Pydantic model input."""
        from pydantic import BaseModel

        class TestMessage(BaseModel):
            text: str
            number: int

        message = TestMessage(text="Hello!", number=42)
        result = one_way_messenger._serialize_content(message)
        assert result == {"text": "Hello!", "number": 42}

    def test_serialize_content_other(self, one_way_messenger):
        """Test content serialization for other types."""
        result = one_way_messenger._serialize_content("plain string")
        assert result == {"data": "plain string"}
