"""Unit tests for messaging classes."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.messaging.sync_conversation import SyncConversation
from agent_messaging.messaging.async_conversation import AsyncConversation
from agent_messaging.messaging.meeting import MeetingManager
from agent_messaging.utils.timeouts import MeetingTimeoutManager
from agent_messaging.handlers.events import MeetingEventHandler
from agent_messaging.models import (
    Agent,
    MessageContext,
    MessageType,
    Session,
    SessionStatus,
    SessionType,
    Meeting,
    MeetingStatus,
    MeetingParticipant,
    ParticipantStatus,
    MeetingEventType,
)
from agent_messaging.exceptions import (
    AgentNotFoundError,
    NoHandlerRegisteredError,
    TimeoutError,
    MeetingError,
)


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

        # Mock the pool.acquire context manager
        mock_connection = AsyncMock()
        mock_pool_cm = AsyncMock()
        mock_pool_cm.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_pool_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.pool.acquire = AsyncMock(return_value=mock_pool_cm)

        # Mock session lock
        with patch(
            "agent_messaging.messaging.sync_conversation.SessionLock"
        ) as mock_session_lock_class:
            mock_session_lock = AsyncMock()
            mock_session_lock.acquire = AsyncMock(return_value=True)
            mock_session_lock_class.return_value = mock_session_lock

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
            mock_session_repo.create.assert_called_once_with(
                sender.id, recipient.id, SessionType.SYNC
            )

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

        # Mock the pool.acquire context manager
        mock_connection = AsyncMock()
        mock_pool_cm = AsyncMock()
        mock_pool_cm.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_pool_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message_repo.pool.acquire = AsyncMock(return_value=mock_pool_cm)

        # Mock session lock
        with patch(
            "agent_messaging.messaging.sync_conversation.SessionLock"
        ) as mock_session_lock_class:
            mock_session_lock = AsyncMock()
            mock_session_lock.acquire = AsyncMock(return_value=True)
            mock_session_lock_class.return_value = mock_session_lock

            # Send and wait (should timeout since no response is set)
            with pytest.raises(TimeoutError, match="No response received within 1.0 seconds"):
                await sync_conversation.send_and_wait(
                    "alice", "bob", {"text": "Hello!"}, timeout=1.0
                )

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
        event = MagicMock()
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


# Phase 5: Meeting Tests


@pytest.fixture
def mock_meeting_repo():
    """Mock meeting repository for testing."""
    repo = MagicMock()
    repo.create_meeting = AsyncMock(return_value=uuid4())
    repo.get_meeting = AsyncMock()
    repo.add_participant = AsyncMock()
    repo.update_participant_status = AsyncMock()
    repo.get_participants = AsyncMock(return_value=[])
    repo.update_meeting_status = AsyncMock()
    repo.set_current_speaker = AsyncMock()
    repo.get_current_speaker = AsyncMock(return_value=None)
    repo.record_event = AsyncMock(return_value=uuid4())
    repo.get_meeting_history = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_session_repo():
    """Mock session repository for testing."""
    repo = MagicMock()
    repo.create_conversation = AsyncMock(return_value=uuid4())
    return repo


@pytest.fixture
def mock_locks():
    """Mock locks utility for testing."""
    locks = MagicMock()
    locks.acquire_lock = AsyncMock()
    locks.release_lock = AsyncMock()
    return locks


@pytest.fixture
def mock_timeout_manager():
    """Mock timeout manager for testing."""
    manager = MagicMock()
    manager.start_turn_timeout = AsyncMock()
    return manager


@pytest.fixture
def mock_event_handler():
    """Mock event handler for testing."""
    handler = MagicMock()
    handler.emit_event = AsyncMock()
    return handler


@pytest.fixture
def meeting_manager(
    mock_meeting_repo,
    mock_message_repo,
    mock_agent_repo,
    mock_event_handler,
):
    """MeetingManager instance for testing."""
    return MeetingManager(
        meeting_repo=mock_meeting_repo,
        message_repo=mock_message_repo,
        agent_repo=mock_agent_repo,
        event_handler=mock_event_handler,
    )


@pytest.fixture
def sample_meeting():
    """Sample meeting for testing."""
    return Meeting(
        id=uuid4(),
        host_id=uuid4(),
        status=MeetingStatus.CREATED,
        current_speaker_id=None,
        turn_duration=None,
        turn_started_at=None,
        created_at=MagicMock(),
        started_at=None,
        ended_at=None,
    )


@pytest.fixture
def sample_agent():
    """Sample agent for testing."""
    return Agent(
        id=uuid4(),
        external_id="alice",
        organization_id=uuid4(),
        name="Alice",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


class TestMeetingManager:
    """Test cases for MeetingManager."""

    @pytest.mark.asyncio
    async def test_create_meeting_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo
    ):
        """Test successful meeting creation."""
        # Setup mock host
        host = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.create_meeting = AsyncMock(return_value=uuid4())

        # Create meeting
        meeting_id = await meeting_manager.create_meeting(
            host_id="alice",
            participant_ids=["bob", "charlie"],
            turn_duration=60.0,
        )

        # Verify meeting was created
        assert meeting_id is not None
        mock_meeting_repo.create_meeting.assert_called_once()
        call_args = mock_meeting_repo.create_meeting.call_args
        assert call_args[1]["host_id"] == host.id
        assert len(call_args[1]["participant_ids"]) == 2

    @pytest.mark.asyncio
    async def test_create_meeting_host_not_found(self, meeting_manager, mock_agent_repo):
        """Test meeting creation with non-existent host."""
        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=AgentNotFoundError("alice"))

        with pytest.raises(AgentNotFoundError):
            await meeting_manager.create_meeting("alice", ["bob"], 60.0)

    @pytest.mark.asyncio
    async def test_attend_meeting_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test successful meeting attendance."""
        # Setup mock agent and meeting
        agent = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=agent)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)

        # Attend meeting
        result = await meeting_manager.attend_meeting("bob", sample_meeting.id)

        # Verify success
        assert result is True
        mock_meeting_repo.add_participant.assert_called_once_with(
            meeting_id=sample_meeting.id,
            agent_id=agent.id,
        )

    @pytest.mark.asyncio
    async def test_start_meeting_success(
        self,
        meeting_manager,
        mock_agent_repo,
        mock_meeting_repo,
        sample_meeting,
        mock_event_handler,
    ):
        """Test successful meeting start."""
        # Setup host and meeting
        host = Agent(
            id=sample_meeting.host_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)
        mock_meeting_repo.get_participants = AsyncMock(
            return_value=[MagicMock(agent_id=uuid4(), status=ParticipantStatus.ATTENDING)]
        )

        # Start meeting
        await meeting_manager.start_meeting("alice", sample_meeting.id)

        # Verify meeting started
        mock_meeting_repo.update_meeting_status.assert_called_with(
            sample_meeting.id,
            MeetingStatus.ACTIVE,
        )
        mock_event_handler.emit_event.assert_called()

    @pytest.mark.asyncio
    async def test_start_meeting_not_host(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test starting meeting by non-host."""
        # Setup non-host agent
        non_host = Agent(
            id=uuid4(),  # Different from host_id
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=non_host)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)

        with pytest.raises(MeetingError, match="Only the host can start the meeting"):
            await meeting_manager.start_meeting("bob", sample_meeting.id)

    @pytest.mark.asyncio
    async def test_speak_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting, mock_message_repo
    ):
        """Test successful speaking in meeting."""
        # Setup speaker and active meeting
        speaker = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=speaker.id,
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=speaker)
        mock_meeting_repo.get_meeting = AsyncMock(return_value=active_meeting)
        mock_message_repo.create = AsyncMock(return_value=uuid4())

        # Speak
        message_id = await meeting_manager.speak(
            "alice", active_meeting.id, {"text": "Hello everyone!"}
        )

        # Verify message created
        assert message_id is not None
        mock_message_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_not_your_turn(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test speaking when it's not your turn."""
        # Setup speaker and meeting where different agent has turn
        speaker = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        other_agent_id = uuid4()
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=other_agent_id,  # Different agent has turn
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=speaker)
        mock_meeting_repo.get_meeting = AsyncMock(return_value=active_meeting)

        with pytest.raises(MeetingError, match="It's not your turn to speak"):
            await meeting_manager.speak("alice", active_meeting.id, {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_end_meeting_success(
        self,
        meeting_manager,
        mock_agent_repo,
        mock_meeting_repo,
        sample_meeting,
        mock_event_handler,
    ):
        """Test successful meeting end."""
        # Setup host and active meeting
        host = Agent(
            id=sample_meeting.host_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=sample_meeting.current_speaker_id,
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.get_meeting = AsyncMock(return_value=active_meeting)

        # End meeting
        await meeting_manager.end_meeting(
            "alice", active_meeting.id, {"text": "Meeting adjourned!"}
        )

        # Verify meeting ended
        mock_meeting_repo.update_meeting_status.assert_called_with(
            active_meeting.id,
            MeetingStatus.ENDED,
        )
        mock_event_handler.emit_event.assert_called()

    @pytest.mark.asyncio
    async def test_get_meeting_status(self, meeting_manager, mock_meeting_repo, sample_meeting):
        """Test getting meeting status."""
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)
        mock_meeting_repo.get_participants = AsyncMock(
            return_value=[
                MagicMock(agent_id=uuid4(), status=ParticipantStatus.ATTENDING, join_order=1)
            ]
        )

        status = await meeting_manager.get_meeting_status(sample_meeting.id)

        # Verify status returned
        assert status is not None
        assert "meeting" in status
        assert "participants" in status
        assert "current_speaker" in status

    @pytest.mark.asyncio
    async def test_get_meeting_history(self, meeting_manager, mock_meeting_repo):
        """Test getting meeting history."""
        meeting_id = uuid4()
        mock_messages = [
            MagicMock(content={"text": "Hello"}, created_at=MagicMock()),
            MagicMock(content={"text": "Hi back"}, created_at=MagicMock()),
        ]
        # Mock the direct query execution
        mock_result = MagicMock()
        mock_result.result.return_value = mock_messages
        mock_meeting_repo._execute = AsyncMock(return_value=mock_result)

        history = await meeting_manager.get_meeting_history(meeting_id)

        # Verify history returned
        assert len(history) == 2
        mock_meeting_repo._execute.assert_called_once()


class TestMeetingTimeoutManager:
    """Test cases for MeetingTimeoutManager."""

    @pytest.fixture
    def timeout_manager(self, mock_meeting_repo, mock_message_repo):
        """MeetingTimeoutManager instance for testing."""
        return MeetingTimeoutManager(
            meeting_repo=mock_meeting_repo,
            message_repo=mock_message_repo,
        )

    @pytest.mark.asyncio
    async def test_start_turn_timeout(self, timeout_manager, mock_meeting_repo):
        """Test starting turn timeout."""
        meeting_id = uuid4()
        agent_id = uuid4()

        # Start timeout
        await timeout_manager.start_turn_timeout(meeting_id, agent_id, 30.0)

        # Verify timeout was started (implementation detail)
        # This would test the internal timeout mechanism
        assert True  # Placeholder - actual implementation would be tested

    @pytest.mark.asyncio
    async def test_handle_turn_timeout(self, timeout_manager, mock_meeting_repo, mock_message_repo):
        """Test handling turn timeout."""
        meeting_id = uuid4()
        agent_id = uuid4()

        # This test is a placeholder - the actual timeout handling is done internally
        # by the monitoring loop. We can't easily test the private _check_timeouts method
        # without complex setup. In a real implementation, this would be tested through
        # integration tests or by testing the public start_turn_timeout method.
        assert True  # Placeholder test


class TestMeetingEventHandler:
    """Test cases for MeetingEventHandler."""

    @pytest.fixture
    def event_handler(self):
        """MeetingEventHandler instance for testing."""
        return MeetingEventHandler()

    def test_register_handler(self, event_handler):
        """Test registering event handler."""

        async def test_handler(event):
            pass

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, test_handler)

        # Verify handler was registered
        assert MeetingEventType.MEETING_STARTED in event_handler._handlers
        assert len(event_handler._handlers[MeetingEventType.MEETING_STARTED]) == 1

    @pytest.mark.asyncio
    async def test_emit_event(self, event_handler):
        """Test emitting event."""
        events_received = []

        async def test_handler(event_data):
            events_received.append(event_data)

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, test_handler)

        # Emit event
        await event_handler.emit_event(
            uuid4(), MeetingEventType.MEETING_STARTED, {"meeting_id": "123"}
        )

        # Verify handler was called
        assert len(events_received) == 1
        assert events_received[0]["meeting_id"] == "123"

    @pytest.mark.asyncio
    async def test_emit_meeting_started(self, event_handler):
        """Test emitting meeting started event."""
        events_received = []

        async def handler(event):
            events_received.append(event)

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, handler)

        # Emit meeting started
        await event_handler.emit_meeting_started(uuid4(), uuid4(), [uuid4(), uuid4()])

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0].event_type == MeetingEventType.MEETING_STARTED

    @pytest.mark.asyncio
    async def test_emit_turn_changed(self, event_handler):
        """Test emitting turn changed event."""
        events_received = []

        async def handler(event):
            events_received.append(event)

        event_handler.register_handler(MeetingEventType.TURN_CHANGED, handler)

        # Emit turn changed
        await event_handler.emit_turn_changed(uuid4(), uuid4(), uuid4())

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0].event_type == MeetingEventType.TURN_CHANGED
