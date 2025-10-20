"""Unified conversation implementation combining sync and async patterns."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..database.repositories.session import SessionRepository
from ..exceptions import (
    AgentNotFoundError,
    NoHandlerRegisteredError,
    SessionLockError,
    SessionStateError,
    TimeoutError,
)
from ..handlers.registry import HandlerRegistry
from ..models import MessageContext, MessageType, SessionStatus
from ..utils.locks import SessionLock

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Conversation(Generic[T]):
    """Unified conversation class supporting both sync and async messaging patterns.

    This class combines the functionality of SyncConversation and AsyncConversation
    into a single interface. Sessions can handle both blocking waits and message
    queues, with intelligent handler invocation logic.

    Key behaviors:
    - send_and_wait: Blocks caller until response/timeout/end
    - send_no_wait: Queues message and wakes waiting agent if any
    - get_or_wait_for_response: Checks queue then waits if empty
    - Intelligent handler triggering on first message or resume
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        agent_repo: AgentRepository,
    ):
        """Initialize the Conversation.

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

        # Track waiting events for responses (from sync pattern)
        self._waiting_events: Dict[UUID, asyncio.Event] = {}
        self._waiting_responses: Dict[UUID, T] = {}

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

    async def send_and_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T,
        timeout: float = 30.0,
    ) -> T:
        """Send a message and wait for response (blocking).

        Creates a session, acquires lock, sends message, waits for response.
        Recipient must call reply() to complete the conversation.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send
            timeout: Maximum seconds to wait for response

        Returns:
            Response message from recipient

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or recipient doesn't exist
            NoHandlerRegisteredError: If recipient has no handler
            TimeoutError: If no response within timeout

        Example:
            response = await sdk.conversation.send_and_wait(
                "alice",
                "support_agent",
                SupportQuery(question="How do I reset password?"),
                timeout=60.0
            )
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
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if timeout > 300:  # 5 minutes max
            raise ValueError("timeout cannot exceed 300 seconds")

        sender_external_id = sender_external_id.strip()
        recipient_external_id = recipient_external_id.strip()

        logger.info(
            f"Starting sync conversation from {sender_external_id} to {recipient_external_id}"
        )

        # Validate agents exist
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")

        # Check handler is registered
        if not self._handler_registry.has_handler():
            raise NoHandlerRegisteredError("No handler registered")

        # Create or get active session
        session = await self._session_repo.get_active_session(sender.id, recipient.id)
        if not session:
            session_id = await self._session_repo.create(sender.id, recipient.id)
            session = await self._session_repo.get_by_id(session_id)
            if not session:
                raise RuntimeError("Failed to create session")

        # Validate session state
        if session.status != SessionStatus.ACTIVE:
            raise SessionStateError(
                f"Session {session.id} is not active (status: {session.status})"
            )
        if session.locked_agent_id is not None:
            locked_agent = await self._agent_repo.get_by_id(session.locked_agent_id)
            locked_agent_name = locked_agent.external_id if locked_agent else "unknown"
            raise SessionLockError(
                f"Session {session.id} is already locked by agent {locked_agent_name}"
            )

        # Create session lock
        session_lock = SessionLock(session.id)

        # Acquire lock for this session (blocks until acquired)
        async with self._message_repo.db_manager.connection() as connection:
            lock_acquired = await session_lock.acquire(connection)
            if not lock_acquired:
                raise RuntimeError(f"Failed to acquire lock for session {session.id}")

        try:
            # Set sender as locked agent
            await self._session_repo.set_locked_agent(session.id, sender.id)

            # Create waiting event for response
            event = asyncio.Event()
            self._waiting_events[session.id] = event

            # Serialize message content
            content_dict = self._serialize_content(message)

            # Store request message
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

            # Invoke recipient handler asynchronously
            self._handler_registry.invoke_handler_async(
                message,
                context,
            )

            # Check for immediate response (handler might have sent a reply synchronously)
            immediate_responses = await self._message_repo.get_unread_messages_from_sender(
                sender.id, recipient.id
            )
            if immediate_responses:
                # Mark as read and return the first response
                await self._message_repo.mark_as_read(immediate_responses[0].id)
                content = self._deserialize_content(immediate_responses[0].content)
                # Clean up
                await self._session_repo.set_locked_agent(session.id, None)
                async with self._message_repo.db_manager.connection() as connection:
                    await session_lock.release(connection)
                return content

            # Wait for response with timeout
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)

                # Get response - first check _waiting_responses (for backward compatibility)
                if session.id in self._waiting_responses:
                    response = self._waiting_responses[session.id]
                    # Clean up
                    del self._waiting_events[session.id]
                    del self._waiting_responses[session.id]
                    return response
                else:
                    # Check for response messages from recipient
                    response_messages = await self._message_repo.get_unread_messages_from_sender(
                        sender.id, recipient.id
                    )
                    if response_messages:
                        # Mark as read and return the first response
                        await self._message_repo.mark_as_read(response_messages[0].id)
                        content = self._deserialize_content(response_messages[0].content)
                        # Clean up
                        del self._waiting_events[session.id]
                        return content
                    else:
                        raise RuntimeError("Response event received but no response found")

            except asyncio.TimeoutError:
                # Clean up on timeout
                if session.id in self._waiting_events:
                    del self._waiting_events[session.id]
                if session.id in self._waiting_responses:
                    del self._waiting_responses[session.id]
                raise TimeoutError(f"No response received within {timeout} seconds")

        finally:
            # Always release lock and clear locked agent
            async with self._message_repo.db_manager.connection() as connection:
                await session_lock.release(connection)
            await self._session_repo.set_locked_agent(session.id, None)

    async def send_no_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T,
    ) -> None:
        """Send a message asynchronously (non-blocking).

        Queues message for recipient and wakes any waiting agent.
        The sender continues immediately without waiting for a response.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or recipient doesn't exist

        Example:
            await sdk.conversation.send_no_wait(
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

        # Create or get active conversation session
        # Create or get active conversation session
        session = await self._session_repo.get_active_session(sender.id, recipient.id)
        if not session:
            session_id = await self._session_repo.create(sender.id, recipient.id)
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
        if self._handler_registry.has_handler():
            self._handler_registry.invoke_handler_async(
                message,
                context,
            )

        # Wake any waiting agent for this session
        if session.id in self._waiting_events:
            self._waiting_events[session.id].set()

        logger.info(f"Async message sent: {message_id} in session {session.id}")

    async def end_conversation(
        self,
        agent_external_id: str,
        other_agent_external_id: str,
    ) -> None:
        """End a conversation between two agents.

        Args:
            agent_external_id: External ID of one agent
            other_agent_external_id: External ID of the other agent

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If agents don't exist
            RuntimeError: If no active session found
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if not other_agent_external_id or not isinstance(other_agent_external_id, str):
            raise ValueError("other_agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")
        if len(other_agent_external_id.strip()) == 0:
            raise ValueError("other_agent_external_id cannot be empty or whitespace")
        if agent_external_id == other_agent_external_id:
            raise ValueError("agent_external_id and other_agent_external_id cannot be the same")

        agent_external_id = agent_external_id.strip()
        other_agent_external_id = other_agent_external_id.strip()

        logger.info(
            f"Ending conversation between {agent_external_id} and {other_agent_external_id}"
        )

        # Validate agents exist
        agent1 = await self._agent_repo.get_by_external_id(agent_external_id)
        agent2 = await self._agent_repo.get_by_external_id(other_agent_external_id)
        if not agent1 or not agent2:
            raise AgentNotFoundError("One or both agents not found")

        # Find active session
        session = await self._session_repo.get_active_session(agent1.id, agent2.id)
        if not session:
            raise RuntimeError(
                f"No active conversation between {agent_external_id} and {other_agent_external_id}"
            )

        # End session
        await self._session_repo.end_session(session.id)

        # Send ending message to both agents if handler is registered
        ending_content = {"type": "conversation_ended", "reason": "explicit_end"}

        # Send to agent1 if handler is registered
        if self._handler_registry.has_handler():
            message_id = await self._message_repo.create(
                sender_id=agent1.id,
                recipient_id=agent2.id,
                session_id=session.id,
                content=ending_content,
                message_type=MessageType.SYSTEM,
            )
            context = MessageContext(
                sender_id=other_agent_external_id,
                recipient_id=agent_external_id,
                message_id=message_id,
                timestamp=datetime.now(),
                session_id=session.id,
            )
            # Note: We send the ending message as a dict, not as generic T
            self._handler_registry.invoke_handler_async(
                ending_content,  # This might need adjustment based on handler expectations
                context,
            )

        # Send to agent2 if handler is registered
        if self._handler_registry.has_handler():
            message_id = await self._message_repo.create(
                sender_id=agent2.id,
                recipient_id=agent1.id,
                session_id=session.id,
                content=ending_content,
                message_type=MessageType.SYSTEM,
            )
            context = MessageContext(
                sender_id=agent_external_id,
                recipient_id=other_agent_external_id,
                message_id=message_id,
                timestamp=datetime.now(),
                session_id=session.id,
            )
            self._handler_registry.invoke_handler_async(
                ending_content,  # This might need adjustment based on handler expectations
                context,
            )

        logger.info(f"Conversation ended: {session.id}")

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
            messages = await sdk.conversation.get_unread_messages("bob")
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

    async def get_or_wait_for_response(
        self,
        agent_a_external_id: str,
        agent_b_external_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[T]:
        """Get response from agent_b, checking queue first then waiting if empty.

        This combines queue checking with waiting behavior. First checks for any
        unread messages from agent_b, then waits for a new message if none found.

        Args:
            agent_a_external_id: External ID of receiving agent (you)
            agent_b_external_id: External ID of sending agent (who you're waiting for)
            timeout: Optional timeout in seconds

        Returns:
            Message from agent_b, or None if timeout

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If either agent doesn't exist

        Example:
            response = await sdk.conversation.get_or_wait_for_response(
                "alice",
                "bob",
                timeout=60.0
            )
            if response:
                print(f"Bob responded: {response}")
            else:
                print("Bob didn't respond in time")
        """
        # Input validation
        if not agent_a_external_id or not isinstance(agent_a_external_id, str):
            raise ValueError("agent_a_external_id must be a non-empty string")
        if not agent_b_external_id or not isinstance(agent_b_external_id, str):
            raise ValueError("agent_b_external_id must be a non-empty string")
        if len(agent_a_external_id.strip()) == 0:
            raise ValueError("agent_a_external_id cannot be empty or whitespace")
        if len(agent_b_external_id.strip()) == 0:
            raise ValueError("agent_b_external_id cannot be empty or whitespace")
        if agent_a_external_id == agent_b_external_id:
            raise ValueError("agent_a and agent_b cannot be the same agent")

        agent_a_external_id = agent_a_external_id.strip()
        agent_b_external_id = agent_b_external_id.strip()

        logger.info(
            f"Getting or waiting for response from {agent_b_external_id} to {agent_a_external_id}"
        )

        # Validate agents exist
        agent_a = await self._agent_repo.get_by_external_id(agent_a_external_id)
        agent_b = await self._agent_repo.get_by_external_id(agent_b_external_id)
        if not agent_a:
            raise AgentNotFoundError(f"Agent A not found: {agent_a_external_id}")
        if not agent_b:
            raise AgentNotFoundError(f"Agent B not found: {agent_b_external_id}")

        # First, check for any existing unread messages from agent_b
        existing_messages = await self._message_repo.get_unread_messages_from_sender(
            agent_a.id, agent_b.id
        )

        if existing_messages:
            # Return the first unread message
            await self._message_repo.mark_as_read(existing_messages[0].id)
            content = self._deserialize_content(existing_messages[0].content)
            logger.info(f"Found existing message from {agent_b_external_id}")
            return content

        # No existing messages, wait for a new one
        logger.info(f"No existing messages, waiting for message from {agent_b_external_id}")

        # Get or create session for waiting
        session = await self._session_repo.get_active_session(agent_b.id, agent_a.id)
        if not session:
            session_id = await self._session_repo.create(agent_b.id, agent_a.id)
            session = await self._session_repo.get_by_id(session_id)
            if not session:
                raise RuntimeError("Failed to create session for waiting")

        # Create waiting event
        event = asyncio.Event()
        self._waiting_events[session.id] = event

        try:
            # Wait for message with timeout
            if timeout is not None:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            else:
                await event.wait()

            # Check if we got a response
            if session.id in self._waiting_responses:
                response = self._waiting_responses[session.id]
                del self._waiting_events[session.id]
                del self._waiting_responses[session.id]
                return response
            else:
                # Check one more time for queued messages (in case send_no_wait was used)
                final_check = await self._message_repo.get_unread_messages_from_sender(
                    agent_a.id, agent_b.id
                )
                if final_check:
                    await self._message_repo.mark_as_read(final_check[0].id)
                    content = self._deserialize_content(final_check[0].content)
                    logger.info(f"Received queued message from {agent_b_external_id}")
                    return content

                logger.warning(f"No response received from {agent_b_external_id}")
                return None

        except asyncio.TimeoutError:
            logger.info(f"Timeout waiting for response from {agent_b_external_id}")
            return None
        finally:
            # Clean up waiting event
            if session.id in self._waiting_events:
                del self._waiting_events[session.id]

    async def resume_agent_handler(
        self,
        agent_external_id: str,
    ) -> None:
        """Resume an agent that stopped working during a conversation.

        This is typically called by the system when it detects an agent
        has stopped. It processes any pending messages and invokes the handler.

        Args:
            agent_external_id: External ID of agent to resume

        Raises:
            AgentNotFoundError: If agent doesn't exist
            NoHandlerRegisteredError: If agent has no handler

        Example:
            # System detects agent_bob stopped
            await sdk.conversation.resume_agent_handler("agent_bob")
        """
        logger.info(f"Resuming agent handler for {agent_external_id}")

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_external_id}")

        # Check handler is registered
        if not self._handler_registry.has_handler():
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
                content,
                context,
            )

            # Mark message as read (processed)
            await self._message_repo.mark_as_read(message.id)

        logger.info(
            f"Resumed agent {agent_external_id} with {len(pending_messages)} pending messages"
        )
