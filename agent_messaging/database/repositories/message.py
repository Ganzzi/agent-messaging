"""Message repository for database operations."""

import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from .base import BaseRepository
from ...models import Message, MessageType

T = TypeVar("T")


class MessageRepository(BaseRepository):
    """Repository for message-related database operations."""

    async def create(
        self,
        sender_id: UUID,
        recipient_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        meeting_id: Optional[UUID] = None,
        message_type: MessageType = MessageType.USER_DEFINED,
        content: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Create a new message.

        Args:
            sender_id: UUID of the sender
            recipient_id: Optional UUID of the recipient
            session_id: Optional UUID of the session
            meeting_id: Optional UUID of the meeting
            message_type: Type of message
            content: Message content as dict
            metadata: Optional metadata

        Returns:
            UUID of the created message
        """
        query = """
            INSERT INTO messages (
                sender_id, recipient_id, session_id, meeting_id,
                message_type, content, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        content_json = json.dumps(content or {})
        metadata_json = json.dumps(metadata) if metadata else None

        result = await self._fetch_one(
            query,
            [
                str(sender_id),
                str(recipient_id) if recipient_id else None,
                str(session_id) if session_id else None,
                str(meeting_id) if meeting_id else None,
                message_type.value,
                content_json,
                metadata_json,
            ],
        )
        return result["id"]

    async def get_by_id(self, message_id: UUID) -> Optional[Message]:
        """Get message by ID.

        Args:
            message_id: Message UUID

        Returns:
            Message if found, None otherwise
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE id = $1
        """
        result = await self._fetch_one(query, [str(message_id)])
        return self._message_from_db(result) if result else None

    async def get_messages_for_recipient(
        self,
        recipient_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Get messages for a recipient.

        Args:
            recipient_id: Recipient UUID
            limit: Maximum number of messages
            offset: Offset for pagination

        Returns:
            List of messages
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE recipient_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        results = await self._fetch_all(
            query,
            [str(recipient_id), limit, offset],
        )
        return [self._message_from_db(result) for result in results]

    async def get_messages_for_session(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> List[Message]:
        """Get messages for a session.

        Args:
            session_id: Session UUID
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
        """
        results = await self._fetch_all(query, [str(session_id), limit])
        return [self._message_from_db(result) for result in results]

    async def get_messages_for_meeting(
        self,
        meeting_id: UUID,
        limit: int = 100,
    ) -> List[Message]:
        """Get messages for a meeting.

        Args:
            meeting_id: Meeting UUID
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE meeting_id = $1
            ORDER BY created_at ASC
            LIMIT $2
        """
        results = await self._fetch_all(query, [str(meeting_id), limit])
        return [self._message_from_db(result) for result in results]

    async def mark_as_read(self, message_id: UUID) -> None:
        """Mark a message as read.

        Args:
            message_id: Message UUID
        """
        query = """
            UPDATE messages
            SET read_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND read_at IS NULL
        """
        await self._execute(query, [str(message_id)])

    async def get_unread_messages(self, recipient_id: UUID) -> List[Message]:
        """Get unread messages for a recipient.

        Args:
            recipient_id: Recipient UUID

        Returns:
            List of unread messages ordered by creation time
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE recipient_id = $1 AND read_at IS NULL
            ORDER BY created_at ASC
        """
        results = await self._fetch_all(query, [str(recipient_id)])
        return [self._message_from_db(result) for result in results]

    async def get_messages_between_agents(
        self,
        recipient_id: UUID,
        sender_id: UUID,
        limit: int = 100,
    ) -> List[Message]:
        """Get messages between two specific agents.

        Args:
            recipient_id: Recipient agent UUID
            sender_id: Sender agent UUID
            limit: Maximum number of messages

        Returns:
            List of messages ordered by creation time
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE recipient_id = $1 AND sender_id = $2
            ORDER BY created_at ASC
            LIMIT $3
        """
        results = await self._fetch_all(query, [str(recipient_id), str(sender_id), limit])
        return [self._message_from_db(result) for result in results]

    async def get_unread_messages_from_sender(
        self,
        recipient_id: UUID,
        sender_id: UUID,
    ) -> List[Message]:
        """Get unread messages from a specific sender.

        Args:
            recipient_id: Recipient agent UUID
            sender_id: Sender agent UUID

        Returns:
            List of unread messages ordered by creation time
        """
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE recipient_id = $1 AND sender_id = $2 AND read_at IS NULL
            ORDER BY created_at ASC
        """
        results = await self._fetch_all(query, [str(recipient_id), str(sender_id)])
        return [self._message_from_db(result) for result in results]

    def _message_from_db(self, result: Dict[str, Any]) -> Message:
        """Convert database row to Message model.

        Args:
            result: Database row

        Returns:
            Message instance
        """
        return Message(
            id=result["id"],
            sender_id=result["sender_id"],
            recipient_id=result["recipient_id"],
            session_id=result["session_id"],
            meeting_id=result["meeting_id"],
            message_type=MessageType(result["message_type"]),
            content=result["content"],
            read_at=result["read_at"],
            created_at=result["created_at"],
            metadata=result["metadata"],
        )
