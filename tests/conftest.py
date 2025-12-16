"""Test fixtures and configuration for Agent Messaging tests."""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

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


# Test Configuration Fixtures
@pytest.fixture
def test_config() -> Config:
    """Test configuration with test database settings."""
    # Load test environment variables
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5433")
    os.environ.setdefault("POSTGRES_USER", "postgres")
    os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
    os.environ.setdefault("POSTGRES_DATABASE", "agent_messaging_test")
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


@pytest.fixture
def mock_db_manager() -> MagicMock:
    """Mock database manager for unit tests."""
    manager = MagicMock(spec=PostgreSQLManager)
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.pool = MagicMock()
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
    repo.create = AsyncMock(return_value=uuid4())
    repo.get_by_external_id = AsyncMock(
        return_value=Agent(
            id=uuid4(),
            external_id="test_agent",
            organization_id=uuid4(),
            name="Test Agent",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    repo.get_by_id = AsyncMock(
        return_value=Agent(
            id=uuid4(),
            external_id="test_agent",
            organization_id=uuid4(),
            name="Test Agent",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    )
    return repo


@pytest.fixture
def mock_message_repo() -> MagicMock:
    """Mock message repository."""
    repo = MagicMock(spec=MessageRepository)
    repo.create = AsyncMock(return_value=uuid4())
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
    repo.create_meeting = AsyncMock(return_value=uuid4())
    repo.get_by_id = AsyncMock(
        return_value=Meeting(
            id=uuid4(),
            host_id=uuid4(),
            status=MeetingStatus.CREATED,
            current_speaker_id=None,
            turn_duration=None,
            created_at=MagicMock(),
            started_at=None,
            ended_at=None,
        )
    )
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
    test_config: Config, mock_db_manager: MagicMock
) -> AsyncGenerator[AgentMessaging, None]:
    """SDK instance for testing."""
    # Mock the PostgreSQLManager import
    with (
        pytest.mock.patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
        pytest.mock.patch("agent_messaging.client.OrganizationRepository"),
        pytest.mock.patch("agent_messaging.client.AgentRepository"),
        pytest.mock.patch("agent_messaging.client.MessageRepository"),
        pytest.mock.patch("agent_messaging.client.SessionRepository"),
        pytest.mock.patch("agent_messaging.client.MeetingRepository"),
        pytest.mock.patch("agent_messaging.client.MeetingEventHandler"),
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
