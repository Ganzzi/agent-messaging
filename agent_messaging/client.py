"""Main Agent Messaging SDK client."""

import logging
from typing import Generic, Optional, TypeVar

from .config import Config
from .database.manager import PostgreSQLManager
from .database.repositories.agent import AgentRepository
from .database.repositories.organization import OrganizationRepository
from .database.repositories.session import SessionRepository
from .database.repositories.message import MessageRepository
from .database.repositories.meeting import MeetingRepository
from .exceptions import (
    AgentNotFoundError,
    OrganizationNotFoundError,
)
from .handlers.registry import HandlerRegistry
from .handlers.events import MeetingEventHandler, MeetingEventType
from .messaging.one_way import OneWayMessenger
from .messaging.sync_conversation import SyncConversation
from .messaging.async_conversation import AsyncConversation
from .messaging.meeting import MeetingManager
from .models import CreateAgentRequest, CreateOrganizationRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentMessaging(Generic[T]):
    """Main SDK class for Agent Messaging Protocol.

    This is the primary entry point for using the Agent Messaging Protocol SDK.
    It provides methods for managing organizations, agents, and messaging.

    Example:
        async with AgentMessaging[dict]() as sdk:
            await sdk.register_organization("org_001", "My Organization")
            await sdk.register_agent("alice", "org_001", "Alice Agent")

            @sdk.register_handler("alice")
            async def handle_alice(message: dict, context: MessageContext):
                return {"response": "Hello"}

            await sdk.one_way.send("alice", "bob", {"text": "Hi"})
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize the SDK.

        Args:
            config: Optional configuration. If not provided, loads from .env
        """
        self.config = config or Config()
        self._db_manager = PostgreSQLManager(self.config.database)
        self._handler_registry = HandlerRegistry(self.config.messaging.handler_timeout)
        self._event_handler = MeetingEventHandler()

        # Repositories (initialized in __aenter__)
        self._org_repo: Optional[OrganizationRepository] = None
        self._agent_repo: Optional[AgentRepository] = None
        self._message_repo: Optional[MessageRepository] = None
        self._session_repo: Optional[SessionRepository] = None
        self._meeting_repo: Optional[MeetingRepository] = None

        logger.info("AgentMessaging SDK initialized")

    async def __aenter__(self) -> "AgentMessaging[T]":
        """Async context manager entry.

        Initializes database connection pool and repositories.

        Returns:
            Self instance
        """
        logger.info("Entering AgentMessaging context")
        await self._db_manager.initialize()

        # Initialize repositories
        self._org_repo = OrganizationRepository(self._db_manager.pool)
        self._agent_repo = AgentRepository(self._db_manager.pool)
        self._message_repo = MessageRepository(self._db_manager.pool)
        self._session_repo = SessionRepository(self._db_manager.pool)
        self._meeting_repo = MeetingRepository(self._db_manager.pool)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit.

        Closes database connection pool and cleans up resources.
        """
        logger.info("Exiting AgentMessaging context")
        await self._handler_registry.shutdown()
        await self._db_manager.close()

    # ========================================================================
    # Organization Management
    # ========================================================================

    async def register_organization(self, external_id: str, name: str) -> str:
        """Register a new organization.

        Args:
            external_id: External identifier for the organization
            name: Human-readable name

        Returns:
            UUID of the created organization

        Raises:
            DatabaseError: If creation fails
        """
        if not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        logger.info(f"Registering organization: {external_id}")
        org_id = await self._org_repo.create(external_id, name)
        logger.info(f"Organization registered: {external_id} (ID: {org_id})")
        return str(org_id)

    async def get_organization(self, external_id: str):
        """Get organization by external ID.

        Args:
            external_id: External identifier

        Returns:
            Organization model

        Raises:
            OrganizationNotFoundError: If not found
        """
        if not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        org = await self._org_repo.get_by_external_id(external_id)
        if not org:
            raise OrganizationNotFoundError(f"Organization not found: {external_id}")
        return org

    # ========================================================================
    # Agent Management
    # ========================================================================

    async def register_agent(
        self, external_id: str, organization_external_id: str, name: str
    ) -> str:
        """Register a new agent.

        Args:
            external_id: External identifier for the agent
            organization_external_id: External ID of the organization
            name: Human-readable name

        Returns:
            UUID of the created agent

        Raises:
            OrganizationNotFoundError: If organization not found
            DatabaseError: If creation fails
        """
        if not self._agent_repo or not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        logger.info(f"Registering agent: {external_id}")

        # Verify organization exists
        org = await self._org_repo.get_by_external_id(organization_external_id)
        if not org:
            raise OrganizationNotFoundError(f"Organization not found: {organization_external_id}")

        # Create agent
        agent_id = await self._agent_repo.create(external_id, org.id, name)
        logger.info(f"Agent registered: {external_id} (ID: {agent_id})")
        return str(agent_id)

    async def get_agent(self, external_id: str):
        """Get agent by external ID.

        Args:
            external_id: External identifier

        Returns:
            Agent model

        Raises:
            AgentNotFoundError: If not found
        """
        if not self._agent_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        agent = await self._agent_repo.get_by_external_id(external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {external_id}")
        return agent

    # ========================================================================
    # Handler Registration
    # ========================================================================

    def register_handler(self, agent_external_id: str):
        """Register a message handler for an agent.

        This decorator registers an async function to handle messages sent to the agent.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            Decorator function

        Example:
            @sdk.register_handler("alice")
            async def handle_alice(message: T, context: MessageContext) -> Optional[T]:
                print(f"Received: {message}")
                return {"response": "OK"}
        """
        logger.info(f"Registering handler for agent: {agent_external_id}")
        return self._handler_registry.register(agent_external_id)

    def has_handler(self, agent_external_id: str) -> bool:
        """Check if a handler is registered for an agent.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            True if handler is registered
        """
        return self._handler_registry.has_handler(agent_external_id)

    def register_event_handler(self, event_type: MeetingEventType):
        """Register an event handler for meeting events.

        This decorator registers an async function to handle meeting events.

        Args:
            event_type: Type of meeting event to handle

        Returns:
            Decorator function

        Example:
            @sdk.register_event_handler(MeetingEvent.TURN_CHANGED)
            async def on_turn_changed(event: MeetingEventPayload):
                print(f"Turn changed in meeting {event.meeting_id}")
        """

        def decorator(handler):
            self._event_handler.register_handler(event_type, handler)
            logger.info(f"Registered event handler for: {event_type}")
            return handler

        return decorator

    # ========================================================================
    # Properties for Messaging Classes
    # ========================================================================

    @property
    def org_repo(self) -> OrganizationRepository:
        """Get organization repository."""
        if not self._org_repo:
            raise RuntimeError("SDK not initialized")
        return self._org_repo

    @property
    def agent_repo(self) -> AgentRepository:
        """Get agent repository."""
        if not self._agent_repo:
            raise RuntimeError("SDK not initialized")
        return self._agent_repo

    @property
    def message_repo(self) -> MessageRepository:
        """Get message repository."""
        if not self._message_repo:
            raise RuntimeError("SDK not initialized")
        return self._message_repo

    @property
    def session_repo(self) -> SessionRepository:
        """Get session repository."""
        if not self._session_repo:
            raise RuntimeError("SDK not initialized")
        return self._session_repo

    @property
    def meeting_repo(self) -> MeetingRepository:
        """Get meeting repository."""
        if not self._meeting_repo:
            raise RuntimeError("SDK not initialized")
        return self._meeting_repo

    @property
    def handler_registry(self) -> HandlerRegistry:
        """Get handler registry."""
        return self._handler_registry

    # ========================================================================
    # Messaging Properties
    # ========================================================================

    @property
    def one_way(self) -> OneWayMessenger[T]:
        """Get one-way messenger for fire-and-forget messaging."""
        return OneWayMessenger[T](
            handler_registry=self._handler_registry,
            message_repo=self._message_repo,
            agent_repo=self._agent_repo,
        )

    @property
    def sync_conversation(self) -> "SyncConversation[T]":
        """Get synchronous conversation messenger for request-response messaging."""
        from .messaging.sync_conversation import SyncConversation

        return SyncConversation[T](
            handler_registry=self._handler_registry,
            message_repo=self._message_repo,
            session_repo=self._session_repo,
            agent_repo=self._agent_repo,
        )

    @property
    def async_conversation(self) -> "AsyncConversation[T]":
        """Get asynchronous conversation messenger for queued messaging."""
        from .messaging.async_conversation import AsyncConversation

        return AsyncConversation[T](
            handler_registry=self._handler_registry,
            message_repo=self._message_repo,
            session_repo=self._session_repo,
            agent_repo=self._agent_repo,
        )

    @property
    def meeting(self) -> "MeetingManager[T]":
        """Get meeting manager for multi-agent meetings."""
        from .messaging.meeting import MeetingManager

        return MeetingManager[T](
            meeting_repo=self._meeting_repo,
            message_repo=self._message_repo,
            agent_repo=self._agent_repo,
            event_handler=self._event_handler,
        )
