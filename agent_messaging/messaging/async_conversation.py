"""Asynchronous conversation implementation with message queuing."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..database.repositories.session import SessionRepository
from ..exceptions import AgentNotFoundError, NoHandlerRegisteredError, TimeoutError
from ..handlers.registry import HandlerRegistry
from ..models import MessageContext, MessageType, SessionStatus, SessionType

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncConversation(Generic[T]):
    """Asynchronous conversation with message queuing.

    Sender sends message and continues immediately without waiting.
    Messages are queued for recipient to retrieve when ready.
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        agent_repo: AgentRepository,
    ):
        """Initialize the AsyncConversation.

        Args:
            handler_registry: Registry for message handlers
            message_repo: Repository for message operations
            session_repo: Repository for session operations
            agent_repo: Repository for agent operations
        """
        self._handler_registry = handler_registry
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._agent_repo = agent_repo

    def _serialize_content(self, message: T) -> Dict[str, Any]:
        """Serialize message content to dict for JSONB storage.

        Args:
            message: Message content

        Returns:
            Dict representation of the message
        """
        if isinstance(message, dict):
            return message
        elif hasattr(message, "model_dump"):  # Pydantic model
            return message.model_dump()
        else:
            # Try to convert to dict, fallback to wrapping
            try:
                return dict(message)
            except (TypeError, ValueError):
                # Wrap in dict if not convertible
                return {"data": message}

    def _deserialize_content(self, content_dict: Dict[str, Any]) -> T:
        """Deserialize message content from dict.

        Args:
            content_dict: Dict representation of message

        Returns:
            Deserialized message content
        """
        # For now, return the dict as-is. In a more sophisticated implementation,
        # this could use type hints or Pydantic models to reconstruct the original type.
        return content_dict  # type: ignore

    async def send(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T,
    ) -> UUID:
        """Send a message asynchronously (non-blocking).

        Creates or reuses a session and stores the message for the recipient.
        The sender continues immediately without waiting for a response.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send

        Returns:
            Session ID for tracking this conversation

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or recipient doesn't exist

        Example:
            session_id = await sdk.async_conversation.send(
                "alice",
                "bob",
                ChatMessage(text="Hello Bob!")
            )
            # Alice continues immediately
        """
        # Input validation
        if not sender_external_id or not isinstance(sender_external_id, str):
            raise ValueError("sender_external_id must be a non-empty string")
        if not recipient_external_id or not isinstance(recipient_external_id, str):
            raise ValueError("recipient_external_id must be a non-empty string")
        if len(sender_external_id.strip()) == 0:
            raise ValueError("sender_external_id cannot be empty or whitespace")
        if len(recipient_external_id.strip()) == 0:
            raise ValueError("recipient_external_id cannot be empty or whitespace")
        if sender_external_id == recipient_external_id:
            raise ValueError("sender and recipient cannot be the same agent")

        sender_external_id = sender_external_id.strip()
        recipient_external_id = recipient_external_id.strip()

        logger.info(f"Sending async message from {sender_external_id} to {recipient_external_id}")

        # Validate agents exist
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")

        # Create or get active async session
        session = await self._session_repo.get_active_session(
            sender.id, recipient.id, SessionType.ASYNC
        )
        if not session:
            session_id = await self._session_repo.create(sender.id, recipient.id, SessionType.ASYNC)
            session = await self._session_repo.get_by_id(session_id)
            if not session:
                raise RuntimeError("Failed to create session")

        # Serialize message content
        content_dict = self._serialize_content(message)

        # Store message
        message_id = await self._message_repo.create(
            sender_id=sender.id,
            recipient_id=recipient.id,
            session_id=session.id,
            content=content_dict,
            message_type=MessageType.USER_DEFINED,
        )

        # Create message context
        context = MessageContext(
            sender_id=sender_external_id,
            recipient_id=recipient_external_id,
            message_id=message_id,
            timestamp=datetime.now(),
            session_id=session.id,
        )

        # Invoke recipient handler asynchronously if registered
        if self._handler_registry.has_handler(recipient_external_id):
            self._handler_registry.invoke_handler_async(
                recipient_external_id,
                message,
                context,
            )

        logger.info(f"Async message sent: {message_id} in session {session.id}")
        return session.id

    async def get_unread_messages(
        self,
        agent_external_id: str,
    ) -> List[T]:
        """Get all unread messages for an agent.

        Messages are marked as read after retrieval.

        Args:
            agent_external_id: External ID of agent

        Returns:
            List of unread messages (ordered by creation time)

        Raises:
            ValueError: If agent_external_id is invalid
            AgentNotFoundError: If agent doesn't exist

        Example:
            messages = await sdk.async_conversation.get_unread_messages("bob")
            for msg in messages:
                print(f"Message: {msg}")
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")

        agent_external_id = agent_external_id.strip()

        logger.info(f"Getting unread messages for {agent_external_id}")

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_external_id}")

        # Get unread messages from database
        messages = await self._message_repo.get_unread_messages(agent.id)

        # Mark messages as read
        for message in messages:
            await self._message_repo.mark_as_read(message.id)

        # Deserialize content
        result = []
        for message in messages:
            content = self._deserialize_content(message.content)
            result.append(content)

        logger.info(f"Retrieved {len(result)} unread messages for {agent_external_id}")
        return result

    async def get_messages_from_agent(
        self,
        recipient_external_id: str,
        sender_external_id: str,
        mark_read: bool = True,
    ) -> List[T]:
        """Get messages from a specific agent.

        Args:
            recipient_external_id: External ID of receiving agent
            sender_external_id: External ID of sending agent
            mark_read: Whether to mark messages as read (default: True)

        Returns:
            List of messages from sender (ordered by creation time)

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If either agent doesn't exist

        Example:
            alice_messages = await sdk.async_conversation.get_messages_from_agent(
                "bob",
                "alice"
            )
        """
        # Input validation
        if not recipient_external_id or not isinstance(recipient_external_id, str):
            raise ValueError("recipient_external_id must be a non-empty string")
        if not sender_external_id or not isinstance(sender_external_id, str):
            raise ValueError("sender_external_id must be a non-empty string")
        if len(recipient_external_id.strip()) == 0:
            raise ValueError("recipient_external_id cannot be empty or whitespace")
        if len(sender_external_id.strip()) == 0:
            raise ValueError("sender_external_id cannot be empty or whitespace")
        if recipient_external_id == sender_external_id:
            raise ValueError("recipient and sender cannot be the same agent")

        recipient_external_id = recipient_external_id.strip()
        sender_external_id = sender_external_id.strip()

        logger.info(f"Getting messages from {sender_external_id} to {recipient_external_id}")

        # Validate agents exist
        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        # Get messages between agents
        messages = await self._message_repo.get_messages_between_agents(recipient.id, sender.id)

        # Mark messages as read if requested
        if mark_read:
            for message in messages:
                if message.read_at is None:
                    await self._message_repo.mark_as_read(message.id)

        # Deserialize content
        result = []
        for message in messages:
            content = self._deserialize_content(message.content)
            result.append(content)

        logger.info(f"Retrieved {len(result)} messages from {sender_external_id}")
        return result

    async def wait_for_message(
        self,
        recipient_external_id: str,
        sender_external_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[T]:
        """Wait for a message from a specific agent.

        Blocks until a message arrives or timeout expires.

        Args:
            recipient_external_id: External ID of receiving agent
            sender_external_id: External ID of sending agent to wait for
            timeout: Optional timeout in seconds

        Returns:
            Message from sender, or None if timeout

        Raises:
            AgentNotFoundError: If either agent doesn't exist

        Example:
            message = await sdk.async_conversation.wait_for_message(
                "bob",
                "alice",
                timeout=60.0
            )
            if message:
                print(f"Alice said: {message}")
            else:
                print("Alice didn't respond")
        """
        logger.info(f"Waiting for message from {sender_external_id} to {recipient_external_id}")

        # Validate agents exist
        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        # Poll for new messages with timeout
        start_time = asyncio.get_event_loop().time()
        poll_interval = 0.1  # Check every 100ms

        while True:
            # Check for unread messages from this sender
            messages = await self._message_repo.get_unread_messages_from_sender(
                recipient.id, sender.id
            )

            if messages:
                # Mark first message as read
                await self._message_repo.mark_as_read(messages[0].id)

                # Deserialize and return
                content = self._deserialize_content(messages[0].content)
                logger.info(f"Received message from {sender_external_id}")
                return content

            # Check timeout
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.info(f"Timeout waiting for message from {sender_external_id}")
                    return None

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def resume_agent_handler(
        self,
        agent_external_id: str,
    ) -> None:
        """Resume an agent that stopped working during a conversation.

        This is typically called by the system when it detects an agent
        has stopped. It waits for any pending messages to be sent, then
        invokes the agent's handler.

        Args:
            agent_external_id: External ID of agent to resume

        Raises:
            AgentNotFoundError: If agent doesn't exist
            NoHandlerRegisteredError: If agent has no handler

        Example:
            # System detects agent_bob stopped
            await sdk.async_conversation.resume_agent_handler("agent_bob")
        """
        logger.info(f"Resuming agent handler for {agent_external_id}")

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_external_id}")

        # Check handler is registered
        if not self._handler_registry.has_handler(agent_external_id):
            raise NoHandlerRegisteredError(f"No handler registered for agent: {agent_external_id}")

        # Get any pending unread messages for this agent
        pending_messages = await self._message_repo.get_unread_messages(agent.id)

        if not pending_messages:
            logger.info(f"No pending messages for {agent_external_id}")
            return

        # Process each pending message
        for message in pending_messages:
            # Create message context
            sender = await self._agent_repo.get_by_id(message.sender_id)
            if not sender:
                logger.warning(f"Sender not found for message {message.id}")
                continue

            context = MessageContext(
                sender_id=sender.external_id,
                recipient_id=agent_external_id,
                message_id=message.id,
                timestamp=message.created_at,
                session_id=message.session_id,
            )

            # Deserialize message content
            content = self._deserialize_content(message.content)

            # Invoke handler
            self._handler_registry.invoke_handler_async(
                agent_external_id,
                content,
                context,
            )

            # Mark message as read (processed)
            await self._message_repo.mark_as_read(message.id)

        logger.info(
            f"Resumed agent {agent_external_id} with {len(pending_messages)} pending messages"
        )
