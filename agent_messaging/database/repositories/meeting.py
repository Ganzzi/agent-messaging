"""Meeting repository for database operations."""

from typing import Any, Dict, List, Optional
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
            [host_id, MeetingStatus.CREATED.value, interval_str],
        )
        meeting_id = result["id"]
        if isinstance(meeting_id, str):
            meeting_id = UUID(meeting_id)
        return meeting_id

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
        result = await self._fetch_one(query, [meeting_id])
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
        await self._execute(query, [status.value, meeting_id])

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
        await self._execute(query, [MeetingStatus.ACTIVE.value, meeting_id])

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
        await self._execute(query, [MeetingStatus.ENDED.value, meeting_id])

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
            [agent_id if agent_id else None, turn_started, meeting_id],
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
            [meeting_id, agent_id, ParticipantStatus.INVITED.value, join_order],
        )
        participant_id = result["id"]
        if isinstance(participant_id, str):
            participant_id = UUID(participant_id)
        return participant_id

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
        await self._execute(query, [status.value, participant_id])

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
        results = await self._fetch_all(query, [meeting_id])
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
        result = await self._fetch_one(query, [meeting_id, agent_id])
        return self._participant_from_db(result) if result else None

    async def get_meeting_details(
        self,
        meeting_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed meeting information with participant list and statistics.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Dictionary with meeting details including participants or None if not found
        """
        query = """
            SELECT 
                m.id,
                m.host_id,
                h.external_id as host_name,
                m.status,
                m.current_speaker_id,
                cs.external_id as current_speaker_name,
                m.turn_duration,
                m.turn_started_at,
                m.created_at,
                m.started_at,
                m.ended_at,
                COUNT(mp.id) as participant_count,
                SUM(CASE WHEN mp.status = 'attending' THEN 1 ELSE 0 END) as attending_count,
                COUNT(m_msg.id) as message_count
            FROM meetings m
            LEFT JOIN agents h ON m.host_id = h.id
            LEFT JOIN agents cs ON m.current_speaker_id = cs.id
            LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id
            LEFT JOIN messages m_msg ON m.id = m_msg.meeting_id
            WHERE m.id = $1
            GROUP BY m.id, h.id, cs.id
        """
        result = await self._fetch_one(query, [meeting_id])
        return result if result else None

    async def get_participant_history(
        self,
        meeting_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get full participant history for a meeting with detailed information.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of participants with agent names and timing information
        """
        query = """
            SELECT 
                mp.id,
                mp.agent_id,
                a.external_id as agent_name,
                mp.status,
                mp.join_order,
                mp.is_locked,
                mp.joined_at,
                mp.left_at
            FROM meeting_participants mp
            LEFT JOIN agents a ON mp.agent_id = a.id
            WHERE mp.meeting_id = $1
            ORDER BY mp.join_order ASC
        """
        results = await self._fetch_all(query, [meeting_id])
        return results if results else []

    async def get_meeting_statistics(
        self,
        agent_id: UUID,
    ) -> Dict[str, Any]:
        """Get meeting statistics for an agent (as organizer or participant).

        Args:
            agent_id: Agent UUID

        Returns:
            Dictionary with statistics (hosted_count, participated_count, total_speakers, etc.)
        """
        query = """
            SELECT 
                COUNT(DISTINCT CASE WHEN m.host_id = $1 THEN m.id END) as hosted_meetings,
                COUNT(DISTINCT CASE WHEN mp.agent_id = $1 THEN m.id END) as participated_meetings,
                COUNT(DISTINCT CASE WHEN m.host_id = $1 AND m.status = 'active' THEN m.id END) as active_hosted,
                SUM(CASE WHEN m_msg.sender_id = $1 THEN 1 ELSE 0 END) as total_messages_sent,
                COUNT(DISTINCT CASE WHEN m_msg.sender_id = $1 THEN m_msg.meeting_id END) as meetings_spoke_in,
                AVG(CASE WHEN m.started_at IS NOT NULL AND m.ended_at IS NOT NULL 
                    THEN EXTRACT(EPOCH FROM (m.ended_at - m.started_at)) 
                    ELSE NULL END) as avg_meeting_duration_seconds
            FROM meetings m
            LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id
            LEFT JOIN messages m_msg ON m.id = m_msg.meeting_id
            WHERE m.host_id = $1 OR mp.agent_id = $1
        """
        result = await self._fetch_one(query, [agent_id])
        return (
            result
            if result
            else {
                "hosted_meetings": 0,
                "participated_meetings": 0,
                "active_hosted": 0,
                "total_messages_sent": 0,
                "meetings_spoke_in": 0,
                "avg_meeting_duration_seconds": None,
            }
        )

    async def get_participation_analysis(
        self,
        meeting_id: UUID,
    ) -> Dict[str, Any]:
        """Analyze participation patterns in a meeting.

        Returns detailed statistics about each participant's activity,
        including message counts, speaking time estimates, and participation rates.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Dictionary containing:
                - total_participants: Total number of participants
                - active_participants: Number who sent at least one message
                - inactive_participants: Number who never sent a message
                - participation_rate: Percentage of participants who spoke
                - by_participant: Dict of agent_id -> participation stats
                - most_active: Agent ID of most active participant (by message count)
                - least_active: Agent ID of least active participant (among active)
                - total_messages: Total message count in meeting
        """
        # Get all participants
        participants_query = """
            SELECT mp.agent_id, a.external_id, mp.joined_at, mp.left_at, mp.status
            FROM meeting_participants mp
            JOIN agents a ON mp.agent_id = a.id
            WHERE mp.meeting_id = $1
            ORDER BY mp.join_order
        """
        participants_result = await self._fetch_all(participants_query, [meeting_id])

        if not participants_result:
            return {
                "total_participants": 0,
                "active_participants": 0,
                "inactive_participants": 0,
                "participation_rate": 0.0,
                "by_participant": {},
                "most_active": None,
                "least_active": None,
                "total_messages": 0,
            }

        # Get message statistics per participant
        message_stats_query = """
            SELECT 
                m.sender_id,
                COUNT(*) as message_count,
                MIN(m.created_at) as first_message_at,
                MAX(m.created_at) as last_message_at,
                SUM(LENGTH(m.content::text)) as total_content_length
            FROM messages m
            WHERE m.meeting_id = $1 AND m.message_type = 'user_defined'
            GROUP BY m.sender_id
        """
        message_stats = await self._fetch_all(message_stats_query, [meeting_id])
        message_stats_by_agent = {row["sender_id"]: row for row in message_stats}

        # Get meeting duration
        meeting_query = """
            SELECT started_at, ended_at
            FROM meetings
            WHERE id = $1
        """
        meeting_result = await self._fetch_one(meeting_query, [meeting_id])

        meeting_duration = None
        if meeting_result and meeting_result["started_at"] and meeting_result["ended_at"]:
            meeting_duration = (
                meeting_result["ended_at"] - meeting_result["started_at"]
            ).total_seconds()

        # Build participation analysis
        by_participant = {}
        active_count = 0
        total_messages = 0
        max_messages = 0
        min_messages = float("inf")
        most_active_id = None
        least_active_id = None

        for participant in participants_result:
            agent_id = participant["agent_id"]
            external_id = participant["external_id"]
            stats = message_stats_by_agent.get(agent_id)

            if stats:
                message_count = stats["message_count"]
                total_messages += message_count
                active_count += 1

                # Track most/least active
                if message_count > max_messages:
                    max_messages = message_count
                    most_active_id = external_id
                if message_count < min_messages:
                    min_messages = message_count
                    least_active_id = external_id

                # Calculate speaking time percentage (rough estimate)
                speaking_time_percentage = None
                if meeting_duration and total_messages > 0:
                    # Estimate: assume equal time per message
                    speaking_time_percentage = (message_count / total_messages) * 100

                by_participant[external_id] = {
                    "message_count": message_count,
                    "first_message_at": (
                        stats["first_message_at"].isoformat() if stats["first_message_at"] else None
                    ),
                    "last_message_at": (
                        stats["last_message_at"].isoformat() if stats["last_message_at"] else None
                    ),
                    "total_content_length": stats["total_content_length"] or 0,
                    "speaking_time_percentage": (
                        round(speaking_time_percentage, 2) if speaking_time_percentage else None
                    ),
                    "status": participant["status"],
                }
            else:
                # Inactive participant
                by_participant[external_id] = {
                    "message_count": 0,
                    "first_message_at": None,
                    "last_message_at": None,
                    "total_content_length": 0,
                    "speaking_time_percentage": 0.0,
                    "status": participant["status"],
                }

        total_participants = len(participants_result)
        inactive_count = total_participants - active_count
        participation_rate = (
            (active_count / total_participants * 100) if total_participants > 0 else 0.0
        )

        return {
            "total_participants": total_participants,
            "active_participants": active_count,
            "inactive_participants": inactive_count,
            "participation_rate": round(participation_rate, 2),
            "by_participant": by_participant,
            "most_active": most_active_id,
            "least_active": least_active_id if least_active_id != most_active_id else None,
            "total_messages": total_messages,
        }

    async def get_meeting_timeline(
        self,
        meeting_id: UUID,
    ) -> Dict[str, Any]:
        """Get chronological timeline of meeting events.

        Returns a timeline combining messages and meeting events
        in chronological order.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Dictionary containing:
                - meeting_id: Meeting UUID
                - started_at: Meeting start timestamp
                - ended_at: Meeting end timestamp (if ended)
                - duration_seconds: Meeting duration (if ended)
                - timeline: List of events in chronological order
        """
        # Get meeting basic info
        meeting_query = """
            SELECT id, started_at, ended_at, status
            FROM meetings
            WHERE id = $1
        """
        meeting_result = await self._fetch_one(meeting_query, [meeting_id])

        if not meeting_result:
            return {
                "meeting_id": str(meeting_id),
                "started_at": None,
                "ended_at": None,
                "duration_seconds": None,
                "timeline": [],
            }

        # Get messages
        messages_query = """
            SELECT 
                m.id,
                m.sender_id,
                a.external_id as sender_external_id,
                m.message_type,
                m.created_at,
                'message' as event_type
            FROM messages m
            JOIN agents a ON m.sender_id = a.id
            WHERE m.meeting_id = $1
            ORDER BY m.created_at ASC
        """
        messages = await self._fetch_all(messages_query, [meeting_id])

        # Get meeting events
        events_query = """
            SELECT 
                me.id,
                me.event_type,
                me.created_at,
                me.agent_id,
                a.external_id as agent_external_id,
                me.data
            FROM meeting_events me
            LEFT JOIN agents a ON me.agent_id = a.id
            WHERE me.meeting_id = $1
            ORDER BY me.created_at ASC
        """
        events = await self._fetch_all(events_query, [meeting_id])

        # Combine and sort by timestamp
        timeline = []

        for msg in messages:
            timeline.append(
                {
                    "type": "message",
                    "timestamp": msg["created_at"].isoformat(),
                    "sender_id": msg["sender_external_id"],
                    "message_type": msg["message_type"],
                    "message_id": str(msg["id"]),
                }
            )

        for event in events:
            timeline.append(
                {
                    "type": "event",
                    "timestamp": event["created_at"].isoformat(),
                    "event_type": event["event_type"],
                    "agent_id": event["agent_external_id"],
                    "data": event["data"],
                }
            )

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])

        # Calculate duration
        duration_seconds = None
        if meeting_result["started_at"] and meeting_result["ended_at"]:
            duration_seconds = (
                meeting_result["ended_at"] - meeting_result["started_at"]
            ).total_seconds()

        return {
            "meeting_id": str(meeting_id),
            "started_at": (
                meeting_result["started_at"].isoformat() if meeting_result["started_at"] else None
            ),
            "ended_at": (
                meeting_result["ended_at"].isoformat() if meeting_result["ended_at"] else None
            ),
            "duration_seconds": duration_seconds,
            "status": meeting_result["status"],
            "timeline": timeline,
        }

    async def get_turn_statistics(
        self,
        meeting_id: UUID,
    ) -> Dict[str, Any]:
        """Analyze turn-taking patterns and statistics.

        Provides insights into turn duration, turn order adherence,
        and speaking patterns.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Dictionary containing:
                - total_turns: Total number of turns taken
                - avg_messages_per_turn: Average messages sent per turn
                - turn_order_adherence: Percentage of turns following expected order
                - participants_turn_stats: Stats per participant
        """
        # Get all messages with turn information
        messages_query = """
            SELECT 
                m.sender_id,
                a.external_id as sender_external_id,
                m.created_at,
                LAG(m.sender_id) OVER (ORDER BY m.created_at) as previous_sender
            FROM messages m
            JOIN agents a ON m.sender_id = a.id
            WHERE m.meeting_id = $1 AND m.message_type = 'user_defined'
            ORDER BY m.created_at ASC
        """
        messages = await self._fetch_all(messages_query, [meeting_id])

        if not messages:
            return {
                "total_turns": 0,
                "total_messages": 0,
                "avg_messages_per_turn": 0.0,
                "unique_speakers": 0,
                "turn_changes": 0,
                "participants_turn_stats": {},
            }

        # Get participant join order
        participants_query = """
            SELECT agent_id, a.external_id, join_order
            FROM meeting_participants mp
            JOIN agents a ON mp.agent_id = a.id
            WHERE meeting_id = $1
            ORDER BY join_order
        """
        participants = await self._fetch_all(participants_query, [meeting_id])
        join_order_map = {p["agent_id"]: p["join_order"] for p in participants}
        external_id_map = {p["agent_id"]: p["external_id"] for p in participants}

        # Analyze turns
        turn_count = 0
        turn_changes = 0
        messages_in_current_turn = 0
        current_speaker = None
        participant_stats = {}

        for msg in messages:
            sender_id = msg["sender_id"]
            sender_external_id = msg["sender_external_id"]

            # Initialize participant stats
            if sender_external_id not in participant_stats:
                participant_stats[sender_external_id] = {
                    "turns_taken": 0,
                    "messages_sent": 0,
                    "avg_messages_per_turn": 0.0,
                }

            participant_stats[sender_external_id]["messages_sent"] += 1

            # Detect turn change
            if current_speaker != sender_id:
                if current_speaker is not None:
                    # Finalize previous turn
                    prev_external_id = external_id_map.get(current_speaker)
                    if prev_external_id:
                        participant_stats[prev_external_id]["turns_taken"] += 1
                    turn_changes += 1

                # Start new turn
                current_speaker = sender_id
                messages_in_current_turn = 1
                turn_count += 1
            else:
                messages_in_current_turn += 1

        # Finalize last turn
        if current_speaker:
            sender_external_id = external_id_map.get(current_speaker)
            if sender_external_id:
                participant_stats[sender_external_id]["turns_taken"] += 1

        # Calculate averages
        for stats in participant_stats.values():
            if stats["turns_taken"] > 0:
                stats["avg_messages_per_turn"] = round(
                    stats["messages_sent"] / stats["turns_taken"], 2
                )

        total_messages = len(messages)
        avg_messages_per_turn = round(total_messages / turn_count, 2) if turn_count > 0 else 0.0

        return {
            "total_turns": turn_count,
            "total_messages": total_messages,
            "avg_messages_per_turn": avg_messages_per_turn,
            "unique_speakers": len(participant_stats),
            "turn_changes": turn_changes,
            "participants_turn_stats": participant_stats,
        }

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
