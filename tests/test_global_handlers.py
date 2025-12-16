"""Tests for global handler system."""

import pytest
from uuid import uuid4
from datetime import datetime

from agent_messaging.handlers import (
    HandlerContext,
    MessageContext,
    register_one_way_handler,
    register_conversation_handler,
    register_meeting_handler,
    register_system_handler,
    has_handler,
    get_handler,
    invoke_handler,
    invoke_handler_async,
    clear_handlers,
)
from agent_messaging.exceptions import NoHandlerRegisteredError


@pytest.fixture(autouse=True)
def clean_handlers():
    """Clean handlers before and after each test."""
    clear_handlers()
    yield
    clear_handlers()


class TestHandlerContextEnum:
    """Test HandlerContext enum values."""

    def test_handler_context_values(self):
        """Test that HandlerContext has the expected values."""
        assert HandlerContext.ONE_WAY.value == "one_way"
        assert HandlerContext.CONVERSATION.value == "conversation"
        assert HandlerContext.MEETING.value == "meeting"
        assert HandlerContext.SYSTEM.value == "system"

    def test_handler_context_enum_count(self):
        """Test that HandlerContext has exactly 4 values."""
        assert len(HandlerContext) == 4


class TestGlobalHandlerRegistration:
    """Test global handler registration functions."""

    def test_register_one_way_handler(self):
        """Test registering a one-way handler."""

        async def handler(msg, ctx):
            return None

        register_one_way_handler(handler)
        assert has_handler(HandlerContext.ONE_WAY)

    def test_register_conversation_handler(self):
        """Test registering a conversation handler."""

        async def handler(msg, ctx):
            return "response"

        register_conversation_handler(handler)
        assert has_handler(HandlerContext.CONVERSATION)

    def test_register_meeting_handler(self):
        """Test registering a meeting handler."""

        async def handler(msg, ctx):
            return "contribution"

        register_meeting_handler(handler)
        assert has_handler(HandlerContext.MEETING)

    def test_register_system_handler(self):
        """Test registering a system handler."""

        async def handler(msg, ctx):
            return None

        register_system_handler(handler)
        assert has_handler(HandlerContext.SYSTEM)

    def test_register_as_decorator(self):
        """Test using register function as decorator."""

        @register_one_way_handler
        async def handler(msg, ctx):
            return None

        assert has_handler(HandlerContext.ONE_WAY)
        assert get_handler(HandlerContext.ONE_WAY) == handler

    def test_clear_handlers(self):
        """Test clearing all handlers."""

        async def handler(msg, ctx):
            return None

        register_one_way_handler(handler)
        register_conversation_handler(handler)
        assert has_handler(HandlerContext.ONE_WAY)
        assert has_handler(HandlerContext.CONVERSATION)

        clear_handlers()

        assert not has_handler(HandlerContext.ONE_WAY)
        assert not has_handler(HandlerContext.CONVERSATION)

    def test_get_handler_returns_none_when_not_registered(self):
        """Test get_handler returns None when no handler registered."""
        assert get_handler(HandlerContext.ONE_WAY) is None

    def test_overwrite_handler(self):
        """Test that registering new handler overwrites old one."""

        async def handler1(msg, ctx):
            return "first"

        async def handler2(msg, ctx):
            return "second"

        register_one_way_handler(handler1)
        assert get_handler(HandlerContext.ONE_WAY) == handler1

        register_one_way_handler(handler2)
        assert get_handler(HandlerContext.ONE_WAY) == handler2


class TestHandlerInvocation:
    """Test handler invocation functions."""

    @pytest.mark.asyncio
    async def test_invoke_handler_async(self):
        """Test async handler invocation."""

        async def handler(msg, ctx):
            return f"processed: {msg}"

        register_one_way_handler(handler)

        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        result = await invoke_handler_async(HandlerContext.ONE_WAY, "test", ctx)
        assert result == "processed: test"

    @pytest.mark.asyncio
    async def test_invoke_conversation_handler(self):
        """Test conversation handler returns response."""

        async def handler(msg, ctx):
            return {"reply": msg}

        register_conversation_handler(handler)

        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.CONVERSATION,
        )

        result = await invoke_handler_async(HandlerContext.CONVERSATION, "hello", ctx)
        assert result == {"reply": "hello"}

    @pytest.mark.asyncio
    async def test_invoke_no_handler_raises(self):
        """Test invoking handler when none registered raises error."""
        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        with pytest.raises(NoHandlerRegisteredError):
            await invoke_handler_async(HandlerContext.ONE_WAY, "test", ctx)

    def test_invoke_handler_sync(self):
        """Test sync handler invocation."""

        async def handler(msg, ctx):
            return f"sync: {msg}"

        register_one_way_handler(handler)

        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        result = invoke_handler(HandlerContext.ONE_WAY, "test", ctx)
        assert result == "sync: test"

    @pytest.mark.asyncio
    async def test_handler_exception_propagates(self):
        """Test that exceptions in handlers are propagated."""

        async def error_handler(msg, ctx):
            raise ValueError("Handler error")

        register_one_way_handler(error_handler)

        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        with pytest.raises(ValueError, match="Handler error"):
            await invoke_handler_async(HandlerContext.ONE_WAY, "test", ctx)

    @pytest.mark.asyncio
    async def test_sync_handler_works_with_async_invoke(self):
        """Test that sync handlers work with async invocation."""

        def sync_handler(msg, ctx):
            return f"sync: {msg}"

        register_one_way_handler(sync_handler)

        ctx = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        result = await invoke_handler_async(HandlerContext.ONE_WAY, "test", ctx)
        assert result == "sync: test"
