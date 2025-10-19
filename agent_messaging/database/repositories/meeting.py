"""Meeting repository for database operations."""

from typing import List, Optional
from uuid import UUID

from .base import BaseRepository
from ...models import Meeting, MeetingStatus, MeetingParticipant, ParticipantStatus


class MeetingRepository(BaseRepository):
    """Repository for meeting-related database operations."""

    async def create(
        self,
        host_id: UUID,
        turn_duration: Optional[float] = None,
    ) -> UUID:
        """Create a new meeting.

        Args:
            host_id: UUID of the host agent
            turn_duration: Optional turn duration in seconds

        Returns:
            UUID of the created meeting
        """
        query = """
            INSERT INTO meetings (host_id, status, turn_duration)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        interval_str = f"{turn_duration} seconds" if turn_duration else None
        result = await self._fetch_one(
            query,
            [str(host_id), MeetingStatus.CREATED.value, interval_str],
        )
        return result["id"]

    async def get_by_id(self, meeting_id: UUID) -> Optional[Meeting]:
        """Get meeting by ID.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Meeting if found, None otherwise
        """
        query = """
            SELECT id, host_id, status, current_speaker_id, turn_duration,
                   turn_started_at, created_at, started_at, ended_at
            FROM meetings
            WHERE id = $1
        """
        result = await self._fetch_one(query, [str(meeting_id)])
        return self._meeting_from_db(result) if result else None

    async def update_status(self, meeting_id: UUID, status: MeetingStatus) -> None:
        """Update meeting status.

        Args:
            meeting_id: Meeting UUID
            status: New status
        """
        query = """
            UPDATE meetings
            SET status = $1
            WHERE id = $2
        """
        await self._execute(query, [status.value, str(meeting_id)])

    async def start_meeting(self, meeting_id: UUID) -> None:
        """Mark meeting as started.

        Args:
            meeting_id: Meeting UUID
        """
        query = """
            UPDATE meetings
            SET status = $1, started_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self._execute(query, [MeetingStatus.ACTIVE.value, str(meeting_id)])

    async def end_meeting(self, meeting_id: UUID) -> None:
        """End a meeting.

        Args:
            meeting_id: Meeting UUID
        """
        query = """
            UPDATE meetings
            SET status = $1, ended_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self._execute(query, [MeetingStatus.ENDED.value, str(meeting_id)])

    async def set_current_speaker(
        self,
        meeting_id: UUID,
        agent_id: Optional[UUID],
        turn_started: bool = True,
    ) -> None:
        """Set the current speaker for a meeting.

        Args:
            meeting_id: Meeting UUID
            agent_id: Agent UUID (None to clear)
            turn_started: Whether to reset turn_started_at
        """
        query = """
            UPDATE meetings
            SET current_speaker_id = $1,
                turn_started_at = CASE WHEN $2::boolean THEN CURRENT_TIMESTAMP ELSE turn_started_at END
            WHERE id = $3
        """
        await self._execute(
            query,
            [str(agent_id) if agent_id else None, turn_started, str(meeting_id)],
        )

    async def add_participant(
        self,
        meeting_id: UUID,
        agent_id: UUID,
        join_order: int,
    ) -> UUID:
        """Add a participant to a meeting.

        Args:
            meeting_id: Meeting UUID
            agent_id: Agent UUID
            join_order: Join order for turn management

        Returns:
            UUID of the created participant record
        """
        query = """
            INSERT INTO meeting_participants (meeting_id, agent_id, status, join_order)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        result = await self._fetch_one(
            query,
            [str(meeting_id), str(agent_id), ParticipantStatus.INVITED.value, join_order],
        )
        return result["id"]

    async def update_participant_status(
        self,
        participant_id: UUID,
        status: ParticipantStatus,
    ) -> None:
        """Update participant status.

        Args:
            participant_id: Participant UUID
            status: New status
        """
        query = """
            UPDATE meeting_participants
            SET status = $1
            WHERE id = $2
        """
        await self._execute(query, [status.value, str(participant_id)])

    async def get_participants(self, meeting_id: UUID) -> List[MeetingParticipant]:
        """Get all participants for a meeting.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of participants
        """
        query = """
            SELECT id, meeting_id, agent_id, status, join_order, is_locked,
                   joined_at, left_at
            FROM meeting_participants
            WHERE meeting_id = $1
            ORDER BY join_order
        """
        results = await self._fetch_all(query, [str(meeting_id)])
        return [self._participant_from_db(result) for result in results]

    async def get_participant(
        self,
        meeting_id: UUID,
        agent_id: UUID,
    ) -> Optional[MeetingParticipant]:
        """Get a specific participant.

        Args:
            meeting_id: Meeting UUID
            agent_id: Agent UUID

        Returns:
            Participant if found, None otherwise
        """
        query = """
            SELECT id, meeting_id, agent_id, status, join_order, is_locked,
                   joined_at, left_at
            FROM meeting_participants
            WHERE meeting_id = $1 AND agent_id = $2
        """
        result = await self._fetch_one(query, [str(meeting_id), str(agent_id)])
        return self._participant_from_db(result) if result else None

    def _meeting_from_db(self, result: dict) -> Meeting:
        """Convert database row to Meeting model.

        Args:
            result: Database row

        Returns:
            Meeting instance
        """
        return Meeting(
            id=result["id"],
            host_id=result["host_id"],
            status=MeetingStatus(result["status"]),
            current_speaker_id=result["current_speaker_id"],
            turn_duration=result["turn_duration"],
            turn_started_at=result["turn_started_at"],
            created_at=result["created_at"],
            started_at=result["started_at"],
            ended_at=result["ended_at"],
        )

    def _participant_from_db(self, result: dict) -> MeetingParticipant:
        """Convert database row to MeetingParticipant model.

        Args:
            result: Database row

        Returns:
            MeetingParticipant instance
        """
        return MeetingParticipant(
            id=result["id"],
            meeting_id=result["meeting_id"],
            agent_id=result["agent_id"],
            status=ParticipantStatus(result["status"]),
            join_order=result["join_order"],
            is_locked=result["is_locked"],
            joined_at=result["joined_at"],
            left_at=result["left_at"],
        )
