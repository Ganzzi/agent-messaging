"""Unified conversation implementation combining sync and async patterns."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional
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
from ..handlers.registry import (
    has_handler,
    invoke_handler,
    invoke_handler_async,
)
from ..handlers.types import HandlerContext, MessageContext, T_Conversation
from ..models import MessageType, SessionStatus
from ..utils.locks import SessionLock

logger = logging.getLogger(__name__)


class Conversation(Generic[T_Conversation]):
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
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        agent_repo: AgentRepository,
    ):
        """Initialize the Conversation.

        Args:
            message_repo: Repository for message operations
            session_repo: Repository for session operations
            agent_repo: Repository for agent operations
        """
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._agent_repo = agent_repo

        # Track waiting events for responses (from sync pattern)
        self._waiting_events: Dict[UUID, asyncio.Event] = {}
        self._waiting_responses: Dict[UUID, T_Conversation] = {}

    def _serialize_content(self, message: T_Conversation) -> Dict[str, Any]:
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

    def _deserialize_content(self, content_dict: Dict[str, Any]) -> T_Conversation:
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
        message: T_Conversation,
        timeout: float = 30.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> T_Conversation:
        """Send a message and wait for response (blocking).

        Creates a session, acquires lock, sends message, waits for response.
        Recipient must call reply() to complete the conversation.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send (T_Conversation type)
            timeout: Maximum seconds to wait for response
            metadata: Optional custom metadata to attach (for tracking, filtering, etc.)

        Returns:
            Response message from recipient (T_Conversation type)

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
                timeout=60.0,
                metadata={"request_id": "req-123", "priority": "high"}
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
        if not has_handler(HandlerContext.CONVERSATION):
            raise NoHandlerRegisteredError("No conversation handler registered")

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

        # CRITICAL FIX: Use single connection scope for lock acquire/release
        # PostgreSQL advisory locks are connection-scoped, so we must acquire and
        # release on the SAME connection to avoid lock leaks
        async with self._message_repo.db_manager.connection() as connection:
            # Acquire lock for this session
            lock_acquired = await session_lock.acquire(connection)
            if not lock_acquired:
                raise SessionLockError(f"Failed to acquire lock for session {session.id}")

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
                    metadata=metadata or {},
                )

                # Get organization for context
                sender_org = await self._agent_repo.get_organization(sender.id)
                org_external_id = sender_org.external_id if sender_org else "unknown"

                # Create message context
                context = MessageContext(
                    sender_id=sender_external_id,
                    receiver_id=recipient_external_id,
                    organization_id=org_external_id,
                    handler_context=HandlerContext.CONVERSATION,
                    message_id=message_id,
                    session_id=str(session.id),
                    metadata=metadata or {},
                )

                # Invoke recipient handler and capture response
                try:
                    # Try to get handler response with short timeout (non-blocking)
                    handler_response = await asyncio.wait_for(
                        invoke_handler(
                            message,
                            context,
                            HandlerContext.CONVERSATION,
                        ),
                        timeout=0.1,  # 100ms timeout for immediate responses
                    )

                    # If handler returned a response, auto-send it
                    if handler_response is not None:
                        # Serialize handler response
                        response_content_dict = self._serialize_content(handler_response)

                        # Store response message from recipient to sender
                        response_message_id = await self._message_repo.create(
                            session_id=session.id,
                            sender_id=recipient.id,
                            recipient_id=sender.id,
                            content=response_content_dict,
                            message_type=MessageType.USER_DEFINED,
                        )

                        # Mark response as read (since we're returning it immediately)
                        await self._message_repo.mark_as_read(response_message_id)

                        # Clean up session lock
                        await self._session_repo.set_locked_agent(session.id, None)

                        # Release lock on same connection
                        await session_lock.release(connection)

                        logger.info(
                            f"Handler returned immediate response, auto-sent message {response_message_id}"
                        )
                        return handler_response

                except asyncio.TimeoutError:
                    # Handler didn't respond immediately, invoke asynchronously
                    asyncio.create_task(
                        invoke_handler_async(
                            HandlerContext.CONVERSATION,
                            message,
                            context,
                        )
                    )
                    logger.debug(f"Handler invoked asynchronously for message {message_id}")
                except Exception as e:
                    # Handler error - log and continue waiting for manual response
                    logger.error(f"Handler error for message {message_id}: {e}", exc_info=True)
                    # Still invoke async in case handler wants to retry
                    asyncio.create_task(
                        invoke_handler_async(
                            HandlerContext.CONVERSATION,
                            message,
                            context,
                        )
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
                    # Release lock on same connection
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
                        response_messages = (
                            await self._message_repo.get_unread_messages_from_sender(
                                sender.id, recipient.id
                            )
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
                # Lock is released on the SAME connection it was acquired on
                await session_lock.release(connection)
                await self._session_repo.set_locked_agent(session.id, None)

    async def send_no_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T_Conversation,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a message asynchronously (non-blocking).

        Queues message for recipient and wakes any waiting agent.
        The sender continues immediately without waiting for a response.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send
            metadata: Optional custom metadata to attach (for tracking, filtering, etc.)

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or recipient doesn't exist

        Example:
            await sdk.conversation.send_no_wait(
                "alice",
                "bob",
                ChatMessage(text="Hello Bob!"),
                metadata={"message_type": "greeting"}
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
            metadata=metadata or {},
        )

        # Get organization for context
        sender_org = await self._agent_repo.get_organization(sender.id)
        org_external_id = sender_org.external_id if sender_org else "unknown"

        # Create message context
        context = MessageContext(
            sender_id=sender_external_id,
            receiver_id=recipient_external_id,
            organization_id=org_external_id,
            handler_context=HandlerContext.CONVERSATION,
            message_id=message_id,
            session_id=str(session.id),
            metadata=metadata or {},
        )

        # Invoke recipient handler asynchronously if registered
        if has_handler(HandlerContext.CONVERSATION):
            asyncio.create_task(
                invoke_handler_async(
                    HandlerContext.CONVERSATION,
                    message,
                    context,
                )
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

        # Get organization for context
        sender_org = await self._agent_repo.get_organization(agent1.id)
        org_external_id = sender_org.external_id if sender_org else "unknown"

        # Send to agent1 if handler is registered
        if has_handler(HandlerContext.CONVERSATION):
            message_id = await self._message_repo.create(
                sender_id=agent1.id,
                recipient_id=agent2.id,
                session_id=session.id,
                content=ending_content,
                message_type=MessageType.SYSTEM,
            )
            context = MessageContext(
                sender_id=other_agent_external_id,
                receiver_id=agent_external_id,
                organization_id=org_external_id,
                handler_context=HandlerContext.CONVERSATION,
                message_id=message_id,
                session_id=str(session.id),
            )
            asyncio.create_task(
                invoke_handler_async(
                    HandlerContext.CONVERSATION,
                    ending_content,
                    context,
                )
            )

        # Send to agent2 if handler is registered
        if has_handler(HandlerContext.CONVERSATION):
            message_id = await self._message_repo.create(
                sender_id=agent2.id,
                recipient_id=agent1.id,
                session_id=session.id,
                content=ending_content,
                message_type=MessageType.SYSTEM,
            )
            context = MessageContext(
                sender_id=agent_external_id,
                receiver_id=other_agent_external_id,
                organization_id=org_external_id,
                handler_context=HandlerContext.CONVERSATION,
                message_id=message_id,
                session_id=str(session.id),
            )
            asyncio.create_task(
                invoke_handler_async(
                    HandlerContext.CONVERSATION,
                    ending_content,
                    context,
                )
            )

        logger.info(f"Conversation ended: {session.id}")

    async def get_unread_messages(
        self,
        agent_external_id: str,
    ) -> List[T_Conversation]:
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
    ) -> Optional[T_Conversation]:
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
        if not has_handler(HandlerContext.CONVERSATION):
            raise NoHandlerRegisteredError(f"No conversation handler registered")

        # Get any pending unread messages for this agent
        pending_messages = await self._message_repo.get_unread_messages(agent.id)

        if not pending_messages:
            logger.info(f"No pending messages for {agent_external_id}")
            return

        # Get organization for context
        agent_org = await self._agent_repo.get_organization(agent.id)
        org_external_id = agent_org.external_id if agent_org else "unknown"

        # Process each pending message
        for message in pending_messages:
            # Create message context
            sender = await self._agent_repo.get_by_id(message.sender_id)
            if not sender:
                logger.warning(f"Sender not found for message {message.id}")
                continue

            context = MessageContext(
                sender_id=sender.external_id,
                receiver_id=agent_external_id,
                organization_id=org_external_id,
                handler_context=HandlerContext.CONVERSATION,
                message_id=message.id,
                session_id=str(message.session_id) if message.session_id else None,
            )
            # Deserialize message content
            content = self._deserialize_content(message.content)

            # Invoke handler - run in background task
            asyncio.create_task(
                invoke_handler_async(
                    HandlerContext.CONVERSATION,
                    content,
                    context,
                )
            )

            # Mark message as read (processed)
            await self._message_repo.mark_as_read(message.id)

        logger.info(
            f"Resumed agent {agent_external_id} with {len(pending_messages)} pending messages"
        )

    async def get_active_sessions(
        self,
        agent_external_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all active sessions for an agent.

        Returns a list of all active (non-ended) conversation sessions that the agent
        is participating in, along with basic information about each session.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            List of active sessions as dictionaries with the following fields:
            - session_id: UUID of the session
            - other_agent_id: External ID of the other participant
            - other_agent_name: Name of the other participant
            - status: Session status (ACTIVE, WAITING, ENDED)
            - created_at: When the session was created
            - locked_by: External ID of agent holding the lock (if any)

        Raises:
            ValueError: If agent_external_id is invalid
            AgentNotFoundError: If agent doesn't exist

        Example:
            sessions = await sdk.conversation.get_active_sessions("alice")
            for session in sessions:
                print(f"Session with {session['other_agent_name']}: {session['session_id']}")
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")

        agent_external_id = agent_external_id.strip()

        logger.info(f"Getting active sessions for {agent_external_id}")

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_external_id}")

        # Get all sessions for this agent (both as agent_a and agent_b)
        all_sessions = await self._session_repo.get_agent_sessions(agent.id)

        # Filter for active sessions and build response with other agent info
        active_sessions = []
        for session in all_sessions:
            # Skip ended sessions
            if session.status != SessionStatus.ACTIVE:
                continue

            # Determine the other agent ID
            other_agent_id = (
                session.agent_b_id if session.agent_a_id == agent.id else session.agent_a_id
            )

            # Get other agent's details
            other_agent = await self._agent_repo.get_by_id(other_agent_id)
            if not other_agent:
                logger.warning(f"Other agent not found for session {session.id}")
                continue

            # Get locked agent details if lock is held
            locked_by = None
            if session.locked_agent_id:
                locked_agent = await self._agent_repo.get_by_id(session.locked_agent_id)
                if locked_agent:
                    locked_by = locked_agent.external_id

            active_sessions.append(
                {
                    "session_id": session.id,
                    "other_agent_id": other_agent.external_id,
                    "other_agent_name": other_agent.name,
                    "status": session.status.value,
                    "created_at": session.created_at,
                    "locked_by": locked_by,
                }
            )

        logger.info(f"Found {len(active_sessions)} active sessions for {agent_external_id}")
        return active_sessions

    async def get_messages_in_session(
        self,
        session_id: str,
        include_read: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all messages in a specific conversation session.

        Retrieves the complete message history for a session, with optional
        filtering for unread messages only.

        Args:
            session_id: UUID of the session (can be passed as string or UUID)
            include_read: If True, include read messages. If False, only unread.

        Returns:
            List of messages as dictionaries with the following fields:
            - message_id: UUID of the message
            - sender_id: External ID of the sender
            - sender_name: Name of the sender
            - message_type: Type of message (USER_DEFINED, SYSTEM, TIMEOUT, ENDING)
            - content: Deserialized message content
            - is_read: Whether message was read
            - created_at: When message was sent

        Raises:
            ValueError: If session_id is invalid
            AgentNotFoundError: If sender agent not found (logs warning but continues)

        Example:
            messages = await sdk.conversation.get_messages_in_session(
                session_id="123e4567-e89b-12d3-a456-426614174000"
            )
            for msg in messages:
                print(f"{msg['sender_name']}: {msg['content']}")

        Example (unread only):
            unread = await sdk.conversation.get_messages_in_session(
                session_id=some_session_id,
                include_read=False
            )
        """
        # Input validation
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")

        # Convert string to UUID
        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except (ValueError, TypeError):
            raise ValueError(f"session_id is not a valid UUID: {session_id}")

        logger.info(f"Getting messages for session {session_uuid}")

        # Get messages for this session from repository
        messages = await self._message_repo.get_messages_for_session(session_uuid)

        # Build response with sender info and deserialized content
        result_messages = []
        for message in messages:
            # Skip read messages if not included
            if not include_read and message.read_at is not None:
                continue

            # Get sender details
            sender = await self._agent_repo.get_by_id(message.sender_id)
            if not sender:
                logger.warning(f"Sender not found for message {message.id}")
                continue

            # Deserialize content
            content = self._deserialize_content(message.content)

            result_messages.append(
                {
                    "message_id": message.id,
                    "sender_id": sender.external_id,
                    "sender_name": sender.name,
                    "message_type": message.message_type.value,
                    "content": content,
                    "is_read": message.read_at is not None,
                    "created_at": message.created_at,
                }
            )

        logger.info(f"Retrieved {len(result_messages)} messages for session {session_uuid}")
        return result_messages

    async def get_conversation_history(
        self,
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """Get full conversation history with formatted message details.

        Args:
            session_id: Session ID (UUID as string)

        Returns:
            List of messages with full details (sender info, timestamp, content)
        """
        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except (ValueError, TypeError):
            raise ValueError(f"session_id is not a valid UUID: {session_id}")

        history = await self._session_repo.get_conversation_history(session_uuid)

        result = []
        for item in history:
            result.append(
                {
                    "message_id": str(item["id"]),
                    "sender_id": item["sender_name"],
                    "message_type": item["message_type"],
                    "content": item["content"],
                    "is_read": item["read_at"] is not None,
                    "created_at": item["created_at"],
                }
            )

        return result

    async def get_session_info(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """Get detailed session information including statistics.

        Args:
            session_id: Session ID (UUID as string)

        Returns:
            Dictionary with session details, participants, and message counts
        """
        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except (ValueError, TypeError):
            raise ValueError(f"session_id is not a valid UUID: {session_id}")

        info = await self._session_repo.get_session_info(session_uuid)

        if not info:
            raise ValueError(f"Session not found: {session_id}")

        return {
            "session_id": str(info["id"]),
            "agent_a": {
                "id": str(info["agent_a_id"]),
                "name": info["agent_a_name"],
            },
            "agent_b": {
                "id": str(info["agent_b_id"]),
                "name": info["agent_b_name"],
            },
            "status": info["status"],
            "is_locked": info["locked_agent_id"] is not None,
            "locked_by": str(info["locked_agent_id"]) if info["locked_agent_id"] else None,
            "message_count": info["message_count"],
            "read_count": info["read_count"],
            "unread_count": info["message_count"] - (info["read_count"] or 0),
            "created_at": info["created_at"],
            "updated_at": info["updated_at"],
            "ended_at": info["ended_at"],
        }

    async def get_session_statistics(
        self,
        agent_id: str,
    ) -> Dict[str, Any]:
        """Get message statistics for an agent across all sessions.

        Args:
            agent_id: Agent external ID

        Returns:
            Dictionary with conversation statistics
        """
        agent = await self._agent_repo.get_by_external_id(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")

        stats = await self._session_repo.get_session_statistics(agent.id)

        return {
            "agent_id": agent_id,
            "total_conversations": stats["total_conversations"],
            "total_messages": stats["total_messages"],
            "unread_count": stats["unread_count"],
            "sent_count": stats["sent_count"],
            "received_count": stats["received_count"],
            "unique_conversation_partners": stats["unique_senders"],
        }
