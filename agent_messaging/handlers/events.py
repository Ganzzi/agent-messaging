"""Event system for meeting lifecycle events."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID

from ..models import (
    MeetingEventType,
    MeetingStartedEventData,
    MeetingEndedEventData,
    TurnChangedEventData,
    ParticipantJoinedEventData,
    ParticipantLeftEventData,
    TimeoutOccurredEventData,
    MessagePostedEventData,
    ParticipantStatusChangedEventData,
    ErrorOccurredEventData,
)

logger = logging.getLogger(__name__)

# Union type for all event data types
MeetingEventData = Union[
    MeetingStartedEventData,
    MeetingEndedEventData,
    TurnChangedEventData,
    ParticipantJoinedEventData,
    ParticipantLeftEventData,
    TimeoutOccurredEventData,
    MessagePostedEventData,
    ParticipantStatusChangedEventData,
    ErrorOccurredEventData,
]


class MeetingEvent:
    """Container for a meeting event with type-safe data."""

    def __init__(
        self,
        meeting_id: UUID,
        event_type: MeetingEventType,
        data: MeetingEventData,
        timestamp: datetime = None,
    ):
        """Initialize meeting event.

        Args:
            meeting_id: Meeting UUID
            event_type: Type of event
            data: Type-safe event data
            timestamp: Event timestamp (defaults to now)
        """
        self.meeting_id = meeting_id
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now()


class MeetingEventHandler:
    """Handles meeting events and notifications with type-safe event data."""

    def __init__(self):
        """Initialize the event handler."""
        # event_type -> list of handler functions
        self._handlers: Dict[MeetingEventType, List[Callable[[MeetingEvent], None]]] = {}

    def register_handler(
        self,
        event_type: MeetingEventType,
        handler: Callable[[MeetingEvent], None],
    ) -> None:
        """Register an event handler.

        Args:
            event_type: Type of meeting event to handle
            handler: Async function to call when event occurs

        Example:
            async def on_meeting_started(event: MeetingEvent):
                data: MeetingStartedEventData = event.data
                print(f"Meeting {event.meeting_id} started by {data.host_id}")
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    def unregister_handler(
        self,
        event_type: MeetingEventType,
        handler: Callable[[MeetingEvent], None],
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
        data: MeetingEventData,
    ) -> None:
        """Emit a meeting event to all registered handlers.

        Args:
            meeting_id: Meeting UUID
            event_type: Type of event
            data: Type-safe event data
        """
        event = MeetingEvent(
            meeting_id=meeting_id,
            event_type=event_type,
            data=data,
        )

        # Call all handlers for this event type
        if event_type in self._handlers:
            tasks = []
            for handler in self._handlers[event_type]:
                try:
                    # Create task for each handler to run concurrently
                    task = asyncio.create_task(handler(event))
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
        """Emit meeting started event with type-safe data."""
        data = MeetingStartedEventData(
            host_id=host_id,
            participant_ids=participant_ids,
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.MEETING_STARTED,
            data=data,
        )

    async def emit_meeting_ended(
        self,
        meeting_id: UUID,
        host_id: UUID,
    ) -> None:
        """Emit meeting ended event with type-safe data."""
        data = MeetingEndedEventData(host_id=host_id)
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.MEETING_ENDED,
            data=data,
        )

    async def emit_turn_changed(
        self,
        meeting_id: UUID,
        previous_speaker_id: UUID = None,
        current_speaker_id: UUID = None,
    ) -> None:
        """Emit turn changed event with type-safe data."""
        data = TurnChangedEventData(
            previous_speaker_id=previous_speaker_id,
            current_speaker_id=current_speaker_id,
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.TURN_CHANGED,
            data=data,
        )

    async def emit_participant_joined(
        self,
        meeting_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Emit participant joined event with type-safe data."""
        data = ParticipantJoinedEventData(agent_id=agent_id)
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.PARTICIPANT_JOINED,
            data=data,
        )

    async def emit_participant_left(
        self,
        meeting_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Emit participant left event with type-safe data."""
        data = ParticipantLeftEventData(agent_id=agent_id)
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.PARTICIPANT_LEFT,
            data=data,
        )

    async def emit_timeout_occurred(
        self,
        meeting_id: UUID,
        timed_out_agent_id: UUID,
        next_speaker_id: UUID,
    ) -> None:
        """Emit timeout occurred event with type-safe data."""
        data = TimeoutOccurredEventData(
            timed_out_agent_id=timed_out_agent_id,
            next_speaker_id=next_speaker_id,
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.TIMEOUT_OCCURRED,
            data=data,
        )

    async def emit_message_posted(
        self,
        meeting_id: UUID,
        message_id: UUID,
        sender_id: UUID,
        content: Dict[str, Any],
    ) -> None:
        """Emit message posted event with type-safe data."""
        data = MessagePostedEventData(
            message_id=message_id,
            sender_id=sender_id,
            content=content,
            timestamp=datetime.now(),
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.MESSAGE_POSTED,
            data=data,
        )

    async def emit_participant_status_changed(
        self,
        meeting_id: UUID,
        agent_id: UUID,
        previous_status: str,
        current_status: str,
    ) -> None:
        """Emit participant status changed event with type-safe data."""
        data = ParticipantStatusChangedEventData(
            agent_id=agent_id,
            previous_status=previous_status,
            current_status=current_status,
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.PARTICIPANT_STATUS_CHANGED,
            data=data,
        )

    async def emit_error_occurred(
        self,
        meeting_id: UUID,
        error_type: str,
        error_message: str,
        affected_agent_id: Optional[UUID] = None,
    ) -> None:
        """Emit error occurred event with type-safe data."""
        data = ErrorOccurredEventData(
            error_type=error_type,
            error_message=error_message,
            affected_agent_id=affected_agent_id,
            timestamp=datetime.now(),
        )
        await self.emit_event(
            meeting_id=meeting_id,
            event_type=MeetingEventType.ERROR_OCCURRED,
            data=data,
        )
