"""Timeout management utilities for meetings and conversations."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from ..database.repositories.meeting import MeetingRepository
from ..database.repositories.message import MessageRepository
from ..models import Meeting, MeetingStatus, MessageType, ParticipantStatus

logger = logging.getLogger(__name__)


class MeetingTimeoutManager:
    """Manages timeouts for meeting turns.

    Monitors active meetings and automatically advances turns when
    speakers exceed their allocated time.
    """

    def __init__(
        self,
        meeting_repo: MeetingRepository,
        message_repo: MessageRepository,
    ):
        """Initialize the timeout manager.

        Args:
            meeting_repo: Repository for meeting operations
            message_repo: Repository for message operations
        """
        self._meeting_repo = meeting_repo
        self._message_repo = message_repo

        # Track active timeout tasks: meeting_id -> asyncio.Task
        self._timeout_tasks: Dict[UUID, asyncio.Task] = {}

        # Check interval for timeout monitoring
        self._check_interval = 5.0  # seconds

    async def start_monitoring(self) -> None:
        """Start the timeout monitoring loop."""
        logger.info("Starting meeting timeout monitoring")
        while True:
            try:
                await self._check_timeouts()
                await asyncio.sleep(self._check_interval)
            except Exception as e:
                logger.error(f"Error in timeout monitoring: {e}")
                await asyncio.sleep(self._check_interval)

    async def _check_timeouts(self) -> None:
        """Check all active meetings for turn timeouts."""
        # This is a simplified implementation
        # In a real system, you'd want to query the database for active meetings
        # with turn timeouts, or maintain an in-memory cache

        # For now, we'll rely on the timeout tasks being managed per meeting
        # The actual timeout logic is handled in the individual timeout tasks
        pass

    async def start_turn_timeout(
        self,
        meeting_id: UUID,
        current_speaker_id: UUID,
        turn_duration: Optional[float],
    ) -> None:
        """Start timeout monitoring for a speaker's turn.

        Args:
            meeting_id: Meeting UUID
            current_speaker_id: Current speaker agent UUID
            turn_duration: Turn duration in seconds (None for no timeout)
        """
        # Cancel any existing timeout for this meeting
        if meeting_id in self._timeout_tasks:
            self._timeout_tasks[meeting_id].cancel()
            del self._timeout_tasks[meeting_id]

        # If no turn duration, don't start timeout
        if turn_duration is None or turn_duration <= 0:
            return

        # Create timeout task
        task = asyncio.create_task(
            self._monitor_turn_timeout(meeting_id, current_speaker_id, turn_duration)
        )
        self._timeout_tasks[meeting_id] = task

        logger.debug(
            f"Started turn timeout monitoring for meeting {meeting_id}, "
            f"speaker {current_speaker_id}, duration {turn_duration}s"
        )

    async def _monitor_turn_timeout(
        self,
        meeting_id: UUID,
        current_speaker_id: UUID,
        turn_duration: float,
    ) -> None:
        """Monitor a single turn for timeout.

        Args:
            meeting_id: Meeting UUID
            current_speaker_id: Current speaker agent UUID
            turn_duration: Turn duration in seconds
        """
        try:
            await asyncio.sleep(turn_duration)

            # Check if meeting still exists and speaker hasn't changed
            meeting = await self._meeting_repo.get_by_id(meeting_id)
            if not meeting:
                logger.warning(f"Meeting {meeting_id} not found during timeout check")
                return

            if meeting.status != MeetingStatus.ACTIVE:
                logger.debug(f"Meeting {meeting_id} is no longer active")
                return

            if meeting.current_speaker_id != current_speaker_id:
                logger.debug(f"Speaker changed for meeting {meeting_id}, timeout cancelled")
                return

            # Timeout occurred - advance to next speaker
            await self._handle_turn_timeout(meeting_id, current_speaker_id)

        except asyncio.CancelledError:
            # Timeout was cancelled (speaker spoke or meeting ended)
            logger.debug(f"Turn timeout cancelled for meeting {meeting_id}")
            raise
        except Exception as e:
            logger.error(f"Error monitoring turn timeout for meeting {meeting_id}: {e}")

    async def _handle_turn_timeout(
        self,
        meeting_id: UUID,
        timed_out_speaker_id: UUID,
    ) -> None:
        """Handle a turn timeout by advancing to next speaker.

        Args:
            meeting_id: Meeting UUID
            timed_out_speaker_id: Agent who timed out
        """
        try:
            # Get meeting and participants
            meeting = await self._meeting_repo.get_by_id(meeting_id)
            if not meeting:
                return

            participants = await self._meeting_repo.get_participants(meeting_id)
            attending_participants = [
                p for p in participants if p.status == ParticipantStatus.ATTENDING
            ]

            if not attending_participants:
                logger.warning(f"No attending participants in meeting {meeting_id}")
                return

            # Find current speaker index
            current_index = None
            for i, p in enumerate(attending_participants):
                if p.agent_id == timed_out_speaker_id:
                    current_index = i
                    break

            if current_index is None:
                logger.warning(
                    f"Timed out speaker {timed_out_speaker_id} not in attending participants"
                )
                return

            # Select next speaker (round-robin)
            next_index = (current_index + 1) % len(attending_participants)
            next_speaker = attending_participants[next_index]

            # Generate timeout message
            timeout_content = {
                "type": "timeout",
                "timed_out_agent": str(timed_out_speaker_id),
                "next_speaker": str(next_speaker.agent_id),
                "message": f"Agent {timed_out_speaker_id} timed out. Turn passed to agent {next_speaker.agent_id}",
            }

            # Store timeout message (sender is None/system)
            await self._message_repo.create(
                session_id=None,
                sender_id=None,  # System message
                recipient_id=None,
                meeting_id=meeting_id,
                message_type=MessageType.TIMEOUT,
                content=timeout_content,
            )

            # Update current speaker
            await self._meeting_repo.set_current_speaker(
                meeting_id=meeting_id,
                agent_id=next_speaker.agent_id,
                turn_started=True,
            )

            # Start timeout for next speaker
            await self.start_turn_timeout(
                meeting_id=meeting_id,
                current_speaker_id=next_speaker.agent_id,
                turn_duration=meeting.turn_duration,
            )

            logger.info(
                f"Turn timeout in meeting {meeting_id}: agent {timed_out_speaker_id} -> {next_speaker.agent_id}"
            )

        except Exception as e:
            logger.error(f"Error handling turn timeout for meeting {meeting_id}: {e}")

    async def cancel_timeout(self, meeting_id: UUID) -> None:
        """Cancel timeout monitoring for a meeting.

        Args:
            meeting_id: Meeting UUID
        """
        if meeting_id in self._timeout_tasks:
            self._timeout_tasks[meeting_id].cancel()
            del self._timeout_tasks[meeting_id]
            logger.debug(f"Cancelled timeout for meeting {meeting_id}")

    async def shutdown(self) -> None:
        """Shutdown the timeout manager and cancel all tasks."""
        logger.info("Shutting down meeting timeout manager")

        # Cancel all timeout tasks
        for task in self._timeout_tasks.values():
            task.cancel()

        self._timeout_tasks.clear()

        # Wait for tasks to complete
        await asyncio.gather(*self._timeout_tasks.values(), return_exceptions=True)
