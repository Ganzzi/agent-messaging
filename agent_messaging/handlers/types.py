"""Handler type system for Phase 3 refactor.

Implements type-safe handler protocols and routing for different messaging contexts.
"""

from enum import Enum
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from ..models import MessageContext

__all__ = [
    "HandlerContext",
    "OneWayHandler",
    "ConversationHandler",
    "MeetingHandler",
    "SystemHandler",
    "MessageContextEnhanced",
]


# ============================================================================
# HandlerContext Enum
# ============================================================================


class HandlerContext(str, Enum):
    """Identifies the context/type of message being handled.

    Used for type-based routing in the handler registry.
    """

    ONE_WAY = "one_way"
    """Fire-and-forget messages without response expected."""

    CONVERSATION = "conversation"
    """Synchronous conversation requiring request-response pattern."""

    MEETING = "meeting"
    """Multi-agent meeting messages during active meeting."""

    SYSTEM = "system"
    """Internal system messages (timeouts, events, etc.)."""


# ============================================================================
# Enhanced MessageContext
# ============================================================================


class MessageContextEnhanced(MessageContext):
    """Enhanced message context with handler routing information.

    Extends base MessageContext with additional metadata for type-based routing.
    """

    handler_context: HandlerContext
    """The type of handler that should process this message."""

    is_sync: bool = False
    """True if this is a synchronous conversation awaiting response."""

    requires_response: bool = False
    """True if handler response should be captured and sent back."""


# ============================================================================
# Handler Protocols (Type-Safe Signatures)
# ============================================================================


@runtime_checkable
class OneWayHandler(Protocol):
    """Protocol for one-way message handlers.

    One-way handlers process fire-and-forget messages. The sender does not
    wait for or expect a response. The handler is invoked asynchronously.

    Example:
        @sdk.register_one_way_handler("agent_id")
        async def handle_notification(message: str, context: MessageContext) -> None:
            print(f"Received: {message}")
    """

    async def __call__(
        self,
        message: Any,
        context: MessageContext,
    ) -> None:
        """Process a one-way message.

        Args:
            message: The message content (user-defined type)
            context: Message metadata and routing information

        Returns:
            None - no response is sent

        Note:
            Any return value is ignored. The message is fire-and-forget.
        """
        ...


@runtime_checkable
class ConversationHandler(Protocol):
    """Protocol for synchronous conversation handlers.

    Conversation handlers process request-response messages. The sender blocks
    and waits for the handler's response with a configurable timeout.

    Example:
        @sdk.register_conversation_handler("agent_id")
        async def handle_query(message: str, context: MessageContext) -> str:
            return f"Answer to: {message}"
    """

    async def __call__(
        self,
        message: Any,
        context: MessageContext,
    ) -> Any:
        """Process a conversation message and return a response.

        Args:
            message: The message content (user-defined type)
            context: Message metadata including session_id

        Returns:
            Response to be sent back to sender. Can be any JSON-serializable type.
            If no response is needed, return None.

        Raises:
            Exception: Any exception is logged; timeout is managed separately
        """
        ...


@runtime_checkable
class MeetingHandler(Protocol):
    """Protocol for multi-agent meeting handlers.

    Meeting handlers process messages during active meetings. Handlers are
    invoked for messages where a particular agent has the speaking turn.

    Example:
        @sdk.register_meeting_handler("agent_id")
        async def handle_meeting_turn(message: str, context: MessageContext) -> str:
            return f"My contribution: ..."
    """

    async def __call__(
        self,
        message: Any,
        context: MessageContext,
    ) -> Any:
        """Process a meeting message.

        Args:
            message: The message content (user-defined type)
            context: Message metadata including meeting_id and turn info

        Returns:
            Message to speak in the meeting. Return None to pass turn silently.

        Note:
            The handler can inspect context.meeting_id to understand meeting state.
        """
        ...


@runtime_checkable
class SystemHandler(Protocol):
    """Protocol for system message handlers.

    System handlers process internal messages like timeouts, meeting events,
    and other system-generated events. These are primarily for monitoring
    and logging purposes.

    Example:
        @sdk.register_system_handler()
        async def handle_timeout(message: dict, context: MessageContext) -> None:
            if message.get("type") == "turn_timeout":
                print(f"Agent {context.sender_id} timed out")
    """

    async def __call__(
        self,
        message: Any,
        context: MessageContext,
    ) -> None:
        """Process a system message.

        Args:
            message: System message payload (usually dict)
            context: Message metadata

        Returns:
            None - system messages are informational
        """
        ...


# ============================================================================
# Handler Type Definitions
# ============================================================================

# Generic handler type that can be any of the above
AnyHandler = Callable[[Any, MessageContext], Any]
"""Type for any handler (one-way, conversation, meeting, system)."""
