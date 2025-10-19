"""Synchronous conversation implementation with blocking wait."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..database.repositories.session import SessionRepository
from ..exceptions import AgentNotFoundError, NoHandlerRegisteredError, TimeoutError
from ..handlers.registry import HandlerRegistry
from ..models import MessageContext, MessageType, SessionStatus, SessionType
from ..utils.locks import SessionLock

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SyncConversation(Generic[T]):
    """Synchronous conversation with blocking request-response pattern.

    Sender blocks and waits for recipient response within a timeout.
    Uses PostgreSQL advisory locks for coordination.
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        agent_repo: AgentRepository,
    ):
        """Initialize the SyncConversation.

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

        # Track waiting events for responses
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
            AgentNotFoundError: If sender or recipient doesn't exist
            NoHandlerRegisteredError: If recipient has no handler
            TimeoutError: If no response within timeout

        Example:
            response = await sdk.sync_conversation.send_and_wait(
                "alice",
                "support_agent",
                SupportQuery(question="How do I reset password?"),
                timeout=60.0
            )
        """
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

        # Check recipient has handler
        if not self._handler_registry.has_handler(recipient_external_id):
            raise NoHandlerRegisteredError(
                f"No handler registered for recipient: {recipient_external_id}"
            )

        # Create or get active session
        session = await self._session_repo.get_active_session(
            sender.id, recipient.id, SessionType.SYNC
        )
        if not session:
            session_id = await self._session_repo.create(sender.id, recipient.id, SessionType.SYNC)
            session = await self._session_repo.get_by_id(session_id)
            if not session:
                raise RuntimeError("Failed to create session")

        # Create session lock
        session_lock = SessionLock(session.id)

        # Acquire lock for this session (blocks until acquired)
        # Note: In a real implementation, you might want timeout here too
        async with self._message_repo.pool.acquire() as connection:
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
                recipient_external_id,
                message,
                context,
            )

            # Wait for response with timeout
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)

                # Get response
                if session.id in self._waiting_responses:
                    response = self._waiting_responses[session.id]
                    # Clean up
                    del self._waiting_events[session.id]
                    del self._waiting_responses[session.id]
                    return response
                else:
                    raise RuntimeError("Response received but not found in storage")

            except asyncio.TimeoutError:
                # Clean up on timeout
                if session.id in self._waiting_events:
                    del self._waiting_events[session.id]
                if session.id in self._waiting_responses:
                    del self._waiting_responses[session.id]
                raise TimeoutError(f"No response received within {timeout} seconds")

        finally:
            # Always release lock and clear locked agent
            async with self._message_repo.pool.acquire() as connection:
                await session_lock.release(connection)
            await self._session_repo.set_locked_agent(session.id, None)

    async def reply(
        self,
        session_id: UUID,
        responder_external_id: str,
        message: T,
    ) -> None:
        """Reply to a synchronous conversation.

        Called by the recipient handler to provide response.
        Releases the waiting sender.

        Args:
            session_id: Session UUID from MessageContext
            responder_external_id: External ID of responding agent
            message: Response message

        Raises:
            RuntimeError: If session not found or not waiting for response

        Example:
            # In recipient handler
            await sdk.sync_conversation.reply(
                context.session_id,
                "support_agent",
                SupportResponse(answer="Click reset link")
            )
        """
        logger.info(f"Replying to sync conversation {session_id} from {responder_external_id}")

        # Validate session exists
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            raise RuntimeError(f"Session not found: {session_id}")

        # Validate responder is the recipient
        responder = await self._agent_repo.get_by_external_id(responder_external_id)
        if not responder:
            raise AgentNotFoundError(f"Responder agent not found: {responder_external_id}")

        if responder.id not in [session.agent_a_id, session.agent_b_id]:
            raise RuntimeError(f"Agent {responder_external_id} not part of session {session_id}")

        # Store response
        self._waiting_responses[session_id] = message

        # Signal waiting sender
        if session_id in self._waiting_events:
            self._waiting_events[session_id].set()
            logger.info(f"Response sent for session {session_id}")
        else:
            logger.warning(f"No waiting event found for session {session_id}")

    async def end_conversation(
        self,
        agent_external_id: str,
        other_agent_external_id: str,
    ) -> None:
        """End a synchronous conversation between two agents.

        Args:
            agent_external_id: External ID of one agent
            other_agent_external_id: External ID of the other agent

        Raises:
            AgentNotFoundError: If agents don't exist
            RuntimeError: If no active session found
        """
        logger.info(
            f"Ending conversation between {agent_external_id} and {other_agent_external_id}"
        )

        # Validate agents exist
        agent1 = await self._agent_repo.get_by_external_id(agent_external_id)
        agent2 = await self._agent_repo.get_by_external_id(other_agent_external_id)
        if not agent1 or not agent2:
            raise AgentNotFoundError("One or both agents not found")

        # Find active session
        session = await self._session_repo.get_active_session(
            agent1.id, agent2.id, SessionType.SYNC
        )
        if not session:
            raise RuntimeError(
                f"No active sync conversation between {agent_external_id} and {other_agent_external_id}"
            )

        # End session
        await self._session_repo.end_session(session.id)

        # Send ending message to both agents if they have handlers
        ending_content = {"type": "conversation_ended", "reason": "explicit_end"}

        # Send to agent1 if they have a handler
        if self._handler_registry.has_handler(agent_external_id):
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
                agent_external_id,
                ending_content,  # This might need adjustment based on handler expectations
                context,
            )

        # Send to agent2 if they have a handler
        if self._handler_registry.has_handler(other_agent_external_id):
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
                other_agent_external_id,
                ending_content,  # This might need adjustment based on handler expectations
                context,
            )

        logger.info(f"Conversation ended: {session.id}")
