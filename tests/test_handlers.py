"""Unit tests for handler modules (registry and events)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime

from agent_messaging.handlers.registry import HandlerRegistry
from agent_messaging.handlers.events import MeetingEventHandler
from agent_messaging.models import MessageContext, MeetingEventType, MeetingEventPayload
from agent_messaging.exceptions import NoHandlerRegisteredError, HandlerTimeoutError


class TestHandlerRegistry:
    """Test cases for HandlerRegistry class."""

    @pytest.fixture
    def registry(self):
        """HandlerRegistry instance."""
        return HandlerRegistry(handler_timeout=1.0)  # Short timeout for testing

    @pytest.fixture
    def sample_context(self):
        """Sample message context."""
        return MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
            session_id=None,
        )

    def test_initialization(self, registry):
        """Test registry initialization."""
        assert registry._handlers == {}
        assert registry._handler_timeout == 1.0
        assert registry._background_tasks == set()

    def test_register_decorator(self, registry):
        """Test handler registration decorator."""
        @registry.register("alice")
        async def alice_handler(message, context):
            return {"response": "Hello from Alice"}

        assert "alice" in registry._handlers
        assert registry._handlers["alice"] == alice_handler

    def test_get_handler_existing(self, registry):
        """Test getting existing handler."""
        async def handler(message, context):
            return None

        registry._handlers["alice"] = handler

        result = registry.get_handler("alice")
        assert result == handler

    def test_get_handler_nonexistent(self, registry):
        """Test getting non-existent handler."""
        result = registry.get_handler("nonexistent")
        assert result is None

    def test_has_handler_true(self, registry):
        """Test checking if handler exists."""
        registry._handlers["alice"] = lambda: None
        assert registry.has_handler("alice") is True

    def test_has_handler_false(self, registry):
        """Test checking if handler doesn't exist."""
        assert registry.has_handler("nonexistent") is False

    @pytest.mark.asyncio
    async def test_invoke_handler_success(self, registry, sample_context):
        """Test successful handler invocation."""
        async def handler(message, context):
            return {"response": f"Processed: {message['text']}"}

        registry._handlers["alice"] = handler

        result = await registry.invoke_handler("alice", {"text": "Hello"}, sample_context)

        assert result == {"response": "Processed: Hello"}

    @pytest.mark.asyncio
    async def test_invoke_handler_no_handler(self, registry, sample_context):
        """Test invoking handler when none registered."""
        with pytest.raises(NoHandlerRegisteredError):
            await registry.invoke_handler("nonexistent", {"text": "Hello"}, sample_context)


class TestMeetingEventHandler:
    """Test cases for MeetingEventHandler class."""

    @pytest.fixture
    def event_handler(self):
        """MeetingEventHandler instance."""
        return MeetingEventHandler()

    def test_initialization(self, event_handler):
        """Test event handler initialization."""
        assert event_handler._handlers == {}

    def test_register_handler(self, event_handler):
        """Test registering event handler."""
        async def handler(payload):
            pass

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, handler)

        assert MeetingEventType.MEETING_STARTED in event_handler._handlers
        assert handler in event_handler._handlers[MeetingEventType.MEETING_STARTED]

    @pytest.mark.asyncio
    async def test_emit_event_no_handlers(self, event_handler):
        """Test emitting event with no handlers."""
        meeting_id = uuid4()

        # Should not raise error
        await event_handler.emit_event(meeting_id, MeetingEventType.MEETING_STARTED)

    @pytest.mark.asyncio
    async def test_emit_event_with_handlers(self, event_handler):
        """Test emitting event with registered handlers."""
        meeting_id = uuid4()
        called = []

        async def handler1(payload):
            called.append(("handler1", payload))

        async def handler2(payload):
            called.append(("handler2", payload))

        event_handler.register_handler(MeetingEventType.MEETING_STARTED, handler1)
        event_handler.register_handler(MeetingEventType.MEETING_STARTED, handler2)

        await event_handler.emit_event(
            meeting_id,
            MeetingEventType.MEETING_STARTED,
            {"host_id": "alice"}
        )

        assert len(called) == 2
        assert called[0][0] == "handler1"
        assert called[1][0] == "handler2"

        # Check payload
        payload = called[0][1]
        assert isinstance(payload, MeetingEventPayload)
        assert payload.meeting_id == meeting_id
        assert payload.event_type == MeetingEventType.MEETING_STARTED
        assert payload.data == {"host_id": "alice"}
