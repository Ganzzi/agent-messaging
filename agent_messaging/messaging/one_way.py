"""One-way messaging implementation."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, TypeVar

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..exceptions import AgentNotFoundError, NoHandlerRegisteredError
from ..handlers.registry import HandlerRegistry
from ..models import MessageContext, MessageType

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OneWayMessenger(Generic[T]):
    """Simple one-way message delivery.

    No session management, no waiting for response.
    Handler is invoked immediately for the recipient.
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
        recipient_external_id: str,
        message: T,
    ) -> str:
        """Send a one-way message.

        The recipient's handler will be invoked immediately (if registered).

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send

        Returns:
            Message ID (UUID as string)

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender or recipient doesn't exist
            NoHandlerRegisteredError: If recipient has no handler

        Example:
            await sdk.one_way.send(
                "agent_alice",
                "agent_bob",
                MyMessage(text="Hello!")
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

        sender_external_id = sender_external_id.strip()
        recipient_external_id = recipient_external_id.strip()

        logger.info(f"Sending one-way message from {sender_external_id} to {recipient_external_id}")

        # Validate sender exists
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        # Validate recipient exists
        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")

        # Check recipient has handler
        if not self._handler_registry.has_handler(recipient_external_id):
            raise NoHandlerRegisteredError(
                f"No handler registered for recipient: {recipient_external_id}"
            )

        # Serialize message content
        content_dict = self._serialize_content(message)

        # Store message in database
        message_id = await self._message_repo.create(
            sender_id=sender.id,
            recipient_id=recipient.id,
            content=content_dict,
            message_type=MessageType.USER_DEFINED,
        )

        # Create message context
        context = MessageContext(
            sender_id=sender_external_id,
            recipient_id=recipient_external_id,
            message_id=message_id,
            timestamp=datetime.now(),
        )

        # Invoke handler asynchronously (fire-and-forget)
        self._handler_registry.invoke_handler_async(
            recipient_external_id,
            message,
            context,
        )

        logger.info(f"One-way message sent successfully: {message_id}")
        return str(message_id)
