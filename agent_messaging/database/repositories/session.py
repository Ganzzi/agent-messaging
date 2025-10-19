"""Session repository for database operations."""

from typing import List, Optional
from uuid import UUID

from .base import BaseRepository
from ...models import Session, SessionStatus, SessionType


class SessionRepository(BaseRepository):
    """Repository for session-related database operations."""

    async def create(
        self,
        agent_a_id: UUID,
        agent_b_id: UUID,
        session_type: SessionType,
    ) -> UUID:
        """Create a new session between two agents.

        Args:
            agent_a_id: First agent UUID
            agent_b_id: Second agent UUID
            session_type: Type of session (sync or async)

        Returns:
            UUID of the created session
        """
        # Ensure consistent ordering: agent_a_id < agent_b_id
        if agent_a_id > agent_b_id:
            agent_a_id, agent_b_id = agent_b_id, agent_a_id

        query = """
            INSERT INTO sessions (agent_a_id, agent_b_id, session_type, status)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        result = await self._fetch_one(
            query,
            [str(agent_a_id), str(agent_b_id), session_type.value, SessionStatus.ACTIVE.value],
        )
        return result["id"]

    async def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """Get session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session if found, None otherwise
        """
        query = """
            SELECT id, agent_a_id, agent_b_id, session_type, status,
                   locked_agent_id, created_at, updated_at, ended_at
            FROM sessions
            WHERE id = $1
        """
        result = await self._fetch_one(query, [str(session_id)])
        return self._session_from_db(result) if result else None

    async def get_active_session(
        self,
        agent_id_1: UUID,
        agent_id_2: UUID,
        session_type: SessionType,
    ) -> Optional[Session]:
        """Get active session between two agents.

        Args:
            agent_id_1: First agent UUID
            agent_id_2: Second agent UUID
            session_type: Type of session

        Returns:
            Session if found and active, None otherwise
        """
        # Ensure consistent ordering
        if agent_id_1 > agent_id_2:
            agent_id_1, agent_id_2 = agent_id_2, agent_id_1

        query = """
            SELECT id, agent_a_id, agent_b_id, session_type, status,
                   locked_agent_id, created_at, updated_at, ended_at
            FROM sessions
            WHERE agent_a_id = $1 AND agent_b_id = $2
              AND session_type = $3 AND status = $4
        """
        result = await self._fetch_one(
            query,
            [str(agent_id_1), str(agent_id_2), session_type.value, SessionStatus.ACTIVE.value],
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
        await self._execute(query, [status.value, str(session_id)])

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
        await self._execute(query, [str(agent_id) if agent_id else None, str(session_id)])

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
        await self._execute(query, [SessionStatus.ENDED.value, str(session_id)])

    async def get_agent_sessions(
        self,
        agent_id: UUID,
        session_type: Optional[SessionType] = None,
    ) -> List[Session]:
        """Get all sessions for an agent.

        Args:
            agent_id: Agent UUID
            session_type: Optional filter by session type

        Returns:
            List of sessions
        """
        if session_type:
            query = """
                SELECT id, agent_a_id, agent_b_id, session_type, status,
                       locked_agent_id, created_at, updated_at, ended_at
                FROM sessions
                WHERE (agent_a_id = $1 OR agent_b_id = $1)
                  AND session_type = $2
                ORDER BY created_at DESC
            """
            results = await self._fetch_all(query, [str(agent_id), session_type.value])
        else:
            query = """
                SELECT id, agent_a_id, agent_b_id, session_type, status,
                       locked_agent_id, created_at, updated_at, ended_at
                FROM sessions
                WHERE agent_a_id = $1 OR agent_b_id = $1
                ORDER BY created_at DESC
            """
            results = await self._fetch_all(query, [str(agent_id)])

        return [self._session_from_db(result) for result in results]

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
            session_type=SessionType(result["session_type"]),
            status=SessionStatus(result["status"]),
            locked_agent_id=result["locked_agent_id"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            ended_at=result["ended_at"],
        )
