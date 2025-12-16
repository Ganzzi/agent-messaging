"""Handler type system for agent messaging.

Defines type-safe handler protocols with three separate generic types:
- T_OneWay: Type for fire-and-forget messages
- T_Conversation: Type for request-response messages
- T_Meeting: Type for meeting messages

Handlers are global processors that apply to all agents across all organizations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar

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
    # Type aliases
    "AnyHandler",
]

# ============================================================================
# Generic Type Variables
# ============================================================================

T_OneWay = TypeVar("T_OneWay")
"""Type variable for one-way (fire-and-forget) message payloads."""

T_Conversation = TypeVar("T_Conversation")
"""Type variable for conversation (request-response) message payloads."""

T_Meeting = TypeVar("T_Meeting")
"""Type variable for meeting message payloads."""


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
# MessageContext Dataclass
# ============================================================================


@dataclass
class MessageContext:
    """Context information passed to handlers with each message.

    Contains routing information and metadata about the message being processed.
    Handlers receive this alongside the message payload to understand the
    message source, destination, and any associated session/meeting context.
    """

    sender_id: str
    """External ID of the agent that sent the message."""

    receiver_id: str
    """External ID of the agent receiving the message."""

    organization_id: str
    """External ID of the organization both agents belong to."""

    handler_context: HandlerContext
    """The type of handler that should process this message."""

    message_id: Optional[int] = None
    """Database ID of the message record, if persisted."""

    session_id: Optional[str] = None
    """Session ID for conversation messages (request-response pairing)."""

    meeting_id: Optional[int] = None
    """Meeting ID for meeting messages."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata associated with the message."""


# ============================================================================
# Handler Protocols (Type-Safe Signatures)
# ============================================================================


class OneWayHandler(Protocol[T_OneWay]):
    """Protocol for one-way message handlers.

    One-way handlers process fire-and-forget messages. The sender does not
    wait for or expect a response. The handler is invoked asynchronously.

    This is a global handler that processes messages for ALL agents.

    Example:
        @register_one_way_handler
        async def handle_notification(message: Notification, context: MessageContext) -> None:
            print(f"Received: {message}")
    """

    async def __call__(
        self,
        message: T_OneWay,
        context: MessageContext,
    ) -> None:
        """Process a one-way message.

        Args:
            message: The message content (T_OneWay type)
            context: Message metadata and routing information

        Returns:
            None - no response is sent

        Note:
            Any return value is ignored. The message is fire-and-forget.
        """
        ...


class ConversationHandler(Protocol[T_Conversation]):
    """Protocol for synchronous conversation handlers.

    Conversation handlers process request-response messages. The sender blocks
    and waits for the handler's response with a configurable timeout.

    This is a global handler that processes messages for ALL agents.

    Example:
        @register_conversation_handler
        async def handle_query(message: Query, context: MessageContext) -> Response:
            return Response(answer=f"Answer to: {message.question}")
    """

    async def __call__(
        self,
        message: T_Conversation,
        context: MessageContext,
    ) -> T_Conversation:
        """Process a conversation message and return a response.

        Args:
            message: The message content (T_Conversation type)
            context: Message metadata including session_id

        Returns:
            Response to be sent back to sender (T_Conversation type).
            If no response is needed, return None.

        Raises:
            Exception: Any exception is logged; timeout is managed separately
        """
        ...


class MeetingHandler(Protocol[T_Meeting]):
    """Protocol for multi-agent meeting handlers.

    Meeting handlers process messages during active meetings. Handlers are
    invoked for messages where a particular agent has the speaking turn.

    This is a global handler that processes messages for ALL agents.

    Example:
        @register_meeting_handler
        async def handle_meeting_turn(message: MeetingMsg, context: MessageContext) -> MeetingMsg:
            return MeetingMsg(content=f"My contribution: ...")
    """

    async def __call__(
        self,
        message: T_Meeting,
        context: MessageContext,
    ) -> T_Meeting:
        """Process a meeting message.

        Args:
            message: The message content (T_Meeting type)
            context: Message metadata including meeting_id and turn info

        Returns:
            Message to speak in the meeting (T_Meeting type). Return None to pass turn silently.

        Note:
            The handler can inspect context.meeting_id to understand meeting state.
        """
        ...


class SystemHandler(Protocol):
    """Protocol for system message handlers.

    System handlers process internal messages like timeouts, meeting events,
    and other system-generated events. These are primarily for monitoring
    and logging purposes.

    This is a global handler that processes system messages for ALL agents.

    Example:
        @register_system_handler
        async def handle_system(message: dict, context: MessageContext) -> None:
            if message.get("type") == "turn_timeout":
                print(f"Agent {context.sender_id} timed out")
    """

    async def __call__(
        self,
        message: dict[str, Any],
        context: MessageContext,
    ) -> None:
        """Process a system message.

        Args:
            message: System message payload (dict)
            context: Message metadata

        Returns:
            None - system messages are informational
        """
        ...


# ============================================================================
# Handler Type Definitions
# ============================================================================

AnyHandler = Callable[[Any, MessageContext], Any]
"""Type alias for any handler callable."""
