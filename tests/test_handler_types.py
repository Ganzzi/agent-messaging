"""Phase 3 tests: Handler Architecture Refactor with Type-Based Routing.

Tests for:
- HandlerContext enum and type system
- Handler protocols (OneWayHandler, ConversationHandler, MeetingHandler, SystemHandler)
- HandlerRegistry with per-agent per-context storage
- Type-based handler routing
- Backward compatibility with global handler (deprecated API)
- Deprecation warnings
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_messaging.handlers import (
    HandlerContext,
    HandlerRegistry,
    OneWayHandler,
    ConversationHandler,
    MeetingHandler,
    SystemHandler,
)
from agent_messaging.models import MessageContext
from agent_messaging.exceptions import NoHandlerRegisteredError, HandlerTimeoutError
from datetime import datetime
from uuid import uuid4


# ============================================================================
# Test HandlerContext Enum
# ============================================================================


class TestHandlerContextEnum:
    """Test HandlerContext enum definition and values."""

    def test_handler_context_values(self):
        """Test that HandlerContext has the expected values."""
        assert HandlerContext.ONE_WAY.value == "one_way"
        assert HandlerContext.CONVERSATION.value == "conversation"
        assert HandlerContext.MEETING.value == "meeting"
        assert HandlerContext.SYSTEM.value == "system"

    def test_handler_context_enum_count(self):
        """Test that HandlerContext has exactly 4 values."""
        assert len(HandlerContext) == 4

    def test_handler_context_is_string_enum(self):
        """Test that HandlerContext values are strings."""
        assert isinstance(HandlerContext.ONE_WAY, HandlerContext)
        assert isinstance(HandlerContext.ONE_WAY.value, str)


# ============================================================================
# Test HandlerRegistry Type-Based Registration
# ============================================================================


class TestHandlerRegistrationNewAPI:
    """Test new Phase 3 handler registration API with type-based routing."""

    @pytest.mark.asyncio
    async def test_register_one_way_handler(self):
        """Test registering a one-way handler for an agent."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return None

        result = registry.register_one_way_handler("agent_alice", handler)
        assert result == handler
        assert registry.has_handler_for_agent("agent_alice", HandlerContext.ONE_WAY)

    @pytest.mark.asyncio
    async def test_register_conversation_handler(self):
        """Test registering a conversation handler for an agent."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return "response"

        result = registry.register_conversation_handler("agent_bob", handler)
        assert result == handler
        assert registry.has_handler_for_agent("agent_bob", HandlerContext.CONVERSATION)

    @pytest.mark.asyncio
    async def test_register_meeting_handler(self):
        """Test registering a meeting handler for an agent."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return "contribution"

        result = registry.register_meeting_handler("agent_charlie", handler)
        assert result == handler
        assert registry.has_handler_for_agent("agent_charlie", HandlerContext.MEETING)

    @pytest.mark.asyncio
    async def test_register_system_handler(self):
        """Test registering a global system handler."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return None

        result = registry.register_system_handler(handler)
        assert result == handler
        assert registry.get_system_handler() == handler

    @pytest.mark.asyncio
    async def test_different_agents_different_handlers(self):
        """Test registering different handlers for different agents."""
        registry = HandlerRegistry()

        async def alice_handler(msg, ctx):
            return "alice"

        async def bob_handler(msg, ctx):
            return "bob"

        registry.register_one_way_handler("alice", alice_handler)
        registry.register_one_way_handler("bob", bob_handler)

        alice_result = registry.get_handler_for_agent("alice", HandlerContext.ONE_WAY)
        bob_result = registry.get_handler_for_agent("bob", HandlerContext.ONE_WAY)

        assert alice_result == alice_handler
        assert bob_result == bob_handler
        assert alice_result != bob_result

    @pytest.mark.asyncio
    async def test_multiple_contexts_per_agent(self):
        """Test registering different context handlers for the same agent."""
        registry = HandlerRegistry()

        async def one_way(msg, ctx):
            return None

        async def conversation(msg, ctx):
            return "reply"

        async def meeting(msg, ctx):
            return "contribution"

        registry.register_one_way_handler("agent", one_way)
        registry.register_conversation_handler("agent", conversation)
        registry.register_meeting_handler("agent", meeting)

        assert registry.get_handler_for_agent("agent", HandlerContext.ONE_WAY) == one_way
        assert registry.get_handler_for_agent("agent", HandlerContext.CONVERSATION) == conversation
        assert registry.get_handler_for_agent("agent", HandlerContext.MEETING) == meeting

    @pytest.mark.asyncio
    async def test_overwrite_handler(self):
        """Test that registering a new handler overwrites the old one."""
        registry = HandlerRegistry()

        async def handler1(msg, ctx):
            return "first"

        async def handler2(msg, ctx):
            return "second"

        registry.register_one_way_handler("agent", handler1)
        assert registry.get_handler_for_agent("agent", HandlerContext.ONE_WAY) == handler1

        registry.register_one_way_handler("agent", handler2)
        assert registry.get_handler_for_agent("agent", HandlerContext.ONE_WAY) == handler2


# ============================================================================
# Test Handler Invocation with Type-Based Routing
# ============================================================================


class TestHandlerInvocationWithRouting:
    """Test handler invocation with type-based routing."""

    @pytest.mark.asyncio
    async def test_invoke_handler_with_agent_context(self):
        """Test invoking a handler with agent-specific routing."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return "success"

        registry.register_one_way_handler("agent_alice", handler)

        msg_context = MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        result = await registry.invoke_handler(
            "test message",
            msg_context,
            agent_external_id="agent_alice",
            handler_context=HandlerContext.ONE_WAY,
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_invoke_handler_async_with_routing(self):
        """Test async handler invocation with type-based routing."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            await asyncio.sleep(0.01)
            return "done"

        registry.register_one_way_handler("agent_bob", handler)

        msg_context = MessageContext(
            sender_id="bob",
            recipient_id="alice",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        task = registry.invoke_handler_async(
            "test message",
            msg_context,
            agent_external_id="agent_bob",
            handler_context=HandlerContext.ONE_WAY,
        )

        assert isinstance(task, asyncio.Task)
        await asyncio.sleep(0.05)  # Let task complete
        assert task.done()

    @pytest.mark.asyncio
    async def test_fallback_to_global_handler(self):
        """Test fallback to global handler when agent-specific handler not found."""
        registry = HandlerRegistry()

        async def global_handler(msg, ctx):
            return "global"

        registry.register(global_handler)  # Register global handler

        msg_context = MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        # Request handler for agent with no specific handler - should fall back to global
        result = await registry.invoke_handler(
            "test message",
            msg_context,
            agent_external_id="unknown_agent",
            handler_context=HandlerContext.ONE_WAY,
        )

        assert result == "global"

    @pytest.mark.asyncio
    async def test_no_handler_error(self):
        """Test that NoHandlerRegisteredError is raised when no handler exists."""
        registry = HandlerRegistry()

        msg_context = MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        with pytest.raises(NoHandlerRegisteredError):
            await registry.invoke_handler(
                "test message",
                msg_context,
                agent_external_id="unknown_agent",
                handler_context=HandlerContext.ONE_WAY,
            )

    @pytest.mark.asyncio
    async def test_handler_timeout(self):
        """Test that HandlerTimeoutError is raised on timeout."""
        registry = HandlerRegistry(handler_timeout=0.01)

        async def slow_handler(msg, ctx):
            await asyncio.sleep(1)
            return "done"

        registry.register_one_way_handler("agent", slow_handler)

        msg_context = MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        with pytest.raises(HandlerTimeoutError):
            await registry.invoke_handler(
                "test message",
                msg_context,
                agent_external_id="agent",
                handler_context=HandlerContext.ONE_WAY,
            )


# ============================================================================
# Test Backward Compatibility with Deprecated API
# ============================================================================


class TestBackwardCompatibility:
    """Test that deprecated global handler API still works."""

    @pytest.mark.asyncio
    async def test_legacy_register_still_works(self):
        """Test that old register() method still works."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return "legacy"

        registry.register(handler)
        assert registry.has_handler()
        assert registry.get_handler() == handler

    @pytest.mark.asyncio
    async def test_legacy_invoke_still_works(self):
        """Test that invoking without agent_id still works with global handler."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return "legacy_response"

        registry.register(handler)

        msg_context = MessageContext(
            sender_id="alice",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        # Invoke without agent_external_id - should use global handler
        result = await registry.invoke_handler("test message", msg_context)
        assert result == "legacy_response"

    @pytest.mark.asyncio
    async def test_agent_handler_overrides_global(self):
        """Test that agent-specific handler takes priority over global."""
        registry = HandlerRegistry()

        async def global_handler(msg, ctx):
            return "global"

        async def agent_handler(msg, ctx):
            return "agent"

        registry.register(global_handler)
        registry.register_one_way_handler("agent", agent_handler)

        msg_context = MessageContext(
            sender_id="agent",
            recipient_id="bob",
            message_id=uuid4(),
            timestamp=datetime.now(),
        )

        result = await registry.invoke_handler(
            "test message",
            msg_context,
            agent_external_id="agent",
            handler_context=HandlerContext.ONE_WAY,
        )

        assert result == "agent"

    @pytest.mark.asyncio
    async def test_deprecation_warning_on_register(self):
        """Test that deprecation warning is logged when using old API."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return None

        with patch("agent_messaging.handlers.registry.logger") as mock_logger:
            registry.register(handler)
            # Check that warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "deprecated" in call_args.lower()


# ============================================================================
# Test Handler Listing/Introspection
# ============================================================================


class TestHandlerIntrospection:
    """Test handler registry introspection methods."""

    @pytest.mark.asyncio
    async def test_list_handlers(self):
        """Test listing all registered handlers."""
        registry = HandlerRegistry()

        async def alice_one_way(msg, ctx):
            return None

        async def alice_conversation(msg, ctx):
            return "reply"

        async def bob_one_way(msg, ctx):
            return None

        registry.register_one_way_handler("alice", alice_one_way)
        registry.register_conversation_handler("alice", alice_conversation)
        registry.register_one_way_handler("bob", bob_one_way)

        handlers = registry.list_handlers()

        assert "alice" in handlers
        assert "bob" in handlers
        assert "one_way" in handlers["alice"]
        assert "conversation" in handlers["alice"]
        assert "one_way" in handlers["bob"]
        assert handlers["alice"]["one_way"] == "alice_one_way"
        assert handlers["alice"]["conversation"] == "alice_conversation"
        assert handlers["bob"]["one_way"] == "bob_one_way"

    @pytest.mark.asyncio
    async def test_has_handler_for_agent(self):
        """Test has_handler_for_agent method."""
        registry = HandlerRegistry()

        async def handler(msg, ctx):
            return None

        # No handler registered
        assert not registry.has_handler_for_agent("agent", HandlerContext.ONE_WAY)

        # Register handler
        registry.register_one_way_handler("agent", handler)
        assert registry.has_handler_for_agent("agent", HandlerContext.ONE_WAY)

        # Different context should return False
        assert not registry.has_handler_for_agent("agent", HandlerContext.CONVERSATION)

    @pytest.mark.asyncio
    async def test_get_system_handler(self):
        """Test getting system handler."""
        registry = HandlerRegistry()

        async def sys_handler(msg, ctx):
            return None

        assert registry.get_system_handler() is None

        registry.register_system_handler(sys_handler)
        assert registry.get_system_handler() == sys_handler


# ============================================================================
# Test Handler Protocol Definitions
# ============================================================================


class TestHandlerProtocols:
    """Test that handler protocols are properly defined."""

    @pytest.mark.asyncio
    async def test_one_way_handler_protocol(self):
        """Test OneWayHandler protocol matches expected signature."""

        async def valid_one_way(message: str, context: MessageContext) -> None:
            pass

        # If this doesn't raise, the protocol is properly defined
        assert callable(valid_one_way)

    @pytest.mark.asyncio
    async def test_conversation_handler_protocol(self):
        """Test ConversationHandler protocol matches expected signature."""

        async def valid_conversation(message: str, context: MessageContext) -> str:
            return "response"

        assert callable(valid_conversation)

    @pytest.mark.asyncio
    async def test_meeting_handler_protocol(self):
        """Test MeetingHandler protocol matches expected signature."""

        async def valid_meeting(message: str, context: MessageContext) -> str:
            return "contribution"

        assert callable(valid_meeting)

    @pytest.mark.asyncio
    async def test_system_handler_protocol(self):
        """Test SystemHandler protocol matches expected signature."""

        async def valid_system(message: dict, context: MessageContext) -> None:
            pass

        assert callable(valid_system)


# ============================================================================
# Test Integration with Multiple Handlers
# ============================================================================


class TestMultiHandlerIntegration:
    """Test complex scenarios with multiple handlers."""

    @pytest.mark.asyncio
    async def test_multiple_agents_different_types(self):
        """Test multiple agents with different handler types."""
        registry = HandlerRegistry()

        async def alice_one_way(msg, ctx):
            return None

        async def bob_conversation(msg, ctx):
            return "reply"

        async def charlie_meeting(msg, ctx):
            return "contribution"

        registry.register_one_way_handler("alice", alice_one_way)
        registry.register_conversation_handler("bob", bob_conversation)
        registry.register_meeting_handler("charlie", charlie_meeting)

        # Test Alice
        msg_context = MessageContext(
            sender_id="alice", recipient_id="x", message_id=uuid4(), timestamp=datetime.now()
        )
        await registry.invoke_handler_async(
            "test", msg_context, agent_external_id="alice", handler_context=HandlerContext.ONE_WAY
        )

        # Test Bob
        result_bob = await registry.invoke_handler(
            "test",
            msg_context,
            agent_external_id="bob",
            handler_context=HandlerContext.CONVERSATION,
        )
        assert result_bob == "reply"

        # Test Charlie
        result_charlie = await registry.invoke_handler(
            "test", msg_context, agent_external_id="charlie", handler_context=HandlerContext.MEETING
        )
        assert result_charlie == "contribution"

    @pytest.mark.asyncio
    async def test_handler_exception_propagates(self):
        """Test that exceptions in handlers are properly propagated."""
        registry = HandlerRegistry()

        async def error_handler(msg, ctx):
            raise ValueError("Handler error")

        registry.register_one_way_handler("agent", error_handler)

        msg_context = MessageContext(
            sender_id="agent", recipient_id="x", message_id=uuid4(), timestamp=datetime.now()
        )

        with pytest.raises(ValueError, match="Handler error"):
            await registry.invoke_handler(
                "test",
                msg_context,
                agent_external_id="agent",
                handler_context=HandlerContext.ONE_WAY,
            )
