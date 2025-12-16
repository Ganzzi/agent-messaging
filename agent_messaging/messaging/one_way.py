"""One-way messaging implementation (one-to-many)."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional

from ..database.repositories.agent import AgentRepository
from ..database.repositories.message import MessageRepository
from ..database.repositories.organization import OrganizationRepository
from ..exceptions import AgentNotFoundError, NoHandlerRegisteredError
from ..handlers.registry import (
    get_handler,
    has_handler,
    invoke_handler_async,
)
from ..handlers.types import HandlerContext, MessageContext, T_OneWay
from ..models import MessageType

logger = logging.getLogger(__name__)


class OneWayMessenger(Generic[T_OneWay]):
    """One-to-many message delivery.

    Sends messages from one sender to multiple recipients.
    No session management, no waiting for response.
    Handlers are invoked immediately for all recipients concurrently.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        org_repo: OrganizationRepository,
    ):
        """Initialize the OneWayMessenger.

        Args:
            message_repo: Repository for message operations
            agent_repo: Repository for agent operations
            org_repo: Repository for organization operations
        """
        self._message_repo = message_repo
        self._agent_repo = agent_repo
        self._org_repo = org_repo

    def _serialize_content(self, message: T_OneWay) -> Dict[str, Any]:
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
        message: T_OneWay,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Send a one-way message to multiple recipients.

        All recipients' handlers will be invoked concurrently (if handler is registered).
        Messages are stored for all recipients even if some fail.

        Args:
            sender_external_id: External ID of sender agent
            recipient_external_ids: List of recipient external IDs
            message: Message to send to all recipients (T_OneWay type)
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
                Notification(type="system_update", text="Server maintenance at 3 AM"),
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
        if not has_handler(HandlerContext.ONE_WAY):
            raise NoHandlerRegisteredError("No one-way handler registered")

        # Serialize message content once
        content_dict = self._serialize_content(message)

        # Get organization from sender for context
        sender_org = await self._org_repo.get_by_id(sender.organization_id)
        org_external_id = sender_org.external_id if sender_org else "unknown"

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
                receiver_id=recipient_external_id,
                organization_id=org_external_id,
                handler_context=HandlerContext.ONE_WAY,
                message_id=message_id,
                metadata=metadata or {},
            )

            # Invoke global handler asynchronously (fire-and-forget)
            # Use asyncio.create_task to run handler in background without waiting
            asyncio.create_task(
                invoke_handler_async(
                    HandlerContext.ONE_WAY,
                    message,
                    context,
                )
            )

            message_ids.append(str(message_id))
            logger.debug(f"Message sent to {recipient_external_id}: {message_id}")

        logger.info(f"One-way message sent successfully to {len(message_ids)} recipients")
        return message_ids

    async def get_sent_messages(
        self,
        sender_external_id: str,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get one-way messages sent by an agent.

        Args:
            sender_external_id: External ID of sender agent
            limit: Maximum number of messages to return (default: 100)
            offset: Offset for pagination (default: 0)
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            List of message dictionaries with sender/recipient info and content

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If sender not found
        """
        if not sender_external_id or not isinstance(sender_external_id, str):
            raise ValueError("sender_external_id must be a non-empty string")
        if len(sender_external_id.strip()) == 0:
            raise ValueError("sender_external_id cannot be empty")

        sender_external_id = sender_external_id.strip()

        # Get sender
        sender = await self._agent_repo.get_by_external_id(sender_external_id)
        if not sender:
            raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")

        # Get sent messages (filter for one-way: no session_id and no meeting_id)
        messages = await self._message_repo.get_sent_messages(
            sender_id=sender.id,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            message_types=[MessageType.USER_DEFINED],
        )

        # Filter for one-way only (no session, no meeting)
        one_way_messages = [m for m in messages if m.session_id is None and m.meeting_id is None]

        # Format results with agent info
        result = []
        for msg in one_way_messages:
            recipient = await self._agent_repo.get_by_id(msg.recipient_id)
            result.append(
                {
                    "message_id": str(msg.id),
                    "sender_id": sender_external_id,
                    "recipient_id": recipient.external_id if recipient else "unknown",
                    "content": msg.content,
                    "read_at": msg.read_at,
                    "created_at": msg.created_at,
                    "metadata": msg.metadata or {},
                }
            )

        return result

    async def get_received_messages(
        self,
        recipient_external_id: str,
        include_read: bool = True,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get one-way messages received by an agent.

        Args:
            recipient_external_id: External ID of recipient agent
            include_read: Include already-read messages (default: True)
            limit: Maximum number of messages to return (default: 100)
            offset: Offset for pagination (default: 0)
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            List of message dictionaries with sender/recipient info and content

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If recipient not found
        """
        if not recipient_external_id or not isinstance(recipient_external_id, str):
            raise ValueError("recipient_external_id must be a non-empty string")
        if len(recipient_external_id.strip()) == 0:
            raise ValueError("recipient_external_id cannot be empty")

        recipient_external_id = recipient_external_id.strip()

        # Get recipient
        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")

        # Get received messages
        messages = await self._message_repo.get_received_messages(
            recipient_id=recipient.id,
            include_read=include_read,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
            message_types=[MessageType.USER_DEFINED],
        )

        # Filter for one-way only (no session, no meeting)
        one_way_messages = [m for m in messages if m.session_id is None and m.meeting_id is None]

        # Format results with agent info
        result = []
        for msg in one_way_messages:
            sender = await self._agent_repo.get_by_id(msg.sender_id)
            result.append(
                {
                    "message_id": str(msg.id),
                    "sender_id": sender.external_id if sender else "unknown",
                    "recipient_id": recipient_external_id,
                    "content": msg.content,
                    "read_at": msg.read_at,
                    "created_at": msg.created_at,
                    "metadata": msg.metadata or {},
                }
            )

        return result

    async def mark_messages_read(
        self,
        recipient_external_id: str,
        sender_external_id: Optional[str] = None,
    ) -> int:
        """Mark one-way messages as read.

        Args:
            recipient_external_id: External ID of recipient agent
            sender_external_id: Optional - only mark messages from this sender

        Returns:
            Number of messages marked as read

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If recipient or sender not found
        """
        if not recipient_external_id or not isinstance(recipient_external_id, str):
            raise ValueError("recipient_external_id must be a non-empty string")
        if len(recipient_external_id.strip()) == 0:
            raise ValueError("recipient_external_id cannot be empty")

        recipient_external_id = recipient_external_id.strip()

        # Get recipient
        recipient = await self._agent_repo.get_by_external_id(recipient_external_id)
        if not recipient:
            raise AgentNotFoundError(f"Recipient agent not found: {recipient_external_id}")

        sender_id = None
        if sender_external_id:
            if not isinstance(sender_external_id, str) or len(sender_external_id.strip()) == 0:
                raise ValueError("sender_external_id must be a non-empty string if provided")
            sender_external_id = sender_external_id.strip()
            sender = await self._agent_repo.get_by_external_id(sender_external_id)
            if not sender:
                raise AgentNotFoundError(f"Sender agent not found: {sender_external_id}")
            sender_id = sender.id

        # Mark messages as read
        count = await self._message_repo.mark_messages_read(
            recipient_id=recipient.id,
            sender_id=sender_id,
        )

        return count

    async def get_message_count(
        self,
        agent_external_id: str,
        role: str = "recipient",
        read_status: Optional[bool] = None,
    ) -> int:
        """Get count of one-way messages for an agent.

        Args:
            agent_external_id: External ID of agent
            role: "recipient" or "sender" (default: "recipient")
            read_status: True for read only, False for unread only, None for all

        Returns:
            Count of matching messages

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If agent not found
        """
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty")
        if role not in ["recipient", "sender"]:
            raise ValueError("role must be 'recipient' or 'sender'")

        agent_external_id = agent_external_id.strip()

        # Get agent
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_external_id}")

        # Get message count
        if role == "recipient":
            count = await self._message_repo.get_message_count(
                recipient_id=agent.id,
                read_status=read_status,
            )
        else:
            count = await self._message_repo.get_message_count(
                sender_id=agent.id,
                read_status=read_status,
            )

        return count
