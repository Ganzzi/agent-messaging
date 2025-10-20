"""Unit tests for MeetingEventHandler."""

import pytest
from uuid import uuid4

from agent_messaging.handlers.events import MeetingEventHandler
from agent_messaging.models import MeetingEventType


@pytest.fixture
def event_handler():
    """MeetingEventHandler instance for testing."""
    return MeetingEventHandler()


class TestMeetingEventHandler:
    """Test cases for MeetingEventHandler."""

    def test_register_handler(self, event_handler):
        """Test registering event handler."""

        async def test_handler(event):
            pass

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, test_handler)

        # Verify handler was registered
        assert MeetingEventType.MEETING_STARTED in event_handler._handlers
        assert len(event_handler._handlers[MeetingEventType.MEETING_STARTED]) == 1

    @pytest.mark.asyncio
    async def test_emit_event(self, event_handler):
        """Test emitting event."""
        events_received = []

        async def test_handler(event_data):
            events_received.append(event_data)

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, test_handler)

        # Emit event
        await event_handler.emit_event(
            uuid4(), MeetingEventType.MEETING_STARTED, {"meeting_id": "123"}
        )

        # Verify handler was called
        assert len(events_received) == 1
        assert events_received[0].data["meeting_id"] == "123"

    @pytest.mark.asyncio
    async def test_emit_meeting_started(self, event_handler):
        """Test emitting meeting started event."""
        events_received = []

        async def handler(event):
            events_received.append(event)

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, handler)

        # Emit meeting started
        await event_handler.emit_meeting_started(uuid4(), uuid4(), [uuid4(), uuid4()])

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0].event_type == MeetingEventType.MEETING_STARTED

    @pytest.mark.asyncio
    async def test_emit_turn_changed(self, event_handler):
        """Test emitting turn changed event."""
        events_received = []

        async def handler(event):
            events_received.append(event)

        event_handler.register_handler(MeetingEventType.TURN_CHANGED, handler)

        # Emit turn changed
        await event_handler.emit_turn_changed(uuid4(), uuid4(), uuid4())

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0].event_type == MeetingEventType.TURN_CHANGED
