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
from ..exceptions import AgentNotFoundError, MeetingError, NotYourTurnError, MeetingNotActiveError
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
            AgentNotFoundError: If organizer or any participant not found
        """
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
        """
        return await self._meeting_repo.get_by_id(meeting_id)

    async def get_participants(self, meeting_id: UUID) -> List[MeetingParticipant]:
        """Get all participants for a meeting.

        Args:
            meeting_id: Meeting UUID

        Returns:
            List of meeting participants
        """
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
        """
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
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found or agent not invited
        """
        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # Validate meeting exists
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

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
            AgentNotFoundError: If host not found
            MeetingError: If meeting not found, not host, wrong status, or participants not ready
        """
        # Validate host exists
        host = await self._agent_repo.get_by_external_id(host_external_id)
        if not host:
            raise AgentNotFoundError(f"Host agent '{host_external_id}' not found")

        # Validate meeting exists and host is correct
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

        if meeting.host_id != host.id:
            raise MeetingError(
                f"Agent '{host_external_id}' is not the host of meeting {meeting_id}"
            )

        # Check meeting status
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

    async def speak(
        self,
        agent_external_id: str,
        meeting_id: UUID,
        message: T,
    ) -> UUID:
        """Speak in a meeting (requires having the turn).

        Args:
            agent_external_id: External ID of the speaking agent
            meeting_id: Meeting UUID
            message: Message content to speak

        Returns:
            Message ID of the spoken message

        Raises:
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found or agent not a participant
            MeetingNotActiveError: If meeting is not active
            NotYourTurnError: If it's not the agent's turn
        """
        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # Validate meeting exists
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

        # Check if it's the agent's turn
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
            raise MeetingError(f"Agent {agent_external_id} not found in attending participants")

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
            AgentNotFoundError: If host not found
            MeetingError: If meeting not found or not host
        """
        # Validate host exists
        host = await self._agent_repo.get_by_external_id(host_external_id)
        if not host:
            raise AgentNotFoundError(f"Host agent '{host_external_id}' not found")

        # Validate meeting exists and host is correct
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

        if meeting.host_id != host.id:
            raise MeetingError(
                f"Agent '{host_external_id}' is not the host of meeting {meeting_id}"
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
            AgentNotFoundError: If agent not found
            MeetingError: If meeting not found, agent not participant, or agent is host
        """
        # Validate agent exists
        agent = await self._agent_repo.get_by_external_id(agent_external_id)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_external_id}' not found")

        # Validate meeting exists
        meeting = await self._meeting_repo.get_by_id(meeting_id)
        if not meeting:
            raise MeetingError(f"Meeting {meeting_id} not found")

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
        """
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
            "current_speaker": current_speaker,
            "turn_duration": meeting.turn_duration,
            "turn_started_at": (
                meeting.turn_started_at.isoformat() if meeting.turn_started_at else None
            ),
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
        """
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
