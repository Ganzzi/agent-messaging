"""Main Agent Messaging SDK client.

Provides the AgentMessaging class with 3 generic type parameters:
- T_OneWay: Type for fire-and-forget messages
- T_Conversation: Type for request-response messages
- T_Meeting: Type for meeting messages
"""

import logging
from typing import Generic, List, Optional

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
from .handlers.types import T_OneWay, T_Conversation, T_Meeting
from .handlers.events import MeetingEventHandler, MeetingEventType
from .handlers import shutdown as shutdown_handlers
from .messaging.one_way import OneWayMessenger
from .messaging.conversation import Conversation
from .messaging.meeting import MeetingManager

logger = logging.getLogger(__name__)


class AgentMessaging(Generic[T_OneWay, T_Conversation, T_Meeting]):
    """Main SDK class for Agent Messaging Protocol.

    This is the primary entry point for using the Agent Messaging Protocol SDK.
    It provides methods for managing organizations, agents, and messaging.

    This class uses 3 generic type parameters:
    - T_OneWay: Type for fire-and-forget messages
    - T_Conversation: Type for request-response messages
    - T_Meeting: Type for meeting messages

    Handlers are registered globally using decorators from agent_messaging.handlers:
    - @register_one_way_handler
    - @register_conversation_handler
    - @register_meeting_handler

    Supports three configuration patterns:

    **Direct Python Configuration (Recommended for PyPI users):**
    ```python
    from agent_messaging import AgentMessaging, Config, DatabaseConfig

    config = Config(
        database=DatabaseConfig(host="prod-db", password="secret"),
        debug=False
    )
    async with AgentMessaging[Notification, Query, MeetingMsg](config=config) as sdk:
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
    async with AgentMessaging[Notification, Query, MeetingMsg]() as sdk:
        pass
    ```

    Example:
        from agent_messaging import AgentMessaging
        from agent_messaging.handlers import (
            register_one_way_handler,
            register_conversation_handler,
            MessageContext,
        )

        # Define handlers globally
        @register_one_way_handler
        async def handle_notification(message: Notification, context: MessageContext) -> None:
            print(f"Received: {message}")

        @register_conversation_handler
        async def handle_query(message: Query, context: MessageContext) -> Query:
            return Query(response="Hello")

        # Use the SDK
        async with AgentMessaging[Notification, Query, MeetingMsg]() as sdk:
            await sdk.register_organization("org_001", "My Organization")
            await sdk.register_agent("alice", "org_001", "Alice Agent")
            await sdk.one_way.send("alice", "bob", Notification(text="Hi"))
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
        self._event_handler = MeetingEventHandler()

        # Repositories (initialized in __aenter__)
        self._org_repo: Optional[OrganizationRepository] = None
        self._agent_repo: Optional[AgentRepository] = None
        self._message_repo: Optional[MessageRepository] = None
        self._session_repo: Optional[SessionRepository] = None
        self._meeting_repo: Optional[MeetingRepository] = None

        logger.info("AgentMessaging SDK initialized")

    async def __aenter__(self) -> "AgentMessaging[T_OneWay, T_Conversation, T_Meeting]":
        """Async context manager entry.

        Initializes database connection pool, schema (if enabled), and repositories.

        Returns:
            Self instance
        """
        logger.info("Entering AgentMessaging context")
        await self._db_manager.initialize()

        # Initialize database schema if enabled (idempotent, safe to call multiple times)
        if self.config.auto_initialize_schema:
            await self._db_manager.initialize_schema()

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
        await shutdown_handlers()
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

    async def deregister_organization(self, external_id: str) -> bool:
        """Deregister (delete) an organization.

        WARNING: This will cascade delete all related agents, sessions, messages,
        and meetings associated with this organization due to foreign key constraints.
        Use with caution in production environments.

        Args:
            external_id: External identifier

        Returns:
            True if organization was deleted, False if not found

        Raises:
            ValueError: If external_id is invalid
        """
        if not self._org_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")

        external_id = external_id.strip()

        logger.info(f"Deregistering organization: {external_id}")
        deleted = await self._org_repo.delete(external_id)
        if deleted:
            logger.info(f"Organization deregistered: {external_id}")
        else:
            logger.warning(f"Organization not found for deregistration: {external_id}")
        return deleted

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

    async def deregister_agent(self, external_id: str) -> bool:
        """Deregister (delete) an agent.

        WARNING: This will cascade delete all related sessions, messages, and meeting
        participations associated with this agent due to foreign key constraints.
        Use with caution in production environments.

        Args:
            external_id: External identifier

        Returns:
            True if agent was deleted, False if not found

        Raises:
            ValueError: If external_id is invalid
        """
        if not self._agent_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Input validation
        if not external_id or not isinstance(external_id, str):
            raise ValueError("external_id must be a non-empty string")
        if len(external_id.strip()) == 0:
            raise ValueError("external_id cannot be empty or whitespace")

        external_id = external_id.strip()

        logger.info(f"Deregistering agent: {external_id}")
        deleted = await self._agent_repo.delete(external_id)
        if deleted:
            logger.info(f"Agent deregistered: {external_id}")
        else:
            logger.warning(f"Agent not found for deregistration: {external_id}")
        return deleted

    # ========================================================================
    # Event Handler Registration
    # ========================================================================

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
    # Message Search
    # ========================================================================

    async def search_messages(
        self,
        search_query: str,
        sender_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        session_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List:
        """Search messages using full-text search.

        Uses PostgreSQL's full-text search capabilities to find messages
        matching the search query. Supports complex queries with AND, OR, NOT operators.

        Query examples:
            - "database" - find messages containing "database"
            - "database postgres" - find messages with both words (AND)
            - "database OR postgres" - find messages with either word
            - "database -mysql" - find "database" but not "mysql" (NOT)
            - '"full text search"' - exact phrase search

        Args:
            search_query: Search query string (user-friendly syntax)
            sender_id: Optional filter by sender external ID
            recipient_id: Optional filter by recipient external ID
            session_id: Optional filter by session ID (UUID string)
            meeting_id: Optional filter by meeting ID (UUID string)
            limit: Maximum number of results (default: 50)
            offset: Number of results to skip (default: 0)

        Returns:
            List of matching message contents ordered by relevance

        Raises:
            RuntimeError: If SDK not initialized
            ValueError: If IDs are invalid
        """
        if not self._message_repo or not self._agent_repo:
            raise RuntimeError("SDK not initialized. Use 'async with' context manager.")

        # Convert external IDs to UUIDs if provided
        sender_uuid = None
        if sender_id:
            sender = await self._agent_repo.get_by_external_id(sender_id)
            if not sender:
                raise ValueError(f"Sender not found: {sender_id}")
            sender_uuid = sender.id

        recipient_uuid = None
        if recipient_id:
            recipient = await self._agent_repo.get_by_external_id(recipient_id)
            if not recipient:
                raise ValueError(f"Recipient not found: {recipient_id}")
            recipient_uuid = recipient.id

        # Convert session/meeting IDs to UUIDs if provided
        from uuid import UUID

        session_uuid = None
        if session_id:
            try:
                session_uuid = UUID(session_id)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid session_id format: {session_id}")

        meeting_uuid = None
        if meeting_id:
            try:
                meeting_uuid = UUID(meeting_id)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid meeting_id format: {meeting_id}")

        # Perform search
        messages = await self._message_repo.get_messages_by_search(
            search_query=search_query,
            sender_id=sender_uuid,
            recipient_id=recipient_uuid,
            session_id=session_uuid,
            meeting_id=meeting_uuid,
            limit=limit,
            offset=offset,
        )

        # Convert to generic type T
        return [message.content for message in messages]  # type: ignore

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

    # ========================================================================
    # Messaging Properties
    # ========================================================================

    @property
    def one_way(self) -> "OneWayMessenger[T_OneWay]":
        """Get one-way messenger for fire-and-forget messaging."""
        return OneWayMessenger[T_OneWay](
            message_repo=self._message_repo,
            agent_repo=self._agent_repo,
            org_repo=self._org_repo,
        )

    @property
    def conversation(self) -> "Conversation[T_Conversation]":
        """Get unified conversation messenger for both sync and async messaging."""
        return Conversation[T_Conversation](
            message_repo=self._message_repo,
            session_repo=self._session_repo,
            agent_repo=self._agent_repo,
        )

    @property
    def meeting(self) -> "MeetingManager[T_Meeting]":
        """Get meeting manager for multi-agent meetings."""
        from .messaging.meeting import MeetingManager

        return MeetingManager[T_Meeting](
            meeting_repo=self._meeting_repo,
            message_repo=self._message_repo,
            agent_repo=self._agent_repo,
            event_handler=self._event_handler,
        )
