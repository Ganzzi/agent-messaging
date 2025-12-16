"""Integration tests for AgentMessaging SDK client."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agent_messaging.client import AgentMessaging
from agent_messaging.config import Config
from agent_messaging.models import (
    Agent,
    Organization,
    MeetingEventType,
    MeetingEventPayload,
)
from agent_messaging.exceptions import (
    AgentNotFoundError,
    OrganizationNotFoundError,
)
from agent_messaging.handlers import (
    clear_handlers,
    has_handler,
    register_one_way_handler,
    HandlerContext,
)


@pytest.fixture(autouse=True)
def clean_handlers_fixture():
    """Clean handlers before and after each test."""
    clear_handlers()
    yield
    clear_handlers()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return Config()


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.pool = MagicMock()
    return manager


@pytest.fixture
def mock_org_repo():
    """Mock organization repository."""
    repo = MagicMock()
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
    return repo


@pytest.fixture
def mock_agent_repo():
    """Mock agent repository."""
    repo = MagicMock()
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
    return repo


@pytest.fixture
def mock_repos(mock_org_repo, mock_agent_repo):
    """Mock all repositories."""
    return {
        "org_repo": mock_org_repo,
        "agent_repo": mock_agent_repo,
        "message_repo": MagicMock(),
        "session_repo": MagicMock(),
        "meeting_repo": MagicMock(),
    }


@pytest.fixture
def mock_registry():
    """Mock handler registry - not used but kept for compatibility."""
    registry = MagicMock()
    registry.register = MagicMock(side_effect=lambda func: func)  # Return the function itself
    registry.has_handler = MagicMock(return_value=True)
    registry.shutdown = AsyncMock()
    return registry


@pytest.fixture
def mock_event_handler():
    """Mock event handler."""
    handler = MagicMock()
    handler.register_handler = MagicMock()
    return handler


class TestAgentMessagingSDK:
    """Integration tests for AgentMessaging SDK."""

    @pytest.mark.asyncio
    async def test_sdk_initialization_and_context_manager(
        self, mock_config, mock_db_manager, mock_repos, mock_event_handler
    ):
        """Test SDK initialization and context manager behavior."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
            patch("agent_messaging.client.MeetingEventHandler", return_value=mock_event_handler),
        ):

            sdk = AgentMessaging[dict, dict, dict](mock_config)

            # Test __aenter__
            result = await sdk.__aenter__()
            assert result is sdk
            mock_db_manager.initialize.assert_called_once()

            # Test repositories are initialized
            assert sdk._org_repo is mock_repos["org_repo"]
            assert sdk._agent_repo is mock_repos["agent_repo"]

            # Test __aexit__
            await sdk.__aexit__(None, None, None)
            mock_db_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_organization(self, mock_config, mock_db_manager, mock_repos):
        """Test organization registration."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                org_id = await sdk.register_organization("test_org", "Test Organization")
                assert isinstance(org_id, str)
                mock_repos["org_repo"].create.assert_called_once_with(
                    "test_org", "Test Organization"
                )

    @pytest.mark.asyncio
    async def test_get_organization(self, mock_config, mock_db_manager, mock_repos):
        """Test organization retrieval."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                org = await sdk.get_organization("test_org")
                assert org.external_id == "test_org"
                assert org.name == "Test Organization"
                mock_repos["org_repo"].get_by_external_id.assert_called_once_with("test_org")

    @pytest.mark.asyncio
    async def test_get_organization_not_found(self, mock_config, mock_db_manager, mock_repos):
        """Test organization retrieval when not found."""
        mock_repos["org_repo"].get_by_external_id = AsyncMock(return_value=None)

        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                with pytest.raises(OrganizationNotFoundError):
                    await sdk.get_organization("nonexistent_org")

    @pytest.mark.asyncio
    async def test_register_agent(self, mock_config, mock_db_manager, mock_repos):
        """Test agent registration."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                agent_id = await sdk.register_agent("test_agent", "test_org", "Test Agent")
                assert isinstance(agent_id, str)
                mock_repos["org_repo"].get_by_external_id.assert_called_once_with("test_org")
                mock_repos["agent_repo"].create.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_agent_org_not_found(self, mock_config, mock_db_manager, mock_repos):
        """Test agent registration with nonexistent organization."""
        mock_repos["org_repo"].get_by_external_id = AsyncMock(return_value=None)

        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                with pytest.raises(OrganizationNotFoundError):
                    await sdk.register_agent("test_agent", "nonexistent_org", "Test Agent")

    @pytest.mark.asyncio
    async def test_get_agent(self, mock_config, mock_db_manager, mock_repos):
        """Test agent retrieval."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                agent = await sdk.get_agent("test_agent")
                assert agent.external_id == "test_agent"
                assert agent.name == "Test Agent"
                mock_repos["agent_repo"].get_by_external_id.assert_called_once_with("test_agent")

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_config, mock_db_manager, mock_repos):
        """Test agent retrieval when not found."""
        mock_repos["agent_repo"].get_by_external_id = AsyncMock(return_value=None)

        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                with pytest.raises(AgentNotFoundError):
                    await sdk.get_agent("nonexistent_agent")

    @pytest.mark.asyncio
    async def test_register_handler(self, mock_config, mock_db_manager, mock_repos):
        """Test message handler registration with global decorators."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):
            # Register handler using global decorator before using SDK
            @register_one_way_handler
            async def test_handler(message, context):
                return {"response": "ok"}

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                # Verify handler was registered globally
                assert has_handler(HandlerContext.ONE_WAY) is True

    @pytest.mark.asyncio
    async def test_register_event_handler(
        self, mock_config, mock_db_manager, mock_repos, mock_event_handler
    ):
        """Test event handler registration."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
            patch("agent_messaging.client.MeetingEventHandler", return_value=mock_event_handler),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                # Test event handler registration
                @sdk.register_event_handler(MeetingEventType.MEETING_STARTED)
                async def on_meeting_started(event: MeetingEventPayload):
                    print(f"Meeting started: {event.meeting_id}")

                # Verify event handler was registered
                mock_event_handler.register_handler.assert_called_once_with(
                    MeetingEventType.MEETING_STARTED, on_meeting_started
                )

    @pytest.mark.asyncio
    async def test_has_handler(self, mock_config, mock_db_manager, mock_repos):
        """Test global handler existence check."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):
            # Register a handler using the global function
            @register_one_way_handler
            async def test_handler(message, context):
                pass

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                # Check using global has_handler function
                assert has_handler(HandlerContext.ONE_WAY) is True
                assert has_handler(HandlerContext.CONVERSATION) is False

    @pytest.mark.asyncio
    async def test_messaging_properties(self, mock_config, mock_db_manager, mock_repos):
        """Test messaging property access."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                # Test one_way property
                one_way = sdk.one_way
                assert one_way is not None

                # Test conversation property (unified sync/async)
                conv = sdk.conversation
                assert conv is not None

                # Test meeting property
                meeting = sdk.meeting
                assert meeting is not None

    @pytest.mark.asyncio
    async def test_sdk_not_initialized_error(self, mock_config):
        """Test error when SDK methods called before initialization."""
        sdk = AgentMessaging[dict, dict, dict](mock_config)

        # Test organization methods
        with pytest.raises(RuntimeError, match="SDK not initialized"):
            await sdk.register_organization("test", "Test")

        with pytest.raises(RuntimeError, match="SDK not initialized"):
            await sdk.get_organization("test")

        # Test agent methods
        with pytest.raises(RuntimeError, match="SDK not initialized"):
            await sdk.register_agent("agent", "org", "Agent")

        with pytest.raises(RuntimeError, match="SDK not initialized"):
            await sdk.get_agent("agent")

    @pytest.mark.asyncio
    async def test_repository_properties(self, mock_config, mock_db_manager, mock_repos):
        """Test repository property access."""
        with (
            patch("agent_messaging.client.PostgreSQLManager", return_value=mock_db_manager),
            patch(
                "agent_messaging.client.OrganizationRepository", return_value=mock_repos["org_repo"]
            ),
            patch("agent_messaging.client.AgentRepository", return_value=mock_repos["agent_repo"]),
            patch(
                "agent_messaging.client.MessageRepository", return_value=mock_repos["message_repo"]
            ),
            patch(
                "agent_messaging.client.SessionRepository", return_value=mock_repos["session_repo"]
            ),
            patch(
                "agent_messaging.client.MeetingRepository", return_value=mock_repos["meeting_repo"]
            ),
        ):

            async with AgentMessaging[dict, dict, dict](mock_config) as sdk:
                # Test repository access
                assert sdk.org_repo is mock_repos["org_repo"]
                assert sdk.agent_repo is mock_repos["agent_repo"]
                assert sdk.message_repo is mock_repos["message_repo"]
                assert sdk.session_repo is mock_repos["session_repo"]
                assert sdk.meeting_repo is mock_repos["meeting_repo"]
