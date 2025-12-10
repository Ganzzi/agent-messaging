"""One-way messaging implementation (one-to-many)."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..exceptions import AgentNotFoundError, NoHandlerRegisteredError
from ..handlers.registry import HandlerRegistry
from ..handlers.types import HandlerContext
from ..models import MessageContext, MessageType

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OneWayMessenger(Generic[T]):
    """One-to-many message delivery.

    Sends messages from one sender to multiple recipients.
    No session management, no waiting for response.
    Handlers are invoked immediately for all recipients concurrently.
    """

    def __init__(
        self,
        handler_registry: HandlerRegistry,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
    ):
        """Initialize the OneWayMessenger.

        Args:
            handler_registry: Registry for message handlers
            message_repo: Repository for message operations
            agent_repo: Repository for agent operations
        """
        self._handler_registry = handler_registry
        self._message_repo = message_repo
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

    async def send(
        self,
        sender_external_id: str,
        recipient_external_ids: List[str],
        message: T,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Send a one-way message to multiple recipients.

        All recipients' handlers will be invoked concurrently (if handler is registered).
        Messages are stored for all recipients even if some fail.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_ids: List of recipient external IDs
            message: Message to send to all recipients
            metadata: Optional custom metadata to attach (for tracking, filtering, etc.)

        Returns:
            List of message IDs (UUIDs as strings) - one per recipient

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or any recipient doesn't exist
            NoHandlerRegisteredError: If no handler is registered

        Example:
            message_ids = await sdk.one_way.send(
                "notification_service",
                ["alice", "bob", "charlie"],
                {"type": "system_update", "message": "Server maintenance at 3 AM"},
                metadata={"priority": "high", "request_id": "req-123"}
            )
        """
        # Input validation
        if not sender_external_id or not isinstance(sender_external_id, str):
            raise ValueError("sender_external_id must be a non-empty string")
        if not recipient_external_ids or not isinstance(recipient_external_ids, list):
            raise ValueError("recipient_external_ids must be a non-empty list")
        if len(sender_external_id.strip()) == 0:
            raise ValueError("sender_external_id cannot be empty or whitespace")
        if len(recipient_external_ids) == 0:
            raise ValueError("recipient_external_ids cannot be empty")

        sender_external_id = sender_external_id.strip()
        recipient_external_ids = [r.strip() for r in recipient_external_ids if isinstance(r, str)]

        if len(recipient_external_ids) == 0:
            raise ValueError("recipient_external_ids must contain valid strings")
        if sender_external_id in recipient_external_ids:
            raise ValueError("sender cannot be in recipient list")

        logger.info(
            f"Sending one-way message from {sender_external_id} to {len(recipient_external_ids)} recipients"
        )

        # Validate sender exists
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        # Validate all recipients exist
        recipients = []
        for recipient_id in recipient_external_ids:
            recipient = await self._agent_repo.get_by_external_id(recipient_id)
            if not recipient:
                raise AgentNotFoundError(f"Recipient agent not found: {recipient_id}")
            recipients.append((recipient_id, recipient))

        # Check handler is registered
        if not self._handler_registry.has_handler():
            raise NoHandlerRegisteredError("No handler registered")

        # Serialize message content once
        content_dict = self._serialize_content(message)

        # Send to all recipients
        message_ids = []
        for recipient_external_id, recipient in recipients:
            # Store message in database
            message_id = await self._message_repo.create(
                sender_id=sender.id,
                recipient_id=recipient.id,
                content=content_dict,
                message_type=MessageType.USER_DEFINED,
                metadata=metadata or {},
            )

            # Create message context
            context = MessageContext(
                sender_id=sender_external_id,
                recipient_id=recipient_external_id,
                message_id=message_id,
                timestamp=datetime.now(),
            )

            # Invoke handler asynchronously (fire-and-forget)
            # Uses type-based routing: tries agent-specific handler first, falls back to global
            self._handler_registry.invoke_handler_async(
                message,
                context,
                agent_external_id=recipient_external_id,
                handler_context=HandlerContext.ONE_WAY,
            )

            message_ids.append(str(message_id))
            logger.debug(f"Message sent to {recipient_external_id}: {message_id}")

        logger.info(f"One-way message sent successfully to {len(message_ids)} recipients")
        return message_ids
