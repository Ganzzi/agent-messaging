"""Multi-agent meeting implementation with turn-based coordination."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from ..database.repositories.agent import AgentRepository
from ..database.repositories.meeting import MeetingRepository
from ..database.repositories.message import MessageRepository
from ..exceptions import (
    AgentNotFoundError,
    MeetingError,
    MeetingNotActiveError,
    MeetingPermissionError,
    MeetingStateError,
    NotYourTurnError,
)
from ..handlers.events import MeetingEventHandler
from ..utils.locks import SessionLock
from ..utils.timeouts import MeetingTimeoutManager
from ..models import (
    CreateMeetingRequest,
    Meeting,
    MeetingParticipant,
    MeetingStatus,
    MessageType,
    ParticipantStatus,
)
from ..utils.locks import SessionLock

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MeetingManager(Generic[T]):
    """Multi-agent meeting manager with turn-based coordination.

    Enables multiple agents to participate in structured meetings with
    turn-based speaking, timeout management, and event-driven notifications.
    """

    def __init__(
        self,
        meeting_repo: MeetingRepository,
        message_repo: MessageRepository,
        agent_repo: AgentRepository,
        event_handler: Optional[MeetingEventHandler] = None,
    ):
        """Initialize the MeetingManager.

        Args:
            meeting_repo: Repository for meeting operations
            message_repo: Repository for message operations
            agent_repo: Repository for agent operations
            event_handler: Optional event handler for meeting events
        """
        self._meeting_repo = meeting_repo
        self._message_repo = message_repo
        self._agent_repo = agent_repo

        # Initialize timeout manager
        self._timeout_manager = MeetingTimeoutManager(meeting_repo, message_repo)

        # Initialize event handler
        self._event_handler = event_handler or MeetingEventHandler()

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

        # Track active meetings and their locks
        self._meeting_locks: Dict[UUID, SessionLock] = {}

    async def create_meeting(
        self,
        organizer_external_id: str,
        participant_external_ids: List[str],
        turn_duration: Optional[float] = None,
    ) -> UUID:
        """Create a new meeting with participants.

        Args:
            organizer_external_id: External ID of the meeting organizer
            participant_external_ids: List of participant external IDs
            turn_duration: Optional turn duration in seconds

        Returns:
            UUID of the created meeting

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If organizer or any participant not found
        """
        # Input validation
        if not organizer_external_id or not isinstance(organizer_external_id, str):
            raise ValueError("organizer_external_id must be a non-empty string")
        if len(organizer_external_id.strip()) == 0:
            raise ValueError("organizer_external_id cannot be empty or whitespace")
        if not isinstance(participant_external_ids, list):
            raise ValueError("participant_external_ids must be a list")
        if len(participant_external_ids) == 0:
            raise ValueError("participant_external_ids cannot be empty")
        if len(participant_external_ids) > 50:
            raise ValueError("participant_external_ids cannot exceed 50 participants")
        if turn_duration is not None:
            if not isinstance(turn_duration, (int, float)) or turn_duration <= 0:
                raise ValueError("turn_duration must be a positive number")
            if turn_duration > 3600:  # 1 hour max
                raise ValueError("turn_duration cannot exceed 3600 seconds (1 hour)")

        organizer_external_id = organizer_external_id.strip()

        # Validate participant IDs
        cleaned_participants = []
        for pid in participant_external_ids:
            if not pid or not isinstance(pid, str):
                raise ValueError("All participant IDs must be non-empty strings")
            cleaned_pid = pid.strip()
            if len(cleaned_pid) == 0:
                raise ValueError("Participant IDs cannot be empty or whitespace")
            if cleaned_pid == organizer_external_id:
                raise ValueError("Organizer cannot be a participant")
            if cleaned_pid in cleaned_participants:
                raise ValueError("Duplicate participant IDs not allowed")
            cleaned_participants.append(cleaned_pid)

        participant_external_ids = cleaned_participants

        # Validate organizer exists
        organizer = await self._agent_repo.get_by_external_id(organizer_external_id)
        if not organizer:
            raise AgentNotFoundError(f"Organizer agent '{organizer_external_id}' not found")

        # Validate all participants exist
        participants = []
        for participant_id in participant_external_ids:
            participant = await self._agent_repo.get_by_external_id(participant_id)
            if not participant:
                raise AgentNotFoundError(f"Participant agent '{participant_id}' not found")
            participants.append(participant)

        # Create the meeting
        meeting_id = await self._meeting_repo.create(
            host_id=organizer.id,
            turn_duration=turn_duration,
        )

        # Add participants to the meeting
        for i, participant in enumerate(participants):
            await self._meeting_repo.add_participant(
                meeting_id=meeting_id,
                agent_id=participant.id,
                join_order=i,
            )

        logger.info(
            f"Created meeting {meeting_id} with organizer {organizer_external_id} "
            f"and {len(participants)} participants"
        )

        return meeting_id

    async def get_meeting(self, meeting_id: UUID) -> Optional[Meeting]:
        """Get meeting by ID.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Meeting if found, None otherwise

        Raises:
            ValueError: If meeting_id is invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        return await self._meeting_repo.get_by_id(meeting_id)
        """Get all participants for a meeting.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of meeting participants

        Raises:
            ValueError: If meeting_id is invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        return await self._meeting_repo.get_participants(meeting_id)

    async def update_participant_status(
        self,
        meeting_id: UUID,
        agent_id: UUID,
        status: ParticipantStatus,
    ) -> None:
        """Update participant status in a meeting.

        Args:
            meeting_id: Meeting UUID
            agent_id: Agent UUID
            status: New participant status

        Raises:
            ValueError: If parameters are invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")
        if not isinstance(agent_id, UUID):
            raise ValueError("agent_id must be a valid UUID")
        if not isinstance(status, ParticipantStatus):
            raise ValueError("status must be a valid ParticipantStatus enum value")

        await self._meeting_repo.update_participant_status(
            meeting_id=meeting_id,
            agent_id=agent_id,
            status=status,
        )

    async def attend_meeting(
        self,
        agent_external_id: str,
        meeting_id: UUID,
    ) -> bool:
        """Attend a meeting (mark agent as attending).

        Args:
            agent_external_id: External ID of the agent attending
            meeting_id: Meeting UUID

        Returns:
            True if successfully marked as attending

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found or agent not invited
            MeetingStateError: If meeting is in invalid state for attendance
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        agent_external_id = agent_external_id.strip()

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # Validate meeting exists
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

        # Validate meeting state allows attendance
        if meeting.status == MeetingStatus.ENDED:
            raise MeetingStateError(f"Cannot attend meeting {meeting_id} - meeting has ended")
        if meeting.status not in [MeetingStatus.CREATED, MeetingStatus.READY, MeetingStatus.ACTIVE]:
            raise MeetingStateError(
                f"Meeting {meeting_id} is in invalid state for attendance: {meeting.status}"
            )

        # Check if agent is a participant
        participant = await self._meeting_repo.get_participant(meeting_id, agent.id)
        if not participant:
            raise MeetingError(
                f"Agent '{agent_external_id}' is not invited to meeting {meeting_id}"
            )

        # Check if already attending
        if participant.status == ParticipantStatus.ATTENDING:
            return True

        # Update status to attending
        await self._meeting_repo.update_participant_status(
            participant_id=participant.id,
            status=ParticipantStatus.ATTENDING,
        )

        # Emit participant joined event
        await self._event_handler.emit_participant_joined(
            meeting_id=meeting_id,
            agent_id=agent.id,
        )

        logger.info(f"Agent {agent_external_id} is now attending meeting {meeting_id}")

        return True

    async def start_meeting(
        self,
        host_external_id: str,
        meeting_id: UUID,
    ) -> None:
        """Start a meeting (host only).

        Args:
            host_external_id: External ID of the meeting host
            meeting_id: Meeting UUID

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If host not found
            MeetingError: If meeting not found, not host, wrong status, or participants not ready
            MeetingPermissionError: If agent is not the host
        """
        # Input validation
        if not host_external_id or not isinstance(host_external_id, str):
            raise ValueError("host_external_id must be a non-empty string")
        if len(host_external_id.strip()) == 0:
            raise ValueError("host_external_id cannot be empty or whitespace")
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        host_external_id = host_external_id.strip()

        # Validate host exists
        host = await self._agent_repo.get_by_external_id(host_external_id)
        if not host:
            raise AgentNotFoundError(f"Host agent '{host_external_id}' not found")

        # Acquire meeting lock to prevent race conditions during start
        # (e.g., multiple start attempts, participants leaving during start)
        meeting_lock = SessionLock(meeting_id)

        async with self._message_repo.db_manager.connection() as connection:
            lock_acquired = await meeting_lock.acquire(connection)
            if not lock_acquired:
                raise MeetingError(f"Failed to acquire lock for meeting {meeting_id}")

            try:
                # Re-fetch meeting state after acquiring lock
                # (state might have changed since initial validation)
                meeting = await self._meeting_repo.get_by_id(meeting_id)
                if not meeting:
                    raise MeetingError(f"Meeting {meeting_id} not found")

                if meeting.host_id != host.id:
                    raise MeetingPermissionError(
                        f"Agent '{host_external_id}' is not the host of meeting {meeting_id}"
                    )

                # Re-check meeting status after lock acquired
                if meeting.status != MeetingStatus.CREATED:
                    raise MeetingError(
                        f"Meeting {meeting_id} is not in CREATED status (current: {meeting.status})"
                    )

                # Get all participants
                participants = await self._meeting_repo.get_participants(meeting_id)
                if not participants:
                    raise MeetingError(f"Meeting {meeting_id} has no participants")

                # Check all participants are attending
                non_attending = [p for p in participants if p.status != ParticipantStatus.ATTENDING]
                if non_attending:
                    agent_ids = [str(p.agent_id) for p in non_attending]
                    raise MeetingError(
                        f"Meeting {meeting_id} cannot start: {len(non_attending)} participants not attending: {agent_ids}"
                    )

                # Start the meeting
                await self._meeting_repo.start_meeting(meeting_id)

                # Select first speaker (first in join order)
                first_speaker = min(participants, key=lambda p: p.join_order)

                # Set current speaker and start turn
                await self._meeting_repo.set_current_speaker(
                    meeting_id=meeting_id,
                    agent_id=first_speaker.agent_id,
                    turn_started=True,
                )

                # Start timeout monitoring for first speaker
                await self._timeout_manager.start_turn_timeout(
                    meeting_id=meeting_id,
                    current_speaker_id=first_speaker.agent_id,
                    turn_duration=meeting.turn_duration,
                )

                # Emit meeting started event
                participant_ids = [p.agent_id for p in participants]
                await self._event_handler.emit_meeting_started(
                    meeting_id=meeting_id,
                    host_id=host.id,
                    participant_ids=participant_ids,
                )

                logger.info(
                    f"Meeting {meeting_id} started by host {host_external_id}. "
                    f"First speaker: agent {first_speaker.agent_id}"
                )

            finally:
                # Always release lock on same connection (PostgreSQL advisory locks are connection-scoped)
                await meeting_lock.release(connection)

    async def speak(
        self,
        agent_external_id: str,
        meeting_id: UUID,
        message: T,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Speak in a meeting (requires having the turn).

        Args:
            agent_external_id: External ID of the speaking agent
            meeting_id: Meeting UUID
            message: Message content to speak
            metadata: Optional custom metadata to attach (for tracking, filtering, etc.)

        Returns:
            Message ID of the spoken message

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found or agent not a participant
            MeetingNotActiveError: If meeting is not active
            NotYourTurnError: If it's not the agent's turn
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        agent_external_id = agent_external_id.strip()

        # Validate agent exists (before acquiring lock)
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # CRITICAL FIX: Use per-meeting lock to prevent concurrent speakers
        # Create lock using meeting_id as the lock key
        meeting_lock = SessionLock(meeting_id)

        # Acquire lock using single connection scope
        async with self._message_repo.db_manager.connection() as connection:
            lock_acquired = await meeting_lock.acquire(connection)
            if not lock_acquired:
                raise MeetingError(f"Meeting {meeting_id} is locked by another operation")

            try:
                # Re-fetch meeting state after lock acquired (state might have changed)
                meeting = await self._meeting_repo.get_by_id(meeting_id)
                if not meeting:
                    raise MeetingError(f"Meeting {meeting_id} not found")

                # Check meeting is active
                if meeting.status != MeetingStatus.ACTIVE:
                    raise MeetingNotActiveError(
                        f"Meeting {meeting_id} is not active (status: {meeting.status})"
                    )

                # Check if agent is a participant
                participant = await self._meeting_repo.get_participant(meeting_id, agent.id)
                if not participant:
                    raise MeetingError(
                        f"Agent '{agent_external_id}' is not a participant in meeting {meeting_id}"
                    )

                # Check if it's still the agent's turn (state might have changed after lock)
                if meeting.current_speaker_id != agent.id:
                    raise NotYourTurnError(
                        f"It's not {agent_external_id}'s turn in meeting {meeting_id}. "
                        f"Current speaker: {meeting.current_speaker_id}"
                    )

                # Store the message
                message_content = self._serialize_content(message)
                message_id = await self._message_repo.create(
                    session_id=None,  # Meeting messages don't have sessions
                    sender_id=agent.id,
                    recipient_id=None,  # Meeting messages go to all participants
                    meeting_id=meeting_id,
                    message_type=MessageType.USER_DEFINED,
                    content=message_content,
                    metadata=metadata or {},
                )

                # Get all participants for round-robin selection
                participants = await self._meeting_repo.get_participants(meeting_id)
                attending_participants = [
                    p for p in participants if p.status == ParticipantStatus.ATTENDING
                ]

                # Find current speaker index
                current_index = None
                for i, p in enumerate(attending_participants):
                    if p.agent_id == agent.id:
                        current_index = i
                        break

                if current_index is None:
                    raise MeetingError(
                        f"Agent {agent_external_id} not found in attending participants"
                    )

                # Select next speaker (round-robin)
                next_index = (current_index + 1) % len(attending_participants)
                next_speaker = attending_participants[next_index]

                # Update current speaker
                await self._meeting_repo.set_current_speaker(
                    meeting_id=meeting_id,
                    agent_id=next_speaker.agent_id,
                    turn_started=True,
                )

                # Start timeout monitoring for next speaker
                await self._timeout_manager.start_turn_timeout(
                    meeting_id=meeting_id,
                    current_speaker_id=next_speaker.agent_id,
                    turn_duration=meeting.turn_duration,
                )

                # Emit turn changed event
                await self._event_handler.emit_turn_changed(
                    meeting_id=meeting_id,
                    previous_speaker_id=agent.id,
                    current_speaker_id=next_speaker.agent_id,
                )

                logger.info(
                    f"Agent {agent_external_id} spoke in meeting {meeting_id} (message {message_id}). "
                    f"Next speaker: agent {next_speaker.agent_id}"
                )

                return message_id

            finally:
                # Always release lock on same connection
                await meeting_lock.release(connection)

    async def end_meeting(
        self,
        host_external_id: str,
        meeting_id: UUID,
    ) -> None:
        """End a meeting (host only).

        Args:
            host_external_id: External ID of the meeting host
            meeting_id: Meeting UUID

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If host not found
            MeetingError: If meeting not found
            MeetingPermissionError: If agent is not the host
            MeetingStateError: If meeting is not active
        """
        # Input validation
        if not host_external_id or not isinstance(host_external_id, str):
            raise ValueError("host_external_id must be a non-empty string")
        if len(host_external_id.strip()) == 0:
            raise ValueError("host_external_id cannot be empty or whitespace")
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        host_external_id = host_external_id.strip()

        # Validate host exists
        host = await self._agent_repo.get_by_external_id(host_external_id)
        if not host:
            raise AgentNotFoundError(f"Host agent '{host_external_id}' not found")

        # Acquire meeting lock to prevent race conditions during end
        # (e.g., multiple end attempts, concurrent speak/leave operations)
        meeting_lock = SessionLock(meeting_id)

        async with self._message_repo.db_manager.connection() as connection:
            lock_acquired = await meeting_lock.acquire(connection)
            if not lock_acquired:
                raise MeetingError(f"Failed to acquire lock for meeting {meeting_id}")

            try:
                # Re-fetch meeting state after acquiring lock
                # (state might have changed since initial validation)
                meeting = await self._meeting_repo.get_by_id(meeting_id)
                if not meeting:
                    raise MeetingError(f"Meeting {meeting_id} not found")

                if meeting.host_id != host.id:
                    raise MeetingPermissionError(
                        f"Agent '{host_external_id}' is not the host of meeting {meeting_id}"
                    )

                # Re-validate meeting state after lock acquired
                if meeting.status == MeetingStatus.ENDED:
                    raise MeetingStateError(f"Meeting {meeting_id} is already ended")
                if meeting.status not in [
                    MeetingStatus.CREATED,
                    MeetingStatus.READY,
                    MeetingStatus.ACTIVE,
                ]:
                    raise MeetingStateError(
                        f"Meeting {meeting_id} cannot be ended from status: {meeting.status}"
                    )

                # Cancel any active timeouts
                await self._timeout_manager.cancel_timeout(meeting_id)

                # End the meeting
                await self._meeting_repo.end_meeting(meeting_id)

                # Create ending message
                ending_content = {
                    "type": "meeting_ended",
                    "host": str(host.id),
                    "message": f"Meeting ended by host {host_external_id}",
                }

                # Store ending message (sender is host)
                await self._message_repo.create(
                    session_id=None,
                    sender_id=host.id,
                    recipient_id=None,
                    meeting_id=meeting_id,
                    message_type=MessageType.ENDING,
                    content=ending_content,
                )

                # Emit meeting ended event
                await self._event_handler.emit_meeting_ended(
                    meeting_id=meeting_id,
                    host_id=host.id,
                )

                logger.info(f"Meeting {meeting_id} ended by host {host_external_id}")

            finally:
                # Always release lock on same connection (PostgreSQL advisory locks are connection-scoped)
                await meeting_lock.release(connection)

        logger.info(f"Meeting {meeting_id} ended by host {host_external_id}")

    async def leave_meeting(
        self,
        agent_external_id: str,
        meeting_id: UUID,
    ) -> None:
        """Leave a meeting.

        Args:
            agent_external_id: External ID of the leaving agent
            meeting_id: Meeting UUID

        Raises:
            ValueError: If parameters are invalid
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found, agent not participant, or agent is host
            MeetingStateError: If meeting is ended
        """
        # Input validation
        if not agent_external_id or not isinstance(agent_external_id, str):
            raise ValueError("agent_external_id must be a non-empty string")
        if len(agent_external_id.strip()) == 0:
            raise ValueError("agent_external_id cannot be empty or whitespace")
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        agent_external_id = agent_external_id.strip()

        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # Validate meeting exists
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

        # Validate meeting state
        if meeting.status == MeetingStatus.ENDED:
            raise MeetingStateError(f"Meeting {meeting_id} is already ended")
        if meeting.status not in [MeetingStatus.CREATED, MeetingStatus.READY, MeetingStatus.ACTIVE]:
            raise MeetingStateError(
                f"Meeting {meeting_id} cannot be left from status: {meeting.status}"
            )

        # Check if agent is host (hosts cannot leave)
        if meeting.host_id == agent.id:
            raise MeetingError(f"Host '{agent_external_id}' cannot leave meeting {meeting_id}")

        # Check if agent is a participant
        participant = await self._meeting_repo.get_participant(meeting_id, agent.id)
        if not participant:
            raise MeetingError(
                f"Agent '{agent_external_id}' is not a participant in meeting {meeting_id}"
            )

        # If it's currently their turn, wait for turn to complete or timeout
        if meeting.current_speaker_id == agent.id and meeting.status == MeetingStatus.ACTIVE:
            # Cancel their timeout and advance to next speaker
            await self._timeout_manager.cancel_timeout(meeting_id)

            # Get all participants and find next speaker
            participants = await self._meeting_repo.get_participants(meeting_id)
            attending_participants = [
                p
                for p in participants
                if p.status == ParticipantStatus.ATTENDING and p.agent_id != agent.id
            ]

            if attending_participants:
                # Select next speaker (first in remaining list)
                next_speaker = attending_participants[0]

                # Update current speaker
                await self._meeting_repo.set_current_speaker(
                    meeting_id=meeting_id,
                    agent_id=next_speaker.agent_id,
                    turn_started=True,
                )

                # Start timeout for next speaker
                await self._timeout_manager.start_turn_timeout(
                    meeting_id=meeting_id,
                    current_speaker_id=next_speaker.agent_id,
                    turn_duration=meeting.turn_duration,
                )

                logger.info(
                    f"Agent {agent_external_id} left meeting {meeting_id} during their turn. "
                    f"Turn passed to {next_speaker.agent_id}"
                )
            else:
                logger.warning(
                    f"Agent {agent_external_id} left meeting {meeting_id} but no other participants remain"
                )

        # Update participant status to LEFT
        await self._meeting_repo.update_participant_status(
            participant_id=participant.id,
            status=ParticipantStatus.LEFT,
        )

        # Emit participant left event
        await self._event_handler.emit_participant_left(
            meeting_id=meeting_id,
            agent_id=agent.id,
        )

        logger.info(f"Agent {agent_external_id} left meeting {meeting_id}")

    async def get_meeting_status(self, meeting_id: UUID) -> Optional[Dict]:
        """Get meeting status information.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Dict with meeting status info, or None if meeting not found

        Raises:
            ValueError: If meeting_id is invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            return None

        participants = await self._meeting_repo.get_participants(meeting_id)

        # Get current speaker info
        current_speaker = None
        if meeting.current_speaker_id:
            for p in participants:
                if p.agent_id == meeting.current_speaker_id:
                    current_speaker = {
                        "agent_id": str(p.agent_id),
                        "join_order": p.join_order,
                        "status": p.status.value,
                    }
                    break

        # Build participant list
        participant_list = [
            {
                "agent_id": str(p.agent_id),
                "join_order": p.join_order,
                "status": p.status.value,
                "joined_at": p.joined_at.isoformat() if p.joined_at else None,
                "left_at": p.left_at.isoformat() if p.left_at else None,
            }
            for p in participants
        ]

        return {
            "meeting_id": str(meeting_id),
            "host_id": str(meeting.host_id),
            "status": meeting.status.value,
            "turn_duration": meeting.turn_duration,
            "current_speaker": current_speaker,
            "created_at": meeting.created_at.isoformat(),
            "started_at": meeting.started_at.isoformat() if meeting.started_at else None,
            "ended_at": meeting.ended_at.isoformat() if meeting.ended_at else None,
            "participants": participant_list,
        }

    async def get_meeting_history(self, meeting_id: UUID) -> List[Dict]:
        """Get meeting message history.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of messages in chronological order

        Raises:
            ValueError: If meeting_id is invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        # Get all messages for this meeting
        # Note: This is a simplified implementation. In a real system,
        # you'd want to add a method to MessageRepository to get messages by meeting_id
        # For now, we'll use a direct query

        query = """
            SELECT id, sender_id, message_type, content, created_at, metadata
            FROM messages
            WHERE meeting_id = $1
            ORDER BY created_at ASC
        """
        results = await self._message_repo._execute(query, [str(meeting_id)])
        rows = results.result()

        messages = []
        for row in rows:
            messages.append(
                {
                    "id": str(row["id"]),
                    "sender_id": str(row["sender_id"]) if row["sender_id"] else None,
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "created_at": row["created_at"].isoformat(),
                    "metadata": row["metadata"],
                }
            )

        return messages

    async def get_meeting_details(
        self,
        meeting_id: str,
    ) -> Dict[str, Any]:
        """Get detailed meeting information including participants and statistics.

        Args:
            meeting_id: Meeting ID (UUID as string)

        Returns:
            Dictionary with meeting details and current status
        """
        try:
            meeting_uuid = UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        except (ValueError, TypeError):
            raise ValueError(f"meeting_id is not a valid UUID: {meeting_id}")

        details = await self._meeting_repo.get_meeting_details(meeting_uuid)

        if not details:
            raise ValueError(f"Meeting not found: {meeting_id}")

        return {
            "meeting_id": str(details["id"]),
            "host": {
                "id": str(details["host_id"]),
                "name": details["host_name"],
            },
            "status": details["status"],
            "current_speaker": (
                {
                    "id": (
                        str(details["current_speaker_id"])
                        if details["current_speaker_id"]
                        else None
                    ),
                    "name": details["current_speaker_name"],
                }
                if details["current_speaker_id"]
                else None
            ),
            "turn_duration_seconds": (
                float(details["turn_duration"].total_seconds())
                if details["turn_duration"]
                else None
            ),
            "turn_started_at": details["turn_started_at"],
            "created_at": details["created_at"],
            "started_at": details["started_at"],
            "ended_at": details["ended_at"],
            "participant_count": details["participant_count"],
            "attending_count": details["attending_count"],
            "message_count": details["message_count"],
        }

    async def get_participant_history(
        self,
        meeting_id: str,
    ) -> List[Dict[str, Any]]:
        """Get full participant history for a meeting.

        Args:
            meeting_id: Meeting ID (UUID as string)

        Returns:
            List of participants with detailed information
        """
        try:
            meeting_uuid = UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        except (ValueError, TypeError):
            raise ValueError(f"meeting_id is not a valid UUID: {meeting_id}")

        participants = await self._meeting_repo.get_participant_history(meeting_uuid)

        result = []
        for p in participants:
            result.append(
                {
                    "participant_id": str(p["id"]),
                    "agent_id": str(p["agent_id"]),
                    "agent_name": p["agent_name"],
                    "status": p["status"],
                    "join_order": p["join_order"],
                    "is_locked": p["is_locked"],
                    "joined_at": p["joined_at"],
                    "left_at": p["left_at"],
                }
            )

        return result

    async def get_meeting_statistics(
        self,
        agent_id: str,
    ) -> Dict[str, Any]:
        """Get meeting statistics for an agent (as organizer or participant).

        Args:
            agent_id: Agent external ID

        Returns:
            Dictionary with meeting statistics
        """
        agent = await self._agent_repo.get_by_external_id(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")

        stats = await self._meeting_repo.get_meeting_statistics(agent.id)

        return {
            "agent_id": agent_id,
            "hosted_meetings": stats["hosted_meetings"],
            "participated_meetings": stats["participated_meetings"],
            "active_hosted": stats["active_hosted"],
            "total_messages_sent": stats["total_messages_sent"],
            "meetings_spoke_in": stats["meetings_spoke_in"],
            "avg_meeting_duration_seconds": stats["avg_meeting_duration_seconds"],
        }

    async def get_participation_analysis(
        self,
        meeting_id: str,
    ) -> Dict[str, Any]:
        """Get detailed participation analysis for a meeting.

        Provides insights into each participant's activity levels, speaking patterns,
        and engagement metrics.

        Args:
            meeting_id: Meeting ID (UUID as string)

        Returns:
            Dictionary with participation analysis including:
                - total_participants: Total number of participants
                - active_participants: Number who sent messages
                - participation_rate: Percentage of active participants
                - by_participant: Individual participant statistics
                - most_active: Most active participant
                - least_active: Least active participant (among active)

        Raises:
            ValueError: If meeting_id is invalid or meeting not found
        """
        try:
            meeting_uuid = UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        except (ValueError, TypeError):
            raise ValueError(f"meeting_id is not a valid UUID: {meeting_id}")

        analysis = await self._meeting_repo.get_participation_analysis(meeting_uuid)

        return analysis

    async def get_meeting_timeline(
        self,
        meeting_id: str,
    ) -> Dict[str, Any]:
        """Get chronological timeline of all meeting events.

        Returns a complete timeline of messages and meeting events in chronological
        order, useful for replaying or analyzing meeting flow.

        Args:
            meeting_id: Meeting ID (UUID as string)

        Returns:
            Dictionary with timeline information including:
                - meeting_id: Meeting UUID
                - started_at: Meeting start timestamp
                - ended_at: Meeting end timestamp (if ended)
                - duration_seconds: Total duration (if ended)
                - timeline: Chronologically ordered list of events

        Raises:
            ValueError: If meeting_id is invalid
        """
        try:
            meeting_uuid = UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        except (ValueError, TypeError):
            raise ValueError(f"meeting_id is not a valid UUID: {meeting_id}")

        timeline = await self._meeting_repo.get_meeting_timeline(meeting_uuid)

        return timeline

    async def get_turn_statistics(
        self,
        meeting_id: str,
    ) -> Dict[str, Any]:
        """Get turn-taking statistics for a meeting.

        Analyzes turn patterns, speaking order adherence, and individual
        participant turn-taking behavior.

        Args:
            meeting_id: Meeting ID (UUID as string)

        Returns:
            Dictionary with turn statistics including:
                - total_turns: Total number of speaking turns
                - avg_messages_per_turn: Average messages per turn
                - turn_changes: Number of speaker changes
                - participants_turn_stats: Per-participant turn statistics

        Raises:
            ValueError: If meeting_id is invalid
        """
        try:
            meeting_uuid = UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        except (ValueError, TypeError):
            raise ValueError(f"meeting_id is not a valid UUID: {meeting_id}")

        stats = await self._meeting_repo.get_turn_statistics(meeting_uuid)

        return stats

        """Get meeting message history.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of messages in chronological order

        Raises:
            ValueError: If meeting_id is invalid
        """
        # Input validation
        if not isinstance(meeting_id, UUID):
            raise ValueError("meeting_id must be a valid UUID")

        # Get all messages for this meeting
        # Note: This is a simplified implementation. In a real system,
        # you'd want to add a method to MessageRepository to get messages by meeting_id
        # For now, we'll use a direct query

        query = """
            SELECT id, sender_id, message_type, content, created_at, metadata
            FROM messages
            WHERE meeting_id = $1
            ORDER BY created_at ASC
        """
        results = await self._message_repo._execute(query, [str(meeting_id)])
        rows = results.result()

        messages = []
        for row in rows:
            messages.append(
                {
                    "id": str(row["id"]),
                    "sender_id": str(row["sender_id"]) if row["sender_id"] else None,
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "created_at": row["created_at"].isoformat(),
                    "metadata": row["metadata"],
                }
            )

        return messages
