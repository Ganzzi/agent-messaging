"""Unit tests for messaging classes."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.messaging.sync_conversation import SyncConversation
from agent_messaging.messaging.async_conversation import AsyncConversation
from agent_messaging.models import (
    Agent,
    MessageContext,
    MessageType,
    Session,
    SessionStatus,
    SessionType,
)
from agent_messaging.exceptions import AgentNotFoundError, NoHandlerRegisteredError, TimeoutError


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
    return repo


@pytest.fixture
def mock_agent_repo():
    """Mock agent repository for testing."""
    repo = MagicMock()
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
        message_id = await one_way_messenger.send("alice", "bob", {"text": "Hello!"})

        # Verify message was created
        assert message_id is not None
        mock_message_repo.create.assert_called_once_with(
            sender_id=sender.id,
            recipient_id=recipient.id,
            content={"text": "Hello!"},
            message_type=MessageType.USER_DEFINED,
        )

        # Verify handler was invoked
        mock_handler_registry.invoke_handler_async.assert_called_once()
        call_args = mock_handler_registry.invoke_handler_async.call_args
        assert call_args[0][0] == "bob"  # recipient_external_id
        assert call_args[0][1] == {"text": "Hello!"}  # message
        assert isinstance(call_args[0][2], MessageContext)  # context

    @pytest.mark.asyncio
    async def test_send_sender_not_found(self, one_way_messenger, mock_agent_repo):
        """Test sending message with non-existent sender."""
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError, match="Sender agent not found: alice"):
            await one_way_messenger.send("alice", "bob", {"text": "Hello!"})

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
            await one_way_messenger.send("alice", "bob", {"text": "Hello!"})

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

        with pytest.raises(
            NoHandlerRegisteredError, match="No handler registered for recipient: bob"
        ):
            await one_way_messenger.send("alice", "bob", {"text": "Hello!"})

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


# SyncConversation Fixtures and Tests


@pytest.fixture
def mock_session_repo():
    """Mock session repository for testing."""
    repo = MagicMock()
    return repo


@pytest.fixture
def sync_conversation(mock_handler_registry, mock_message_repo, mock_session_repo, mock_agent_repo):
    """SyncConversation instance for testing."""
    return SyncConversation(
        handler_registry=mock_handler_registry,
        message_repo=mock_message_repo,
        session_repo=mock_session_repo,
        agent_repo=mock_agent_repo,
    )


class TestSyncConversation:
    """Test cases for SyncConversation."""

    @pytest.mark.asyncio
    async def test_send_and_wait_success(
        self,
        sync_conversation,
        mock_agent_repo,
        mock_session_repo,
        mock_message_repo,
        mock_handler_registry,
    ):
        """Test successful send_and_wait conversation."""
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

        # Setup mock session
        session_id = uuid4()
        session = Session(
            id=session_id,
            agent_a_id=sender.id,
            agent_b_id=recipient.id,
            session_type=SessionType.SYNC,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, recipient])
        mock_session_repo.get_active_session = AsyncMock(return_value=None)
        mock_session_repo.create = AsyncMock(return_value=session_id)
        mock_session_repo.get_by_id = AsyncMock(return_value=session)
        mock_session_repo.set_locked_agent = AsyncMock()
        mock_message_repo.create = AsyncMock(return_value=uuid4())
        mock_message_repo.pool = MagicMock()
        mock_message_repo.pool.acquire = AsyncMock()

        # Mock the lock context manager
        lock_mock = AsyncMock()
        lock_mock.__aenter__ = AsyncMock(return_value=True)
        lock_mock.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=lock_mock)
        mock_message_repo.pool.acquire.return_value.__aexit__ = AsyncMock()

        # Setup response
        response_message = {"reply": "Hello back!"}
        sync_conversation._waiting_responses[session_id] = response_message

        # Send and wait
        response = await sync_conversation.send_and_wait(
            "alice", "bob", {"text": "Hello!"}, timeout=5.0
        )

        # Verify response
        assert response == response_message

        # Verify session was created
        mock_session_repo.create.assert_called_once_with(sender.id, recipient.id, SessionType.SYNC)

        # Verify message was created
        mock_message_repo.create.assert_called_once()

        # Verify handler was invoked
        mock_handler_registry.invoke_handler_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_and_wait_timeout(
        self,
        sync_conversation,
        mock_agent_repo,
        mock_session_repo,
        mock_message_repo,
        mock_handler_registry,
    ):
        """Test send_and_wait with timeout."""
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

        # Setup mock session
        session_id = uuid4()
        session = Session(
            id=session_id,
            agent_a_id=sender.id,
            agent_b_id=recipient.id,
            session_type=SessionType.SYNC,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, recipient])
        mock_session_repo.get_active_session = AsyncMock(return_value=None)
        mock_session_repo.create = AsyncMock(return_value=session_id)
        mock_session_repo.get_by_id = AsyncMock(return_value=session)
        mock_session_repo.set_locked_agent = AsyncMock()
        mock_message_repo.create = AsyncMock(return_value=uuid4())
        mock_message_repo.pool = MagicMock()
        mock_message_repo.pool.acquire = AsyncMock()

        # Mock the lock context manager
        lock_mock = AsyncMock()
        lock_mock.__aenter__ = AsyncMock(return_value=True)
        lock_mock.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=lock_mock)
        mock_message_repo.pool.acquire.return_value.__aexit__ = AsyncMock()

        # Send and wait (should timeout since no response is set)
        with pytest.raises(TimeoutError, match="No response received within 1.0 seconds"):
            await sync_conversation.send_and_wait("alice", "bob", {"text": "Hello!"}, timeout=1.0)

    @pytest.mark.asyncio
    async def test_reply_success(self, sync_conversation, mock_agent_repo, mock_session_repo):
        """Test successful reply to conversation."""
        # Setup mock agents
        responder = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        # Setup mock session
        session_id = uuid4()
        session = Session(
            id=session_id,
            agent_a_id=uuid4(),
            agent_b_id=responder.id,
            session_type=SessionType.SYNC,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=responder)
        mock_session_repo.get_by_id = AsyncMock(return_value=session)

        # Setup waiting event
        event = AsyncMock()
        sync_conversation._waiting_events[session_id] = event

        # Reply
        await sync_conversation.reply(session_id, "bob", {"reply": "Hello back!"})

        # Verify response was stored
        assert session_id in sync_conversation._waiting_responses
        assert sync_conversation._waiting_responses[session_id] == {"reply": "Hello back!"}

        # Verify event was set
        event.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_conversation_success(
        self,
        sync_conversation,
        mock_agent_repo,
        mock_session_repo,
        mock_message_repo,
        mock_handler_registry,
    ):
        """Test successful conversation ending."""
        # Setup mock agents
        agent1 = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        agent2 = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        # Setup mock session
        session_id = uuid4()
        session = Session(
            id=session_id,
            agent_a_id=agent1.id,
            agent_b_id=agent2.id,
            session_type=SessionType.SYNC,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[agent1, agent2])
        mock_session_repo.get_active_session = AsyncMock(return_value=session)
        mock_session_repo.end_session = AsyncMock()
        mock_handler_registry.has_handler = MagicMock(return_value=True)
        mock_message_repo.create = AsyncMock(return_value=uuid4())

        # End conversation
        await sync_conversation.end_conversation("alice", "bob")

        # Verify session was ended
        mock_session_repo.end_session.assert_called_once_with(session_id)

        # Verify ending messages were sent
        assert mock_message_repo.create.call_count == 2  # One for each agent

    def test_serialize_content_dict(self, sync_conversation):
        """Test content serialization for dict input."""
        result = sync_conversation._serialize_content({"text": "Hello!"})
        assert result == {"text": "Hello!"}

    def test_serialize_content_pydantic(self, sync_conversation):
        """Test content serialization for Pydantic model input."""
        from pydantic import BaseModel

        class TestMessage(BaseModel):
            text: str
            number: int

        message = TestMessage(text="Hello!", number=42)
        result = sync_conversation._serialize_content(message)
        assert result == {"text": "Hello!", "number": 42}

    def test_serialize_content_other(self, sync_conversation):
        """Test content serialization for other types."""
        result = sync_conversation._serialize_content("plain string")
        assert result == {"data": "plain string"}


@pytest.fixture
def mock_session_repo():
    """Mock session repository for testing."""
    repo = MagicMock()
    return repo


@pytest.fixture
def async_conversation(
    mock_handler_registry, mock_message_repo, mock_session_repo, mock_agent_repo
):
    """AsyncConversation instance for testing."""
    return AsyncConversation(
        handler_registry=mock_handler_registry,
        message_repo=mock_message_repo,
        session_repo=mock_session_repo,
        agent_repo=mock_agent_repo,
    )


class TestAsyncConversation:
    """Test cases for AsyncConversation."""

    @pytest.mark.asyncio
    async def test_send_success(
        self,
        async_conversation,
        mock_agent_repo,
        mock_session_repo,
        mock_message_repo,
        mock_handler_registry,
    ):
        """Test successful async message sending."""
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

        # Setup mock session
        session_id = uuid4()
        session = Session(
            id=session_id,
            agent_a_id=sender.id,
            agent_b_id=recipient.id,
            session_type=SessionType.ASYNC,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[sender, recipient])
        mock_session_repo.get_active_session = AsyncMock(return_value=None)
        mock_session_repo.create = AsyncMock(return_value=session_id)
        mock_session_repo.get_by_id = AsyncMock(return_value=session)
        mock_message_repo.create = AsyncMock(return_value=uuid4())

        # Send message
        result_session_id = await async_conversation.send("alice", "bob", {"text": "Hello!"})

        # Verify session ID was returned
        assert result_session_id == session_id

        # Verify session was created
        mock_session_repo.create.assert_called_once_with(sender.id, recipient.id, SessionType.ASYNC)

        # Verify message was created
        mock_message_repo.create.assert_called_once()
        call_args = mock_message_repo.create.call_args
        assert call_args[1]["sender_id"] == sender.id
        assert call_args[1]["recipient_id"] == recipient.id
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["content"] == {"text": "Hello!"}
        assert call_args[1]["message_type"] == MessageType.USER_DEFINED

        # Verify handler was invoked
        mock_handler_registry.invoke_handler_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_sender_not_found(self, async_conversation, mock_agent_repo):
        """Test send with non-existent sender."""
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError, match="Sender agent not found: alice"):
            await async_conversation.send("alice", "bob", {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_send_recipient_not_found(self, async_conversation, mock_agent_repo):
        """Test send with non-existent recipient."""
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
            await async_conversation.send("alice", "bob", {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_get_unread_messages(
        self, async_conversation, mock_agent_repo, mock_message_repo
    ):
        """Test getting unread messages for an agent."""
        from agent_messaging.models import Message

        # Setup mock agent
        agent_id = uuid4()
        agent = Agent(
            id=agent_id,
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        # Setup mock messages
        message1 = Message(
            id=uuid4(),
            sender_id=uuid4(),
            recipient_id=agent_id,
            session_id=uuid4(),
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello 1"},
            read_at=None,
            created_at=MagicMock(),
            metadata=None,
        )
        message2 = Message(
            id=uuid4(),
            sender_id=uuid4(),
            recipient_id=agent_id,
            session_id=uuid4(),
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello 2"},
            read_at=None,
            created_at=MagicMock(),
            metadata=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=agent)
        mock_message_repo.get_unread_messages = AsyncMock(return_value=[message1, message2])
        mock_message_repo.mark_as_read = AsyncMock()

        # Get unread messages
        messages = await async_conversation.get_unread_messages("bob")

        # Verify results
        assert len(messages) == 2
        assert messages[0] == {"text": "Hello 1"}
        assert messages[1] == {"text": "Hello 2"}

        # Verify messages were marked as read
        assert mock_message_repo.mark_as_read.call_count == 2

    @pytest.mark.asyncio
    async def test_get_messages_from_agent(
        self, async_conversation, mock_agent_repo, mock_message_repo
    ):
        """Test getting messages from a specific agent."""
        from agent_messaging.models import Message

        # Setup mock agents
        recipient_id = uuid4()
        sender_id = uuid4()
        recipient = Agent(
            id=recipient_id,
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        sender = Agent(
            id=sender_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        # Setup mock message
        message = Message(
            id=uuid4(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=uuid4(),
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello from Alice"},
            read_at=None,
            created_at=MagicMock(),
            metadata=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[recipient, sender])
        mock_message_repo.get_messages_between_agents = AsyncMock(return_value=[message])
        mock_message_repo.mark_as_read = AsyncMock()

        # Get messages
        messages = await async_conversation.get_messages_from_agent("bob", "alice")

        # Verify results
        assert len(messages) == 1
        assert messages[0] == {"text": "Hello from Alice"}

        # Verify message was marked as read
        mock_message_repo.mark_as_read.assert_called_once_with(message.id)

    @pytest.mark.asyncio
    async def test_wait_for_message_success(
        self, async_conversation, mock_agent_repo, mock_message_repo
    ):
        """Test waiting for a message from a specific agent."""
        from agent_messaging.models import Message

        # Setup mock agents
        recipient_id = uuid4()
        sender_id = uuid4()
        recipient = Agent(
            id=recipient_id,
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        sender = Agent(
            id=sender_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        # Setup mock message
        message = Message(
            id=uuid4(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=uuid4(),
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content={"text": "Hello Bob"},
            read_at=None,
            created_at=MagicMock(),
            metadata=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[recipient, sender])
        mock_message_repo.get_unread_messages_from_sender = AsyncMock(return_value=[message])
        mock_message_repo.mark_as_read = AsyncMock()

        # Wait for message
        result = await async_conversation.wait_for_message("bob", "alice", timeout=1.0)

        # Verify result
        assert result == {"text": "Hello Bob"}
        mock_message_repo.mark_as_read.assert_called_once_with(message.id)

    @pytest.mark.asyncio
    async def test_wait_for_message_timeout(
        self, async_conversation, mock_agent_repo, mock_message_repo
    ):
        """Test waiting for a message with timeout."""
        # Setup mock agents
        recipient_id = uuid4()
        sender_id = uuid4()
        recipient = Agent(
            id=recipient_id,
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        sender = Agent(
            id=sender_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[recipient, sender])
        mock_message_repo.get_unread_messages_from_sender = AsyncMock(return_value=[])

        # Wait for message (should timeout)
        result = await async_conversation.wait_for_message("bob", "alice", timeout=0.1)

        # Verify timeout
        assert result is None

    def test_serialize_content_dict(self, async_conversation):
        """Test content serialization for dict input."""
        result = async_conversation._serialize_content({"text": "Hello!"})
        assert result == {"text": "Hello!"}

    def test_serialize_content_pydantic(self, async_conversation):
        """Test content serialization for Pydantic model input."""
        from pydantic import BaseModel

        class TestMessage(BaseModel):
            text: str
            number: int

        message = TestMessage(text="Hello!", number=42)
        result = async_conversation._serialize_content(message)
        assert result == {"text": "Hello!", "number": 42}

    def test_serialize_content_other(self, async_conversation):
        """Test content serialization for other types."""
        result = async_conversation._serialize_content("plain string")
        assert result == {"data": "plain string"}
