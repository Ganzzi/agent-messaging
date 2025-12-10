"""Comprehensive unit tests for handler routing system.

This test module focuses on verifying the Phase 3+ handler registration
and routing system. Tests ensure that handlers are correctly registered
by agent and context, and that the right handler is invoked for each
messaging pattern.

Key areas tested:
1. Handler registration (one-way, conversation, meeting, system)
2. Handler retrieval by agent and context
3. Multiple agents with different handlers
4. Context-specific routing
"""

import pytest
from uuid import uuid4, UUID

from agent_messaging.handlers.registry import HandlerRegistry
from agent_messaging.handlers.types import HandlerContext
from agent_messaging.models import MessageContext


class TestHandlerRegistration:
    """Test handler registration for different contexts."""

    def test_register_one_way_handler(self):
        """Test registering a one-way handler for an agent."""
        registry = HandlerRegistry()
        agent_id = "alice"

        async def handle_notification(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler(agent_id, handle_notification)

        # Verify handler is registered
        assert registry.has_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        handler = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        assert handler is not None
        assert handler.__name__ == "handle_notification"

    def test_register_conversation_handler(self):
        """Test registering a conversation handler for an agent."""
        registry = HandlerRegistry()
        agent_id = "bob"

        async def handle_query(message: dict, context: MessageContext) -> dict:
            return {"answer": "42"}

        registry.register_conversation_handler(agent_id, handle_query)

        # Verify handler is registered
        assert registry.has_handler_for_agent(agent_id, HandlerContext.CONVERSATION)
        handler = registry.get_handler_for_agent(agent_id, HandlerContext.CONVERSATION)
        assert handler is not None
        assert handler.__name__ == "handle_query"

    def test_register_meeting_handler(self):
        """Test registering a meeting handler for an agent."""
        registry = HandlerRegistry()
        agent_id = "charlie"

        async def handle_turn(message: dict, context: MessageContext) -> dict:
            return {"contribution": "Great idea!"}

        registry.register_meeting_handler(agent_id, handle_turn)

        # Verify handler is registered
        assert registry.has_handler_for_agent(agent_id, HandlerContext.MEETING)
        handler = registry.get_handler_for_agent(agent_id, HandlerContext.MEETING)
        assert handler is not None
        assert handler.__name__ == "handle_turn"

    def test_register_system_handler(self):
        """Test registering a global system handler."""
        registry = HandlerRegistry()

        async def handle_system(message: dict, context: MessageContext) -> None:
            pass

        registry.register_system_handler(handle_system)

        # Verify system handler is registered
        handler = registry.get_system_handler()
        assert handler is not None
        assert handler.__name__ == "handle_system"

    def test_multiple_handlers_per_agent(self):
        """Test registering multiple handler types for same agent."""
        registry = HandlerRegistry()
        agent_id = "dave"

        async def handle_one_way(message: dict, context: MessageContext) -> None:
            pass

        async def handle_conversation(message: dict, context: MessageContext) -> dict:
            return {}

        async def handle_meeting(message: dict, context: MessageContext) -> dict:
            return {}

        registry.register_one_way_handler(agent_id, handle_one_way)
        registry.register_conversation_handler(agent_id, handle_conversation)
        registry.register_meeting_handler(agent_id, handle_meeting)

        # Verify all three handlers are registered and distinct
        assert registry.has_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        assert registry.has_handler_for_agent(agent_id, HandlerContext.CONVERSATION)
        assert registry.has_handler_for_agent(agent_id, HandlerContext.MEETING)

        h1 = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        h2 = registry.get_handler_for_agent(agent_id, HandlerContext.CONVERSATION)
        h3 = registry.get_handler_for_agent(agent_id, HandlerContext.MEETING)

        assert h1.__name__ == "handle_one_way"
        assert h2.__name__ == "handle_conversation"
        assert h3.__name__ == "handle_meeting"


class TestHandlerRetrieval:
    """Test handler retrieval by agent and context."""

    def test_get_handler_for_registered_agent(self):
        """Test retrieving handler for a registered agent."""
        registry = HandlerRegistry()
        agent_id = "eve"

        async def my_handler(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler(agent_id, my_handler)

        handler = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        assert handler is not None
        assert handler is my_handler

    def test_get_handler_for_unregistered_agent(self):
        """Test retrieving handler for an unregistered agent returns None."""
        registry = HandlerRegistry()

        handler = registry.get_handler_for_agent("unknown", HandlerContext.ONE_WAY)
        assert handler is None

    def test_get_handler_wrong_context(self):
        """Test retrieving handler with wrong context returns None."""
        registry = HandlerRegistry()
        agent_id = "frank"

        async def my_handler(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler(agent_id, my_handler)

        # Try to get conversation handler when only one-way is registered
        handler = registry.get_handler_for_agent(agent_id, HandlerContext.CONVERSATION)
        assert handler is None

    def test_has_handler_for_agent(self):
        """Test checking if agent has handler for specific context."""
        registry = HandlerRegistry()
        agent_id = "grace"

        # No handler registered yet
        assert not registry.has_handler_for_agent(agent_id, HandlerContext.ONE_WAY)

        # Register handler
        async def my_handler(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler(agent_id, my_handler)

        # Now has handler
        assert registry.has_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        # But not for other contexts
        assert not registry.has_handler_for_agent(agent_id, HandlerContext.CONVERSATION)


class TestMultipleAgents:
    """Test handler routing with multiple agents."""

    def test_multiple_agents_different_handlers(self):
        """Test that different agents can have different handlers."""
        registry = HandlerRegistry()

        async def alice_handler(message: dict, context: MessageContext) -> None:
            pass

        async def bob_handler(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler("alice", alice_handler)
        registry.register_one_way_handler("bob", bob_handler)

        # Verify each agent has their own handler
        alice_h = registry.get_handler_for_agent("alice", HandlerContext.ONE_WAY)
        bob_h = registry.get_handler_for_agent("bob", HandlerContext.ONE_WAY)

        assert alice_h is not None
        assert bob_h is not None
        assert alice_h is not bob_h
        assert alice_h.__name__ == "alice_handler"
        assert bob_h.__name__ == "bob_handler"

    def test_agent_isolation(self):
        """Test that registering handler for one agent doesn't affect others."""
        registry = HandlerRegistry()

        async def handler_a(message: dict, context: MessageContext) -> None:
            pass

        registry.register_one_way_handler("agent_a", handler_a)

        # Agent B should not have any handlers
        assert registry.has_handler_for_agent("agent_a", HandlerContext.ONE_WAY)
        assert not registry.has_handler_for_agent("agent_b", HandlerContext.ONE_WAY)


class TestContextSpecificRouting:
    """Test that handlers are stored and retrieved per context."""

    def test_context_isolation(self):
        """Test that different contexts store different handlers."""
        registry = HandlerRegistry()
        agent_id = "mike"

        async def one_way_handler(message: dict, context: MessageContext) -> None:
            pass

        async def conversation_handler(message: dict, context: MessageContext) -> dict:
            return {}

        registry.register_one_way_handler(agent_id, one_way_handler)
        registry.register_conversation_handler(agent_id, conversation_handler)

        # Verify contexts are isolated
        h1 = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        h2 = registry.get_handler_for_agent(agent_id, HandlerContext.CONVERSATION)

        assert h1 is not None
        assert h2 is not None
        assert h1 is not h2
        assert h1.__name__ == "one_way_handler"
        assert h2.__name__ == "conversation_handler"

    def test_overwrite_handler_for_context(self):
        """Test that registering a new handler overwrites the old one."""
        registry = HandlerRegistry()
        agent_id = "nancy"

        async def old_handler(message: dict, context: MessageContext) -> None:
            pass

        async def new_handler(message: dict, context: MessageContext) -> None:
            pass

        # Register first handler
        registry.register_one_way_handler(agent_id, old_handler)
        handler1 = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        assert handler1.__name__ == "old_handler"

        # Register second handler (should overwrite)
        registry.register_one_way_handler(agent_id, new_handler)
        handler2 = registry.get_handler_for_agent(agent_id, HandlerContext.ONE_WAY)
        assert handler2.__name__ == "new_handler"


class TestLegacyGlobalHandler:
    """Test backward compatibility with legacy global handler API."""

    def test_register_legacy_global_handler(self):
        """Test registering a legacy global handler (deprecated)."""
        registry = HandlerRegistry()

        async def global_handler(message: dict, context: MessageContext) -> None:
            pass

        # Should work but log deprecation warning
        result = registry.register(global_handler)

        assert result is global_handler
        assert registry.has_handler()
        assert registry.get_handler() is global_handler

    def test_legacy_handler_does_not_affect_per_agent_handlers(self):
        """Test that legacy global handler is separate from per-agent handlers."""
        registry = HandlerRegistry()

        async def global_handler(message: dict, context: MessageContext) -> None:
            pass

        async def agent_handler(message: dict, context: MessageContext) -> None:
            pass

        registry.register(global_handler)
        registry.register_one_way_handler("agent_001", agent_handler)

        # Both should exist independently
        assert registry.has_handler()  # Legacy global
        assert registry.has_handler_for_agent("agent_001", HandlerContext.ONE_WAY)  # Per-agent
