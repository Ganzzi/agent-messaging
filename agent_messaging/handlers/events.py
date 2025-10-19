"""Event system for meeting lifecycle events."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List
from uuid import UUID

from ..models import MeetingEventPayload, MeetingEventType

logger = logging.getLogger(__name__)


class MeetingEventHandler:
    """Handles meeting events and notifications."""

    def __init__(self):
        """Initialize the event handler."""
        # event_type -> list of handler functions
        self._handlers: Dict[MeetingEventType, List[Callable]] = {}

    def register_handler(
        self,
        event_type: MeetingEventType,
        handler: Callable[[MeetingEventPayload], None],
    ) -> None:
        """Register an event handler.

        Args:
            event_type: Type of meeting event to handle
            handler: Async function to call when event occurs
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    def unregister_handler(
        self,
        event_type: MeetingEventType,
        handler: Callable[[MeetingEventPayload], None],
    ) -> None:
        """Unregister an event handler.

        Args:
            event_type: Type of meeting event
            handler: Handler function to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Unregistered handler for event type: {event_type}")
            except ValueError:
                logger.warning(f"Handler not found for event type: {event_type}")

    async def emit_event(
        self,
        meeting_id: UUID,
        event_type: MeetingEventType,
        data: Dict[str, Any] = None,
    ) -> None:
        """Emit a meeting event to all registered handlers.

        Args:
            meeting_id: Meeting UUID
            event_type: Type of event
            data: Additional event data
        """
        if data is None:
            data = {}

        payload = MeetingEventPayload(
            meeting_id=meeting_id,
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
        )

        # Call all handlers for this event type
        if event_type in self._handlers:
            tasks = []
            for handler in self._handlers[event_type]:
                try:
                    # Create task for each handler to run concurrently
                    task = asyncio.create_task(handler(payload))
                    tasks.append(task)
                except Exception as e:
                    logger.error(f"Error creating task for event handler: {e}")

            # Wait for all handlers to complete
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error in event handlers for {event_type}: {e}")

        logger.debug(f"Emitted event: {event_type} for meeting {meeting_id}")

    async def emit_meeting_started(
        self,
        meeting_id: UUID,
        host_id: UUID,
        participant_ids: List[UUID],
    ) -> None:
        """Emit meeting started event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.MEETING_STARTED,
            data={
                "host_id": str(host_id),
                "participant_ids": [str(pid) for pid in participant_ids],
            },
        )

    async def emit_meeting_ended(
        self,
        meeting_id: UUID,
        host_id: UUID,
    ) -> None:
        """Emit meeting ended event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.MEETING_ENDED,
            data={
                "host_id": str(host_id),
            },
        )

    async def emit_turn_changed(
        self,
        meeting_id: UUID,
        previous_speaker_id: UUID = None,
        current_speaker_id: UUID = None,
    ) -> None:
        """Emit turn changed event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.TURN_CHANGED,
            data={
                "previous_speaker_id": str(previous_speaker_id) if previous_speaker_id else None,
                "current_speaker_id": str(current_speaker_id) if current_speaker_id else None,
            },
        )

    async def emit_participant_joined(
        self,
        meeting_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Emit participant joined event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.PARTICIPANT_JOINED,
            data={
                "agent_id": str(agent_id),
            },
        )

    async def emit_participant_left(
        self,
        meeting_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Emit participant left event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.PARTICIPANT_LEFT,
            data={
                "agent_id": str(agent_id),
            },
        )

    async def emit_timeout_occurred(
        self,
        meeting_id: UUID,
        timed_out_agent_id: UUID,
        next_speaker_id: UUID,
    ) -> None:
        """Emit timeout occurred event."""
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.TIMEOUT_OCCURRED,
            data={
                "timed_out_agent_id": str(timed_out_agent_id),
                "next_speaker_id": str(next_speaker_id),
            },
        )
