# Handler system for Agent Messaging Protocol
"""Global handler registration and invocation for agent messaging.

This module provides a functional API for registering message handlers.
Handlers are global processors that apply to ALL agents.

Example:
    from agent_messaging.handlers import (
        register_one_way_handler,
        register_conversation_handler,
        register_meeting_handler,
        MessageContext,
        HandlerContext,
    )

    @register_one_way_handler
    async def handle_notification(message: Notification, context: MessageContext) -> None:
        print(f"Received: {message}")
"""

from .types import (
    # Generic type variables
    T_OneWay,
    T_Conversation,
    T_Meeting,
    # Context types
    HandlerContext,
    MessageContext,
    # Handler protocols
    OneWayHandler,
    ConversationHandler,
    MeetingHandler,
    SystemHandler,
    AnyHandler,
)
from .registry import (
    # Registration decorators
    register_one_way_handler,
    register_conversation_handler,
    register_meeting_handler,
    register_system_handler,
    # Lookup functions
    get_handler,
    has_handler,
    list_handlers,
    # Invocation functions
    invoke_handler,
    invoke_handler_async,
    # Management functions
    clear_handlers,
    set_handler_timeout,
    shutdown,
)
from .events import MeetingEventHandler, MeetingEvent

__all__ = [
    # Generic type variables
    "T_OneWay",
    "T_Conversation",
    "T_Meeting",
    # Context types
    "HandlerContext",
    "MessageContext",
    # Handler protocols
    "OneWayHandler",
    "ConversationHandler",
    "MeetingHandler",
    "SystemHandler",
    "AnyHandler",
    # Registration decorators
    "register_one_way_handler",
    "register_conversation_handler",
    "register_meeting_handler",
    "register_system_handler",
    # Lookup functions
    "get_handler",
    "has_handler",
    "list_handlers",
    # Invocation functions
    "invoke_handler",
    "invoke_handler_async",
    # Management functions
    "clear_handlers",
    "set_handler_timeout",
    "shutdown",
    # Meeting events
    "MeetingEventHandler",
    "MeetingEvent",
]
