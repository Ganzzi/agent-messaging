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
from .messaging.conversation import Conversation
from .messaging.meeting import MeetingManager
from .models import CreateAgentRequest, CreateOrganizationRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentMessaging(Generic[T]):
    """Main SDK class for Agent Messaging Protocol.

    This is the primary entry point for using the Agent Messaging Protocol SDK.
    It provides methods for managing organizations, agents, and messaging.

    Supports three configuration patterns:

    **Direct Python Configuration (Recommended for PyPI users):**
    ```python
    from agent_messaging import AgentMessaging, Config, DatabaseConfig

    config = Config(
        database=DatabaseConfig(host="prod-db", password="secret"),
        debug=False
    )
    async with AgentMessaging[dict](config=config) as sdk:
        # Use with custom config
        pass
    ```

    **Environment Variables (Recommended for Docker/K8s):**
    ```bash
    export POSTGRES_HOST=postgres
    export POSTGRES_PASSWORD=secure_pass
    python app.py
    ```
    ```python
    async with AgentMessaging[dict]() as sdk:  # Uses env vars
        pass
    ```

    **.env File (Convenient for local development):**
    ```bash
    pip install agent-messaging[dev]  # For .env support
    echo "POSTGRES_HOST=localhost" > .env
    ```
    ```python
    async with AgentMessaging[dict]() as sdk:  # Loads .env automatically
        pass
    ```

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
            config: Optional configuration. If not provided, uses environment variables
                   or .env file (if python-dotenv is available). For direct configuration,
                   pass a Config instance.
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
        self._org_repo = OrganizationRepository(self._db_manager)
        self._agent_repo = AgentRepository(self._db_manager)
        self._message_repo = MessageRepository(self._db_manager)
        self._session_repo = SessionRepository(self._db_manager)
        self._meeting_repo = MeetingRepository(self._db_manager)

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
            ValueError: If external_id or name are invalid
            DatabaseError: If creation fails
        """
        if not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if not name or not isinstance(name, str):
            raise ValueError("name must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")
        if len(name.strip()) == 0:
            raise ValueError("name cannot be empty or whitespace")

        external_id = external_id.strip()
        name = name.strip()

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
            ValueError: If external_id is invalid
            OrganizationNotFoundError: If not found
        """
        if not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")

        external_id = external_id.strip()

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
            ValueError: If parameters are invalid
            OrganizationNotFoundError: If organization not found
            DatabaseError: If creation fails
        """
        if not self._agent_repo or not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if not organization_external_id or not isinstance(organization_external_id, str):
            raise ValueError("organization_external_id must be a non-empty string")
        if not name or not isinstance(name, str):
            raise ValueError("name must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")
        if len(organization_external_id.strip()) == 0:
            raise ValueError("organization_external_id cannot be empty or whitespace")
        if len(name.strip()) == 0:
            raise ValueError("name cannot be empty or whitespace")

        external_id = external_id.strip()
        organization_external_id = organization_external_id.strip()
        name = name.strip()

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
            ValueError: If external_id is invalid
            AgentNotFoundError: If not found
        """
        if not self._agent_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")

        external_id = external_id.strip()

        agent = await self._agent_repo.get_by_external_id(external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {external_id}")
        return agent

    # ========================================================================
    # Handler Registration
    # ========================================================================

    def register_handler(self):
        """Register a message handler for all agents.

        This decorator registers an async function to handle messages for all agents.
        Only one handler can be registered globally.

        Returns:
            Decorator function

        Example:
            @sdk.register_handler()
            async def handle_message(message: T, context: MessageContext) -> Optional[T]:
                print(f"Agent {context.recipient_id} received: {message}")
                return {"response": "OK"}
        """
        logger.info("Registering global message handler")
        return self._handler_registry.register

    def has_handler(self) -> bool:
        """Check if a handler is registered.

        Returns:
            True if handler is registered
        """
        return self._handler_registry.has_handler()

    def register_event_handler(self, event_type: MeetingEventType):
        """Register an event handler for meeting events.

        This decorator registers an async function to handle meeting events with type-safe data.

        Args:
            event_type: Type of meeting event to handle

        Returns:
            Decorator function

        Raises:
            ValueError: If event_type is invalid

        Example:
            from agent_messaging.handlers import MeetingEvent
            from agent_messaging.models import TurnChangedEventData

            @sdk.register_event_handler(MeetingEventType.TURN_CHANGED)
            async def on_turn_changed(event: MeetingEvent):
                data: TurnChangedEventData = event.data
                print(f"Turn changed in meeting {event.meeting_id}")
                print(f"Previous speaker: {data.previous_speaker_id}")
                print(f"Current speaker: {data.current_speaker_id}")
        """
        # Input validation
        if not isinstance(event_type, MeetingEventType):
            raise ValueError("event_type must be a valid MeetingEventType")

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
    def conversation(self) -> "Conversation[T]":
        """Get unified conversation messenger for both sync and async messaging."""
        return Conversation[T](
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
