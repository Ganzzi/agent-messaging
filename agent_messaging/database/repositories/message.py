"""Message repository for database operations."""

import json
from datetime import datetime
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
        # psqlpy expects dict/list for JSONB, not JSON strings
        content_dict = content or {}
        metadata_dict = metadata if metadata else None

        result = await self._fetch_one(
            query,
            [
                sender_id,
                recipient_id if recipient_id else None,
                session_id if session_id else None,
                meeting_id if meeting_id else None,
                message_type.value,
                content_dict,
                metadata_dict,
            ],
        )
        message_id = result["id"]
        if isinstance(message_id, str):
            message_id = UUID(message_id)
        return message_id

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
        result = await self._fetch_one(query, [message_id])
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
            [recipient_id, limit, offset],
        )
        return [self._message_from_db(result) for result in results]

    async def get_messages_for_session(
        self,
        session_id: UUID,
        limit: int = 100,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        message_types: Optional[List[MessageType]] = None,
    ) -> List[Message]:
        """Get messages for a session.

        Args:
            session_id: Session UUID
            limit: Maximum number of messages
            date_from: Optional start date filter (inclusive)
            date_to: Optional end date filter (inclusive)
            message_types: Optional list of message types to filter

        Returns:
            List of messages
        """
        conditions = ["session_id = $1"]
        params: List[Any] = [session_id]
        param_index = 2

        if date_from:
            conditions.append(f"created_at >= ${param_index}")
            params.append(date_from)
            param_index += 1

        if date_to:
            conditions.append(f"created_at <= ${param_index}")
            params.append(date_to)
            param_index += 1

        if message_types:
            type_values = ", ".join([f"'{mt.value}'" for mt in message_types])
            conditions.append(f"message_type IN ({type_values})")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at ASC
            LIMIT ${param_index}
        """
        params.append(limit)
        results = await self._fetch_all(query, params)
        return [self._message_from_db(result) for result in results]

    async def get_messages_for_meeting(
        self,
        meeting_id: UUID,
        limit: int = 100,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        message_types: Optional[List[MessageType]] = None,
    ) -> List[Message]:
        """Get messages for a meeting.

        Args:
            meeting_id: Meeting UUID
            limit: Maximum number of messages
            date_from: Optional start date filter (inclusive)
            date_to: Optional end date filter (inclusive)
            message_types: Optional list of message types to filter

        Returns:
            List of messages
        """
        conditions = ["meeting_id = $1"]
        params: List[Any] = [meeting_id]
        param_index = 2

        if date_from:
            conditions.append(f"created_at >= ${param_index}")
            params.append(date_from)
            param_index += 1

        if date_to:
            conditions.append(f"created_at <= ${param_index}")
            params.append(date_to)
            param_index += 1

        if message_types:
            type_values = ", ".join([f"'{mt.value}'" for mt in message_types])
            conditions.append(f"message_type IN ({type_values})")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at ASC
            LIMIT ${param_index}
        """
        params.append(limit)
        results = await self._fetch_all(query, params)
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
        await self._execute(query, [message_id])

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
        results = await self._fetch_all(query, [recipient_id])
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
        results = await self._fetch_all(query, [recipient_id, sender_id, limit])
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
        results = await self._fetch_all(query, [recipient_id, sender_id])
        return [self._message_from_db(result) for result in results]

    async def get_sent_messages(
        self,
        sender_id: UUID,
        limit: int = 100,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        message_types: Optional[List[MessageType]] = None,
    ) -> List[Message]:
        """Get all messages sent by an agent.

        Args:
            sender_id: Sender agent UUID
            limit: Maximum number of messages
            offset: Offset for pagination
            date_from: Optional start date filter (inclusive)
            date_to: Optional end date filter (inclusive)
            message_types: Optional list of message types to filter

        Returns:
            List of messages ordered by creation time (newest first)
        """
        conditions = ["sender_id = $1"]
        params: List[Any] = [sender_id]
        param_index = 2

        if date_from:
            conditions.append(f"created_at >= ${param_index}")
            params.append(date_from)
            param_index += 1

        if date_to:
            conditions.append(f"created_at <= ${param_index}")
            params.append(date_to)
            param_index += 1

        if message_types:
            # Create IN clause for message types
            type_values = ", ".join([f"'{mt.value}'" for mt in message_types])
            conditions.append(f"message_type IN ({type_values})")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_index} OFFSET ${param_index+1}
        """
        params.extend([limit, offset])
        results = await self._fetch_all(query, params)
        return [self._message_from_db(result) for result in results]

    async def get_received_messages(
        self,
        recipient_id: UUID,
        limit: int = 100,
        offset: int = 0,
        include_read: bool = True,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        message_types: Optional[List[MessageType]] = None,
    ) -> List[Message]:
        """Get all messages received by an agent (one-way and conversations).

        Args:
            recipient_id: Recipient agent UUID
            limit: Maximum number of messages
            offset: Offset for pagination
            include_read: Include read messages (default True)
            date_from: Optional start date filter (inclusive)
            date_to: Optional end date filter (inclusive)
            message_types: Optional list of message types to filter

        Returns:
            List of messages ordered by creation time (newest first)
        """
        conditions = ["recipient_id = $1"]
        params: List[Any] = [recipient_id]
        param_index = 2

        if not include_read:
            conditions.append("read_at IS NULL")

        if date_from:
            conditions.append(f"created_at >= ${param_index}")
            params.append(date_from)
            param_index += 1

        if date_to:
            conditions.append(f"created_at <= ${param_index}")
            params.append(date_to)
            param_index += 1

        if message_types:
            # Create IN clause for message types
            type_values = ", ".join([f"'{mt.value}'" for mt in message_types])
            conditions.append(f"message_type IN ({type_values})")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_index} OFFSET ${param_index+1}
        """
        params.extend([limit, offset])
        results = await self._fetch_all(query, params)
        return [self._message_from_db(result) for result in results]

    async def mark_messages_read(
        self,
        recipient_id: UUID,
        sender_id: Optional[UUID] = None,
    ) -> int:
        """Mark messages as read (bulk operation).

        Args:
            recipient_id: Recipient agent UUID
            sender_id: Optional specific sender to filter by

        Returns:
            Number of messages marked as read
        """
        if sender_id:
            query = """
                UPDATE messages
                SET read_at = CURRENT_TIMESTAMP
                WHERE recipient_id = $1 AND sender_id = $2 AND read_at IS NULL
            """
            await self._execute(query, [recipient_id, sender_id])
        else:
            query = """
                UPDATE messages
                SET read_at = CURRENT_TIMESTAMP
                WHERE recipient_id = $1 AND read_at IS NULL
            """
            await self._execute(query, [recipient_id])

        # Return count of affected rows by fetching unread count
        count_query = """
            SELECT COUNT(*) as count FROM messages
            WHERE recipient_id = $1 AND read_at IS NULL
        """
        result = await self._fetch_one(count_query, [recipient_id])
        # If all are marked, return previous count (this is approximate)
        return result["count"] if result else 0

    async def get_message_count(
        self,
        recipient_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        meeting_id: Optional[UUID] = None,
        read_status: Optional[bool] = None,
    ) -> int:
        """Get count of messages matching criteria.

        Args:
            recipient_id: Filter by recipient
            sender_id: Filter by sender
            session_id: Filter by session
            meeting_id: Filter by meeting
            read_status: True for read only, False for unread only, None for all

        Returns:
            Count of matching messages
        """
        conditions = []
        params: List[Any] = []
        param_index = 1

        if recipient_id:
            conditions.append(f"recipient_id = ${param_index}")
            params.append(recipient_id)
            param_index += 1

        if sender_id:
            conditions.append(f"sender_id = ${param_index}")
            params.append(sender_id)
            param_index += 1

        if session_id:
            conditions.append(f"session_id = ${param_index}")
            params.append(session_id)
            param_index += 1

        if meeting_id:
            conditions.append(f"meeting_id = ${param_index}")
            params.append(meeting_id)
            param_index += 1

        if read_status is not None:
            if read_status:
                conditions.append(f"read_at IS NOT NULL")
            else:
                conditions.append(f"read_at IS NULL")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT COUNT(*) as count FROM messages WHERE {where_clause}"

        result = await self._fetch_one(query, params)
        return result["count"] if result else 0

    async def get_messages_by_search(
        self,
        search_query: str,
        sender_id: Optional[UUID] = None,
        recipient_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        meeting_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        """Search messages using PostgreSQL full-text search.

        Searches the content field using PostgreSQL's full-text search capabilities.
        Supports complex queries with operators like AND, OR, NOT, phrase search.

        Args:
            search_query: Search query string (supports PostgreSQL tsquery syntax)
                Examples:
                - "database" - find messages containing "database"
                - "database & postgres" - find messages with both words
                - "database | postgres" - find messages with either word
                - "database & !mysql" - find "database" but not "mysql"
                - "'full text search'" - phrase search
            sender_id: Optional filter by sender UUID
            recipient_id: Optional filter by recipient UUID
            session_id: Optional filter by session UUID
            meeting_id: Optional filter by meeting UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching messages ordered by relevance (rank)
        """
        conditions = []
        params = []
        param_index = 1

        # Add full-text search condition
        # Use websearch_to_tsquery for user-friendly query syntax
        conditions.append(
            f"to_tsvector('english', content::text) @@ websearch_to_tsquery('english', ${param_index})"
        )
        params.append(search_query)
        param_index += 1

        # Add optional context filters
        if sender_id:
            conditions.append(f"sender_id = ${param_index}")
            params.append(sender_id)
            param_index += 1

        if recipient_id:
            conditions.append(f"recipient_id = ${param_index}")
            params.append(recipient_id)
            param_index += 1

        if session_id:
            conditions.append(f"session_id = ${param_index}")
            params.append(session_id)
            param_index += 1

        if meeting_id:
            conditions.append(f"meeting_id = ${param_index}")
            params.append(meeting_id)
            param_index += 1

        where_clause = " AND ".join(conditions)

        # Include ranking in results
        query = f"""
            SELECT 
                id, sender_id, recipient_id, session_id, meeting_id,
                message_type, content, read_at, created_at, metadata,
                ts_rank(to_tsvector('english', content::text), websearch_to_tsquery('english', $1)) as rank
            FROM messages
            WHERE {where_clause}
            ORDER BY rank DESC, created_at DESC
            LIMIT ${param_index} OFFSET ${param_index+1}
        """
        params.extend([limit, offset])

        results = await self._fetch_all(query, params)
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

    async def get_messages_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        recipient_id: Optional[UUID] = None,
        sender_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        meeting_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Query messages by metadata filters.

        Supports exact matches and special operators:
        - key__contains: Array contains value (for array fields)
        - key__exists: Key exists in metadata
        - key: Exact match

        Args:
            metadata_filter: Dictionary of metadata filters
            recipient_id: Optional filter by recipient
            sender_id: Optional filter by sender
            session_id: Optional filter by session
            meeting_id: Optional filter by meeting
            limit: Maximum results to return
            offset: Results offset for pagination

        Returns:
            List of matching messages

        Example:
            # Get messages with priority=high
            messages = await repo.get_messages_by_metadata(
                metadata_filter={"priority": "high"}
            )

            # Get messages with tags containing "urgent"
            messages = await repo.get_messages_by_metadata(
                metadata_filter={"tags__contains": "urgent"}
            )

            # Get messages where request_id exists
            messages = await repo.get_messages_by_metadata(
                metadata_filter={"request_id__exists": True}
            )
        """
        conditions = []
        params: List[Any] = []
        param_index = 1

        # Add metadata filters
        for key, value in metadata_filter.items():
            if "__contains" in key:
                # Array contains operator: metadata->'key' @> '[value]'
                actual_key = key.replace("__contains", "")
                conditions.append(f"metadata->'{actual_key}' @> ${param_index}")
                # For array contains, wrap value in array
                params.append(json.dumps([value]))
            elif "__exists" in key:
                # Key exists operator: metadata ? 'key'
                actual_key = key.replace("__exists", "")
                if value:  # Check if exists
                    conditions.append(f"metadata ? '{actual_key}'")
                else:  # Check if not exists
                    conditions.append(f"NOT (metadata ? '{actual_key}')")
            else:
                # Exact match: metadata->>'key' = 'value'
                conditions.append(f"metadata->>'{key}' = ${param_index}")
                params.append(str(value))
            param_index += 1

        # Add optional context filters
        if recipient_id:
            conditions.append(f"recipient_id = ${param_index}")
            params.append(recipient_id)
            param_index += 1

        if sender_id:
            conditions.append(f"sender_id = ${param_index}")
            params.append(sender_id)
            param_index += 1

        if session_id:
            conditions.append(f"session_id = ${param_index}")
            params.append(session_id)
            param_index += 1

        if meeting_id:
            conditions.append(f"meeting_id = ${param_index}")
            params.append(meeting_id)
            param_index += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_index} OFFSET ${param_index+1}
        """
        params.extend([limit, offset])

        results = await self._fetch_all(query, params)
        return [self._message_from_db(result) for result in results]
