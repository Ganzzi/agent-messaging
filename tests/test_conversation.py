"""Unit tests for Conversation class."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent_messaging.messaging.conversation import Conversation
from agent_messaging.models import (
    Agent,
    Message,
    MessageType,
    Session,
    SessionStatus,
)
from agent_messaging.exceptions import AgentNotFoundError, TimeoutError


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
def mock_session_repo():
    """Mock session repository for testing."""
    repo = MagicMock()
    repo.get_active_session = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=uuid4())
    repo.get_by_id = AsyncMock(return_value=None)
    repo.set_locked_agent = AsyncMock()
    repo.end_session = AsyncMock()
    return repo


@pytest.fixture
def conversation(mock_handler_registry, mock_message_repo, mock_session_repo, mock_agent_repo):
    """Conversation instance for testing."""
    return Conversation(
        handler_registry=mock_handler_registry,
        message_repo=mock_message_repo,
        session_repo=mock_session_repo,
        agent_repo=mock_agent_repo,
    )


class TestConversation:
    """Test cases for unified Conversation (combines sync and async patterns)."""

    @pytest.mark.asyncio
    async def test_send_and_wait_success(
        self,
        conversation,
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

        # Mock the connection context manager
        mock_connection = AsyncMock()
        mock_connection_cm = MagicMock()
        mock_connection_cm.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.db_manager.connection = MagicMock(return_value=mock_connection_cm)

        # Mock session lock
        with patch("agent_messaging.messaging.conversation.SessionLock") as mock_session_lock_class:
            mock_session_lock = AsyncMock()
            mock_session_lock.acquire = AsyncMock(return_value=True)
            mock_session_lock_class.return_value = mock_session_lock

            # Create a mock response message
            response_message = Message(
                id=uuid4(),
                sender_id=recipient.id,
                recipient_id=sender.id,
                session_id=session_id,
                meeting_id=None,
                message_type=MessageType.USER_DEFINED,
                content={"reply": "Hello back!"},
                read_at=None,
                created_at=MagicMock(),
                metadata=None,
            )

            # Mock get_unread_messages_from_sender to return the response
            mock_message_repo.get_unread_messages_from_sender = AsyncMock(
                return_value=[response_message]
            )
            mock_message_repo.mark_as_read = AsyncMock()

            # Mock asyncio.wait_for to return immediately (simulating event being set)
            with patch(
                "agent_messaging.messaging.conversation.asyncio.wait_for",
                new_callable=AsyncMock,
            ) as mock_wait_for:
                mock_wait_for.return_value = None  # Return immediately

            # Send and wait
            response = await conversation.send_and_wait(
                "alice", "bob", {"text": "Hello!"}, timeout=5.0
            )

            # Verify response
            assert response == {"reply": "Hello back!"}

            # Verify session was created
            mock_session_repo.create.assert_called_once_with(sender.id, recipient.id)

            # Verify message was marked as read
            mock_message_repo.mark_as_read.assert_called_once_with(response_message.id)

        # Verify message was created
        mock_message_repo.create.assert_called_once()

        # Verify handler was invoked
        mock_handler_registry.invoke_handler_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_and_wait_timeout(
        self,
        conversation,
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

        # Mock the connection context manager
        mock_connection = AsyncMock()
        mock_connection_cm = MagicMock()
        mock_connection_cm.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.db_manager.connection = MagicMock(return_value=mock_connection_cm)

        # Mock session lock
        with patch("agent_messaging.messaging.conversation.SessionLock") as mock_session_lock_class:
            mock_session_lock = AsyncMock()
            mock_session_lock.acquire = AsyncMock(return_value=True)
            mock_session_lock_class.return_value = mock_session_lock

            # Send and wait (should timeout since no response is set)
            with pytest.raises(TimeoutError, match="No response received within 1.0 seconds"):
                await conversation.send_and_wait("alice", "bob", {"text": "Hello!"}, timeout=1.0)

    @pytest.mark.asyncio
    async def test_end_conversation_success(
        self,
        conversation,
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
        await conversation.end_conversation("alice", "bob")

        # Verify session was ended
        mock_session_repo.end_session.assert_called_once_with(session_id)

        # Verify ending messages were sent
        assert mock_message_repo.create.call_count == 2  # One for each agent

    def test_serialize_content_dict(self, conversation):
        """Test content serialization for dict input."""
        result = conversation._serialize_content({"text": "Hello!"})
        assert result == {"text": "Hello!"}

    def test_serialize_content_pydantic(self, conversation):
        """Test content serialization for Pydantic model input."""
        from pydantic import BaseModel

        class TestMessage(BaseModel):
            text: str
            number: int

        message = TestMessage(text="Hello!", number=42)
        result = conversation._serialize_content(message)
        assert result == {"text": "Hello!", "number": 42}

    def test_serialize_content_other(self, conversation):
        """Test content serialization for other types."""
        result = conversation._serialize_content("plain string")
        assert result == {"data": "plain string"}

    @pytest.mark.asyncio
    async def test_send_no_wait_success(
        self,
        conversation,
        mock_agent_repo,
        mock_session_repo,
        mock_message_repo,
        mock_handler_registry,
    ):
        """Test successful send_no_wait (async messaging)."""
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
        await conversation.send_no_wait("alice", "bob", {"text": "Hello!"})

        # Verify session was created
        mock_session_repo.create.assert_called_once_with(sender.id, recipient.id)

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
    async def test_send_no_wait_sender_not_found(self, conversation, mock_agent_repo):
        """Test send_no_wait with non-existent sender."""
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError, match="Sender agent not found: alice"):
            await conversation.send_no_wait("alice", "bob", {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_send_no_wait_recipient_not_found(self, conversation, mock_agent_repo):
        """Test send_no_wait with non-existent recipient."""
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
            await conversation.send_no_wait("alice", "bob", {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_get_unread_messages_async(
        self, conversation, mock_agent_repo, mock_message_repo
    ):
        """Test getting unread messages for an agent (async version)."""
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
        messages = await conversation.get_unread_messages("bob")

        # Verify results
        assert len(messages) == 2
        assert messages[0] == {"text": "Hello 1"}
        assert messages[1] == {"text": "Hello 2"}

        # Verify messages were marked as read
        assert mock_message_repo.mark_as_read.call_count == 2

    @pytest.mark.asyncio
    async def test_get_or_wait_for_response_success(
        self, conversation, mock_agent_repo, mock_message_repo
    ):
        """Test waiting for a response from a specific agent."""
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
        result = await conversation.get_or_wait_for_response("bob", "alice", timeout=1.0)

        # Verify result
        assert result == {"text": "Hello Bob"}
        mock_message_repo.mark_as_read.assert_called_once_with(message.id)

    @pytest.mark.asyncio
    async def test_get_or_wait_for_response_timeout(
        self, conversation, mock_agent_repo, mock_message_repo, mock_session_repo
    ):
        """Test waiting for a response with timeout."""
        # Setup mock agents
        recipient_id = uuid4()
        sender_id = uuid4()
        session_id = uuid4()
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

        # Setup mock session
        session = Session(
            id=session_id,
            agent_a_id=sender_id,
            agent_b_id=recipient_id,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
            ended_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=[recipient, sender])
        mock_message_repo.get_unread_messages_from_sender = AsyncMock(return_value=[])
        mock_session_repo.get_active_session = AsyncMock(return_value=None)
        mock_session_repo.create = AsyncMock(return_value=session_id)
        mock_session_repo.get_by_id = AsyncMock(return_value=session)

        # Wait for message (should timeout)
        result = await conversation.get_or_wait_for_response("bob", "alice", timeout=0.1)

        # Verify timeout
        assert result is None
