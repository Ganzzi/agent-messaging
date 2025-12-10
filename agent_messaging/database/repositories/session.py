"""Session repository for database operations."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import BaseRepository
from ...models import Session, SessionStatus


class SessionRepository(BaseRepository):
    """Repository for session-related database operations."""

    async def create(
        self,
        agent_a_id: UUID,
        agent_b_id: UUID,
    ) -> UUID:
        """Create a new session between two agents.

        Args:
            agent_a_id: First agent UUID
            agent_b_id: Second agent UUID

        Returns:
            UUID of the created session
        """
        # Ensure consistent ordering: agent_a_id < agent_b_id
        if agent_a_id > agent_b_id:
            agent_a_id, agent_b_id = agent_b_id, agent_a_id

        query = """
            INSERT INTO sessions (agent_a_id, agent_b_id, status)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        result = await self._fetch_one(
            query,
            [agent_a_id, agent_b_id, SessionStatus.ACTIVE.value],
        )
        # psqlpy returns UUID as a string or UUID object depending on version
        session_id = result["id"]
        if isinstance(session_id, str):
            session_id = UUID(session_id)
        return session_id

    async def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """Get session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session if found, None otherwise
        """
        query = """
            SELECT id, agent_a_id, agent_b_id, status,
                   locked_agent_id, created_at, updated_at, ended_at
            FROM sessions
            WHERE id = $1
        """
        result = await self._fetch_one(query, [session_id])
        return self._session_from_db(result) if result else None

    async def get_active_session(
        self,
        agent_id_1: UUID,
        agent_id_2: UUID,
    ) -> Optional[Session]:
        """Get active session between two agents.

        Args:
            agent_id_1: First agent UUID
            agent_id_2: Second agent UUID

        Returns:
            Session if found and active, None otherwise
        """
        # Ensure consistent ordering
        if agent_id_1 > agent_id_2:
            agent_id_1, agent_id_2 = agent_id_2, agent_id_1

        query = """
            SELECT id, agent_a_id, agent_b_id, status,
                   locked_agent_id, created_at, updated_at, ended_at
            FROM sessions
            WHERE agent_a_id = $1 AND agent_b_id = $2 AND status = $3
        """
        result = await self._fetch_one(
            query,
            [agent_id_1, agent_id_2, SessionStatus.ACTIVE.value],
        )
        return self._session_from_db(result) if result else None

    async def update_status(self, session_id: UUID, status: SessionStatus) -> None:
        """Update session status.

        Args:
            session_id: Session UUID
            status: New status
        """
        query = """
            UPDATE sessions
            SET status = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self._execute(query, [status.value, session_id])

    async def set_locked_agent(self, session_id: UUID, agent_id: Optional[UUID]) -> None:
        """Set or clear the locked agent for a session.

        Args:
            session_id: Session UUID
            agent_id: Agent UUID (None to clear lock)
        """
        query = """
            UPDATE sessions
            SET locked_agent_id = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self._execute(query, [agent_id if agent_id else None, session_id])

    async def end_session(self, session_id: UUID) -> None:
        """End a session.

        Args:
            session_id: Session UUID
        """
        query = """
            UPDATE sessions
            SET status = $1, ended_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self._execute(query, [SessionStatus.ENDED.value, session_id])

    async def get_agent_sessions(
        self,
        agent_id: UUID,
    ) -> List[Session]:
        """Get all sessions for an agent.

        Args:
            agent_id: Agent UUID

        Returns:
            List of sessions
        """
        query = """
            SELECT id, agent_a_id, agent_b_id, status,
                   locked_agent_id, created_at, updated_at, ended_at
            FROM sessions
            WHERE agent_a_id = $1 OR agent_b_id = $1
            ORDER BY created_at DESC
        """
        results = await self._fetch_all(query, [agent_id])

        return [self._session_from_db(result) for result in results]

    async def get_conversation_history(
        self,
        session_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get full conversation history for a session with message details.

        Args:
            session_id: Session UUID

        Returns:
            List of messages with sender names, ordered by creation time
        """
        query = """
            SELECT 
                m.id,
                m.sender_id,
                a_sender.external_id as sender_name,
                m.message_type,
                m.content,
                m.read_at,
                m.created_at
            FROM messages m
            LEFT JOIN agents a_sender ON m.sender_id = a_sender.id
            WHERE m.session_id = $1
            ORDER BY m.created_at ASC
        """
        results = await self._fetch_all(query, [session_id])
        return results if results else []

    async def get_session_info(
        self,
        session_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed session information including participants and message count.

        Args:
            session_id: Session UUID

        Returns:
            Dictionary with session details or None if not found
        """
        query = """
            SELECT 
                s.id,
                s.agent_a_id,
                a_a.external_id as agent_a_name,
                s.agent_b_id,
                a_b.external_id as agent_b_name,
                s.status,
                s.locked_agent_id,
                s.created_at,
                s.updated_at,
                s.ended_at,
                COUNT(m.id) as message_count,
                SUM(CASE WHEN m.read_at IS NOT NULL THEN 1 ELSE 0 END) as read_count
            FROM sessions s
            LEFT JOIN agents a_a ON s.agent_a_id = a_a.id
            LEFT JOIN agents a_b ON s.agent_b_id = a_b.id
            LEFT JOIN messages m ON s.id = m.session_id
            WHERE s.id = $1
            GROUP BY s.id, a_a.id, a_b.id
        """
        result = await self._fetch_one(query, [session_id])
        return result if result else None

    async def get_session_statistics(
        self,
        agent_id: UUID,
    ) -> Dict[str, Any]:
        """Get message statistics for an agent across all sessions.

        Args:
            agent_id: Agent UUID

        Returns:
            Dictionary with statistics (message_count, unread_count, total_conversations, etc.)
        """
        query = """
            SELECT 
                COUNT(DISTINCT s.id) as total_conversations,
                COUNT(m.id) as total_messages,
                SUM(CASE WHEN m.read_at IS NULL AND m.recipient_id = $1 THEN 1 ELSE 0 END) as unread_count,
                SUM(CASE WHEN m.sender_id = $1 THEN 1 ELSE 0 END) as sent_count,
                SUM(CASE WHEN m.recipient_id = $1 THEN 1 ELSE 0 END) as received_count,
                COUNT(DISTINCT m.sender_id) as unique_senders,
                COUNT(DISTINCT m.recipient_id) as unique_recipients
            FROM sessions s
            LEFT JOIN messages m ON (s.id = m.session_id)
            WHERE s.agent_a_id = $1 OR s.agent_b_id = $1
        """
        result = await self._fetch_one(query, [agent_id])
        return (
            result
            if result
            else {
                "total_conversations": 0,
                "total_messages": 0,
                "unread_count": 0,
                "sent_count": 0,
                "received_count": 0,
                "unique_senders": 0,
                "unique_recipients": 0,
            }
        )

    def _session_from_db(self, result: dict) -> Session:
        """Convert database row to Session model.

        Args:
            result: Database row

        Returns:
            Session instance
        """
        return Session(
            id=result["id"],
            agent_a_id=result["agent_a_id"],
            agent_b_id=result["agent_b_id"],
            status=SessionStatus(result["status"]),
            locked_agent_id=result["locked_agent_id"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            ended_at=result["ended_at"],
        )
