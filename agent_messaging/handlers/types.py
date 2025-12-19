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

    MESSAGE_NOTIFICATION = "message_notification"
    """Notification that a new message has arrived for an agent that is not currently waiting."""


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

    Type Safety:
        While the generic T_OneWay is erased at runtime, you should use explicit
        type hints for IDE support and static type checking:

    Example with TypedDict:
        from typing import TypedDict

        class Notification(TypedDict):
            type: str
            text: str
            priority: str

        @register_one_way_handler
        async def handle_notification(
            message: Notification,  # ← Type hint for IDE autocomplete
            context: MessageContext
        ) -> None:
            # IDE knows message.text, message.priority exist
            print(f"[{message['priority']}] {message['text']}")

    Example with Pydantic:
        from pydantic import BaseModel

        class Notification(BaseModel):
            type: str
            text: str
            priority: str = "normal"

        @register_one_way_handler
        async def handle_notification(
            message: Notification,  # ← Pydantic model
            context: MessageContext
        ) -> None:
            # Full IDE autocomplete + runtime validation
            print(f"[{message.priority}] {message.text}")
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

    Type Safety:
        Use explicit type hints for request and response types. Both should be
        the same type (T_Conversation), but you can use unions or inheritance
        for flexibility.

    Example with TypedDict:
        from typing import TypedDict

        class Query(TypedDict):
            question: str
            context: str

        class Response(TypedDict):
            answer: str
            confidence: float

        @register_conversation_handler
        async def handle_query(
            message: Query,  # ← Type hint for request
            context: MessageContext
        ) -> Response:  # ← Type hint for response
            # IDE knows message.question exists
            answer = process_question(message['question'])
            return {"answer": answer, "confidence": 0.95}

    Example with Pydantic:
        from pydantic import BaseModel

        class Query(BaseModel):
            question: str
            context: str = ""

        class Response(BaseModel):
            answer: str
            confidence: float = 1.0

        @register_conversation_handler
        async def handle_query(
            message: Query,  # ← Pydantic request model
            context: MessageContext
        ) -> Response:  # ← Pydantic response model
            # Full IDE autocomplete + validation
            answer = process_question(message.question)
            return Response(answer=answer, confidence=0.95)
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


# ============================================================================
# Handler Type Definitions
# ============================================================================

AnyHandler = Callable[[Any, MessageContext], Any]
"""Type alias for any handler callable."""
