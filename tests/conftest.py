"""Test fixtures and configuration for Agent Messaging tests."""

import asyncio
import os
from pathlib import Path
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Dict, Any, List
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, DEFAULT
from uuid import uuid4

# Load test environment variables before importing agent_messaging
_test_env_path = Path(__file__).parent.parent / ".test.env"
if _test_env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_test_env_path, override=True)

from agent_messaging.client import AgentMessaging
from agent_messaging.config import Config
from agent_messaging.database.manager import PostgreSQLManager
from agent_messaging.database.repositories.agent import AgentRepository
from agent_messaging.database.repositories.organization import OrganizationRepository
from agent_messaging.database.repositories.message import MessageRepository
from agent_messaging.database.repositories.session import SessionRepository
from agent_messaging.database.repositories.meeting import MeetingRepository
from agent_messaging.handlers import clear_handlers, MessageContext
from agent_messaging.handlers.events import MeetingEventHandler
from agent_messaging.models import (
    Organization,
    Agent,
    Message,
    Session,
    SessionStatus,
    Meeting,
    MeetingStatus,
    MeetingParticipant,
    ParticipantStatus,
    MessageType,
)
from agent_messaging.utils.locks import SessionLock
from agent_messaging.messaging.one_way import OneWayMessenger
from agent_messaging.messaging.conversation import Conversation
from agent_messaging.messaging.meeting import MeetingManager


_DB_INTEGRATION_TEST_FILES = {
    "test_lock_mechanisms.py",
    "test_message_notification.py",
    "test_metadata_filtering.py",
    "test_meeting_wait_for_turn.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-classify tests for deterministic PR unit gating.

    Files that require a live PostgreSQL instance are marked as `integration`
    so the Phase 1 PR command (`-m "not integration and not e2e"`) remains
    reliable in environments without infrastructure services.
    """
    for item in items:
        file_name = Path(str(item.fspath)).name
        if file_name in _DB_INTEGRATION_TEST_FILES:
            item.add_marker(pytest.mark.integration)
        elif "integration" not in item.keywords and "e2e" not in item.keywords:
            item.add_marker(pytest.mark.unit)


# Test Configuration Fixtures
@pytest.fixture
def test_config() -> Config:
    """Test configuration with test database settings."""
    # Load test environment variables (QA credentials)
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5433")
    os.environ.setdefault("POSTGRES_USER", "backend")
    os.environ.setdefault("POSTGRES_PASSWORD", "backend123")
    os.environ.setdefault("POSTGRES_DATABASE", "agent_messaging_test")
    os.environ.setdefault("POSTGRES_DB", "agent_messaging_test")
    os.environ.setdefault("POSTGRES_MAX_POOL_SIZE", "5")
    os.environ.setdefault("MESSAGING__DEFAULT_SYNC_TIMEOUT", "5.0")
    os.environ.setdefault("MESSAGING__DEFAULT_MEETING_TURN_DURATION", "10.0")

    return Config()


# Database Fixtures
@pytest_asyncio.fixture
async def db_manager(test_config: Config) -> AsyncGenerator[PostgreSQLManager, None]:
    """Real database manager for integration tests."""
    manager = PostgreSQLManager(test_config.database)
    await manager.initialize()

    yield manager

    await manager.close()


# Alias for lock tests (backward compatibility)
@pytest_asyncio.fixture
async def db_manager_for_locks(test_config: Config) -> AsyncGenerator[PostgreSQLManager, None]:
    """Database manager for lock tests (alias for db_manager)."""
    manager = PostgreSQLManager(test_config.database)
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
def mock_db_manager() -> MagicMock:
    """Mock database manager for unit tests."""
    manager = MagicMock(spec=PostgreSQLManager)
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.pool = MagicMock()

    # Create a mock connection that supports async context manager protocol
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Make connection() return the async context manager
    manager.connection = MagicMock(return_value=mock_conn)

    return manager


@pytest_asyncio.fixture
async def mock_connection() -> AsyncGenerator[MagicMock, None]:
    """Mock database connection."""
    connection = MagicMock()
    connection.close = MagicMock()
    connection.execute = AsyncMock(return_value=MagicMock())
    connection.fetch = AsyncMock(return_value=MagicMock())
    connection.fetch_row = AsyncMock(return_value=MagicMock())
    connection.fetch_val = AsyncMock(return_value=MagicMock())
    yield connection


# Repository Fixtures
@pytest.fixture
def org_repo(mock_db_manager: MagicMock) -> OrganizationRepository:
    """Organization repository instance."""
    return OrganizationRepository(mock_db_manager.pool)


@pytest.fixture
def agent_repo(mock_db_manager: MagicMock) -> AgentRepository:
    """Agent repository instance."""
    return AgentRepository(mock_db_manager.pool)


@pytest.fixture
def message_repo(mock_db_manager: MagicMock) -> MessageRepository:
    """Message repository instance."""
    return MessageRepository(mock_db_manager.pool)


@pytest.fixture
def session_repo(mock_db_manager: MagicMock) -> SessionRepository:
    """Session repository instance."""
    return SessionRepository(mock_db_manager.pool)


@pytest.fixture
def meeting_repo(mock_db_manager: MagicMock) -> MeetingRepository:
    """Meeting repository instance."""
    return MeetingRepository(mock_db_manager.pool)


@pytest.fixture
def mock_org_repo() -> MagicMock:
    """Mock organization repository."""
    repo = MagicMock(spec=OrganizationRepository)
    repo.create = AsyncMock(return_value=uuid4())
    repo.get_by_external_id = AsyncMock(
        return_value=Organization(
            id=uuid4(),
            external_id="test_org",
            name="Test Organization",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    repo.get_by_id = AsyncMock(
        return_value=Organization(
            id=uuid4(),
            external_id="test_org",
            name="Test Organization",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    return repo


@pytest.fixture
def mock_agent_repo() -> MagicMock:
    """Mock agent repository."""
    repo = MagicMock(spec=AgentRepository)

    _agents_by_external_id: dict[str, Agent] = {}
    _agents_by_id: dict[Any, Agent] = {}

    async def _create(external_id, organization_id, name=None, **kwargs):
        agent = Agent(
            id=uuid4(),
            external_id=external_id,
            organization_id=organization_id,
            name=name or external_id,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        _agents_by_external_id[external_id] = agent
        _agents_by_id[agent.id] = agent
        return agent.id

    async def _get_by_external_id(external_id):
        explicit_return = repo.get_by_external_id._mock_return_value
        if explicit_return is not DEFAULT:
            return explicit_return
        return _agents_by_external_id.get(external_id)

    async def _get_by_id(agent_id):
        explicit_return = repo.get_by_id._mock_return_value
        if explicit_return is not DEFAULT:
            return explicit_return
        return _agents_by_id.get(agent_id)

    repo.create = AsyncMock(side_effect=_create)
    repo.get_by_external_id = AsyncMock(side_effect=_get_by_external_id)
    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    repo._agents_by_external_id = _agents_by_external_id
    repo._agents_by_id = _agents_by_id
    return repo


@pytest.fixture
def mock_message_repo(mock_db_manager: MagicMock, mock_agent_repo: MagicMock) -> MagicMock:
    """Mock message repository."""
    repo = MagicMock(spec=MessageRepository)
    repo.db_manager = mock_db_manager

    _messages: list[Message] = []

    async def _create(**kwargs):
        sender_id = kwargs.get("sender_id")
        content = dict(kwargs.get("content", {"text": "test message"}))
        if "sender_external_id" not in content and sender_id:
            sender = mock_agent_repo._agents_by_id.get(sender_id)
            if sender:
                content["sender_external_id"] = sender.external_id

        message = Message(
            id=uuid4(),
            sender_id=sender_id,
            recipient_id=kwargs.get("recipient_id"),
            session_id=kwargs.get("session_id"),
            meeting_id=kwargs.get("meeting_id"),
            content=content,
            message_type=kwargs.get("message_type", MessageType.USER_DEFINED),
            created_at=datetime.utcnow(),
        )
        _messages.append(message)
        return message.id

    async def _get_messages_for_meeting(meeting_id, date_from=None, limit=1000):
        msgs = [m for m in _messages if m.meeting_id == meeting_id]
        if date_from is not None:
            msgs = [m for m in msgs if m.created_at and m.created_at > date_from]
        msgs.sort(key=lambda m: m.created_at)
        return msgs[:limit]

    repo.create = AsyncMock(side_effect=_create)
    repo.get_messages_for_meeting = AsyncMock(side_effect=_get_messages_for_meeting)
    repo.get_by_id = AsyncMock(
        return_value=Message(
            id=uuid4(),
            sender_id=uuid4(),
            recipient_id=uuid4(),
            content={"text": "test message"},
            message_type=MessageType.USER_DEFINED,
            created_at=MagicMock(),
        )
    )
    repo.get_unread_messages = AsyncMock(return_value=[])
    repo.mark_as_read = AsyncMock()
    return repo


@pytest.fixture
def mock_session_repo() -> MagicMock:
    """Mock session repository."""
    repo = MagicMock(spec=SessionRepository)
    repo.create_conversation = AsyncMock(return_value=uuid4())
    repo.get_by_id = AsyncMock(
        return_value=Session(
            id=uuid4(),
            agent_a_id=uuid4(),
            agent_b_id=uuid4(),
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    return repo


@pytest.fixture
def mock_meeting_repo() -> MagicMock:
    """Mock meeting repository."""
    repo = MagicMock(spec=MeetingRepository)

    # Store meetings to simulate real behavior
    _meetings = {}
    _host_ids = {}  # meeting_id -> host_id mapping
    _participants = {}  # meeting_id -> list of participant dicts

    async def _create(host_id, *args, **kwargs):
        meeting_id = uuid4()
        _host_ids[meeting_id] = host_id
        _participants[meeting_id] = [
            {
                "id": uuid4(),
                "agent_id": host_id,
                "join_order": -1,
                "status": ParticipantStatus.ATTENDING,
            }
        ]
        _meetings[meeting_id] = Meeting(
            id=meeting_id,
            host_id=host_id,
            status=MeetingStatus.CREATED,
            current_speaker_id=None,
            turn_duration=kwargs.get('turn_duration'),
            created_at=MagicMock(),
            started_at=None,
            ended_at=None,
        )
        return meeting_id

    async def _get_by_id(meeting_id):
        if meeting_id in _meetings:
            return _meetings[meeting_id]
        # Fallback for tests that don't use create
        return Meeting(
            id=meeting_id,
            host_id=_host_ids.get(meeting_id, uuid4()),
            status=MeetingStatus.CREATED,
            current_speaker_id=None,
            turn_duration=None,
            created_at=MagicMock(),
            started_at=None,
            ended_at=None,
        )

    async def _add_participant(meeting_id, agent_id, join_order=None, **kwargs):
        if meeting_id not in _participants:
            _participants[meeting_id] = []
        resolved_join_order = join_order if join_order is not None else len(_participants[meeting_id])
        _participants[meeting_id].append(
            {
                "id": uuid4(),
                "agent_id": agent_id,
                "join_order": resolved_join_order,
                "status": ParticipantStatus.INVITED,
            }
        )

    async def _get_participants(meeting_id):
        if meeting_id in _participants:
            return [
                MeetingParticipant(
                    id=participant["id"],
                    meeting_id=meeting_id,
                    agent_id=participant["agent_id"],
                    join_order=participant["join_order"],
                    status=participant["status"],
                )
                for participant in sorted(_participants[meeting_id], key=lambda p: p["join_order"])
            ]
        return []

    async def _start_meeting(meeting_id):
        if meeting_id in _meetings:
            _meetings[meeting_id].status = MeetingStatus.ACTIVE

    async def _set_current_speaker(meeting_id, agent_id, turn_started=True):
        if meeting_id in _meetings:
            _meetings[meeting_id].current_speaker_id = agent_id

    async def _get_participant(meeting_id, agent_id):
        for participant in _participants.get(meeting_id, []):
            if participant["agent_id"] == agent_id:
                return MeetingParticipant(
                    id=participant["id"],
                    meeting_id=meeting_id,
                    agent_id=participant["agent_id"],
                    join_order=participant["join_order"],
                    status=participant["status"],
                )
        return None

    async def _update_participant_status(participant_id=None, meeting_id=None, agent_id=None, status=None):
        for current_meeting_id, entries in _participants.items():
            for participant in entries:
                if participant_id is not None and participant["id"] == participant_id:
                    participant["status"] = status
                    return
                if (
                    meeting_id is not None
                    and agent_id is not None
                    and current_meeting_id == meeting_id
                    and participant["agent_id"] == agent_id
                ):
                    participant["status"] = status
                    return

    async def _end_meeting(meeting_id):
        if meeting_id in _meetings:
            _meetings[meeting_id].status = MeetingStatus.ENDED

    async def _update(meeting_id, **kwargs):
        if meeting_id in _meetings:
            for key, value in kwargs.items():
                if hasattr(_meetings[meeting_id], key):
                    setattr(_meetings[meeting_id], key, value)

    repo.create = AsyncMock(side_effect=_create)
    repo.create_meeting = AsyncMock(side_effect=_create)
    repo.add_participant = AsyncMock(side_effect=_add_participant)
    repo.get_participants = AsyncMock(side_effect=_get_participants)
    repo.get_participant = AsyncMock(side_effect=_get_participant)
    repo.update_participant_status = AsyncMock(side_effect=_update_participant_status)
    repo.start_meeting = AsyncMock(side_effect=_start_meeting)
    repo.set_current_speaker = AsyncMock(side_effect=_set_current_speaker)
    repo.end_meeting = AsyncMock(side_effect=_end_meeting)
    repo.get_by_host_id = AsyncMock(return_value=[])
    repo.update = AsyncMock(side_effect=_update)
    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    return repo


# Handler and Event Fixtures
@pytest.fixture(autouse=True)
def clean_handlers():
    """Clean global handlers before and after each test."""
    clear_handlers()
    yield
    clear_handlers()


@pytest.fixture
def event_handler() -> MeetingEventHandler:
    """Event handler instance."""
    return MeetingEventHandler()


@pytest.fixture
def one_way_messenger(
    mock_message_repo: MagicMock, mock_agent_repo: MagicMock, mock_org_repo: MagicMock
):
    """OneWayMessenger instance with mocked dependencies."""
    from agent_messaging.messaging.one_way import OneWayMessenger

    return OneWayMessenger(
        message_repo=mock_message_repo,
        agent_repo=mock_agent_repo,
        org_repo=mock_org_repo,
    )


# SDK Fixtures
@pytest_asyncio.fixture
async def sdk(
    test_config: Config,
    mock_db_manager: MagicMock,
    mock_org_repo: MagicMock,
    mock_agent_repo: MagicMock,
    mock_message_repo: MagicMock,
    mock_session_repo: MagicMock,
    mock_meeting_repo: MagicMock,
) -> AsyncGenerator[AgentMessaging, None]:
    """SDK instance for testing."""
    # Create a mock event handler with async methods
    mock_event_handler = MagicMock()
    mock_event_handler.emit_participant_joined = AsyncMock()
    mock_event_handler.emit_participant_left = AsyncMock()
    mock_event_handler.emit_meeting_started = AsyncMock()
    mock_event_handler.emit_meeting_ended = AsyncMock()
    mock_event_handler.emit_turn_changed = AsyncMock()
    mock_event_handler.emit_message_posted = AsyncMock()

    # Mock the PostgreSQLManager import
    with (
        patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
        patch("agent_messaging.client.OrganizationRepository", return_value=mock_org_repo),
        patch("agent_messaging.client.AgentRepository", return_value=mock_agent_repo),
        patch("agent_messaging.client.MessageRepository", return_value=mock_message_repo),
        patch("agent_messaging.client.SessionRepository", return_value=mock_session_repo),
        patch("agent_messaging.client.MeetingRepository", return_value=mock_meeting_repo),
        patch("agent_messaging.client.MeetingEventHandler", return_value=mock_event_handler),
    ):

        async with AgentMessaging[Dict[str, Any], Dict[str, Any], Dict[str, Any]](
            test_config
        ) as sdk_instance:
            yield sdk_instance


@pytest.fixture
def mock_sdk(mock_db_manager: MagicMock) -> MagicMock:
    """Mock SDK instance."""
    sdk = MagicMock(spec=AgentMessaging)
    sdk.__aenter__ = AsyncMock(return_value=sdk)
    sdk.__aexit__ = AsyncMock()
    return sdk


# Test Data Fixtures
@pytest.fixture
def sample_organization() -> Organization:
    """Sample organization for testing."""
    return Organization(
        id=uuid4(),
        external_id="test_org_001",
        name="Test Organization",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


@pytest.fixture
def sample_agent(sample_organization: Organization) -> Agent:
    """Sample agent for testing."""
    return Agent(
        id=uuid4(),
        external_id="test_agent_001",
        organization_id=sample_organization.id,
        name="Test Agent",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


@pytest.fixture
def sample_message(sample_agent: Agent) -> Message:
    """Sample message for testing."""
    return Message(
        id=uuid4(),
        sender_id=sample_agent.id,
        recipient_id=uuid4(),
        content={"text": "Hello, world!"},
        message_type=MessageType.USER_DEFINED,
        created_at=MagicMock(),
    )


@pytest.fixture
def sample_session(sample_agent: Agent) -> Session:
    """Sample session for testing."""
    return Session(
        id=uuid4(),
        agent_a_id=sample_agent.id,
        agent_b_id=uuid4(),
        status=SessionStatus.ACTIVE,
        locked_agent_id=None,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


@pytest.fixture
def sample_meeting(sample_agent: Agent) -> Meeting:
    """Sample meeting for testing."""
    return Meeting(
        id=uuid4(),
        host_id=sample_agent.id,
        status=MeetingStatus.CREATED,
        current_speaker_id=None,
        turn_duration=None,
        created_at=MagicMock(),
        started_at=None,
        ended_at=None,
    )


@pytest.fixture
def sample_message_context(sample_agent: Agent, sample_message: Message) -> MessageContext:
    """Sample message context for testing."""
    return MessageContext(
        sender_id=sample_agent.external_id,
        recipient_id="recipient_agent",
        message_id=sample_message.id,
        timestamp=MagicMock(),
        session_id=None,
    )


# Utility Fixtures
@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def cleanup_tasks() -> AsyncGenerator[List[asyncio.Task], None]:
    """Fixture to track and cleanup background tasks."""
    tasks = []
    yield tasks

    # Cancel and cleanup any remaining tasks
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


# Performance Test Fixtures
@pytest.fixture
def performance_config() -> Config:
    """Configuration optimized for performance testing."""
    config = Config()
    # Override with performance settings
    config.database.max_pool_size = 20
    config.messaging.default_sync_timeout = 30.0
    return config


# E2E Test Fixtures
@pytest_asyncio.fixture
async def e2e_sdk(
    test_config: Config, db_manager: PostgreSQLManager
) -> AsyncGenerator[AgentMessaging, None]:
    """Real SDK instance for end-to-end tests."""
    async with AgentMessaging[Dict[str, Any], Dict[str, Any], Dict[str, Any]](test_config) as sdk:
        yield sdk


# Integration Test Fixtures for Phase 2 Query Tests
@pytest.fixture
def db_pool(db_manager: PostgreSQLManager):
    """Database manager for backward compatibility with Phase 2 tests.

    Note: Despite the name 'db_pool', this returns the full db_manager
    because repositories expect PostgreSQLManager, not just the pool.
    """
    return db_manager


@pytest_asyncio.fixture
async def org_a(db_manager: PostgreSQLManager) -> Organization:
    """Test organization A for integration tests."""
    org_repo = OrganizationRepository(db_manager)
    org_id = await org_repo.create(external_id=f"org_a_{uuid4().hex[:8]}", name="Organization A")
    return await org_repo.get_by_id(org_id)


@pytest_asyncio.fixture
async def agent_alice(db_manager: PostgreSQLManager, org_a: Organization) -> Agent:
    """Test agent Alice for integration tests."""
    agent_repo = AgentRepository(db_manager)
    agent_id = await agent_repo.create(
        external_id=f"alice_{uuid4().hex[:8]}", organization_id=org_a.id, name="Alice"
    )
    return await agent_repo.get_by_id(agent_id)


@pytest_asyncio.fixture
async def agent_bob(db_manager: PostgreSQLManager, org_a: Organization) -> Agent:
    """Test agent Bob for integration tests."""
    agent_repo = AgentRepository(db_manager)
    agent_id = await agent_repo.create(
        external_id=f"bob_{uuid4().hex[:8]}", organization_id=org_a.id, name="Bob"
    )
    return await agent_repo.get_by_id(agent_id)


@pytest_asyncio.fixture
async def agent_charlie(db_manager: PostgreSQLManager, org_a: Organization) -> Agent:
    """Test agent Charlie for integration tests."""
    agent_repo = AgentRepository(db_manager)
    agent_id = await agent_repo.create(
        external_id=f"charlie_{uuid4().hex[:8]}", organization_id=org_a.id, name="Charlie"
    )
    return await agent_repo.get_by_id(agent_id)


# Integration Test Fixtures for Phase 4 (Metadata & Advanced Features)
@pytest_asyncio.fixture
async def message_repo_integration(db_manager: PostgreSQLManager) -> MessageRepository:
    """Real message repository for Phase 4 integration tests."""
    return MessageRepository(db_manager)


@pytest_asyncio.fixture
async def session_repo_integration(db_manager: PostgreSQLManager) -> SessionRepository:
    """Real session repository for Phase 4 integration tests."""
    return SessionRepository(db_manager)


@pytest_asyncio.fixture
async def meeting_repo_integration(db_manager: PostgreSQLManager) -> MeetingRepository:
    """Real meeting repository for Phase 4 integration tests."""
    return MeetingRepository(db_manager)


# Test Helper Functions
@pytest.fixture
def create_test_org_data() -> Dict[str, Any]:
    """Factory for test organization data."""

    def _create(external_id: str = None, name: str = None) -> Dict[str, Any]:
        return {
            "external_id": external_id or f"org_{uuid4().hex[:8]}",
            "name": name or f"Test Organization {uuid4().hex[:8]}",
        }

    return _create


@pytest.fixture
def create_test_agent_data() -> Dict[str, Any]:
    """Factory for test agent data."""

    def _create(org_id: str = None, external_id: str = None, name: str = None) -> Dict[str, Any]:
        return {
            "organization_external_id": org_id or f"org_{uuid4().hex[:8]}",
            "external_id": external_id or f"agent_{uuid4().hex[:8]}",
            "name": name or f"Test Agent {uuid4().hex[:8]}",
        }

    return _create


@pytest.fixture
def create_test_message_data() -> Dict[str, Any]:
    """Factory for test message data."""

    def _create(content: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "content": content or {"text": f"Test message {uuid4().hex[:8]}"},
            "message_type": MessageType.USER_DEFINED,
        }

    return _create
