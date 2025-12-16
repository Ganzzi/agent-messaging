"""Unit tests for OneWayMessenger."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.models import Agent, MessageType, Organization
from agent_messaging.handlers.types import MessageContext
from agent_messaging.exceptions import AgentNotFoundError, NoHandlerRegisteredError
from agent_messaging.handlers import register_one_way_handler, clear_handlers


@pytest.fixture(autouse=True)
def clean_handlers_fixture():
    """Clean handlers before and after each test."""
    clear_handlers()
    yield
    clear_handlers()


@pytest.fixture
def mock_invoke_handler_async():
    """Mock for the global invoke_handler_async function."""
    with patch("agent_messaging.messaging.one_way.invoke_handler_async") as mock:
        mock.return_value = None
        yield mock


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
    repo.get_organization = AsyncMock(
        return_value=Organization(
            id=uuid4(),
            external_id="test_org",
            name="Test Org",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    return repo


@pytest.fixture
def one_way_messenger(mock_message_repo, mock_agent_repo):
    """OneWayMessenger instance for testing."""
    return OneWayMessenger(
        message_repo=mock_message_repo,
        agent_repo=mock_agent_repo,
    )


class TestOneWayMessenger:
    """Test cases for OneWayMessenger."""

    @pytest.mark.asyncio
    async def test_send_success(
        self, one_way_messenger, mock_agent_repo, mock_message_repo, mock_invoke_handler_async
    ):
        """Test successful one-way message sending."""

        # Register a handler
        @register_one_way_handler
        async def test_handler(message, context):
            pass

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
            metadata={},  # Phase 4: metadata parameter added
        )

        # Verify handler was invoked
        mock_invoke_handler_async.assert_called_once()
        call_args = mock_invoke_handler_async.call_args
        assert call_args[0][0] == {"text": "Hello!"}  # message (positional arg 0)
        assert isinstance(call_args[0][1], MessageContext)  # context (positional arg 1)

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
    async def test_send_no_handler(self, one_way_messenger, mock_agent_repo):
        """Test sending message when no handler is registered."""
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

        # Don't register any handler - ensure handlers are cleared
        with pytest.raises(NoHandlerRegisteredError, match="No one-way handler registered"):
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
