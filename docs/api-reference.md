# Agent Messaging Protocol - API Reference

> Complete API documentation for the Agent Messaging Protocol SDK v0.4.0

**Version:** 0.4.0  
**Status:** Production Ready  
**Last Updated:** December 19, 2025

---

## Table of Contents

1. [SDK Classes](#sdk-classes)
2. [Messaging Classes](#messaging-classes)
3. [Handler System](#handler-system)
4. [Models and Data Types](#models-and-data-types)
5. [Exceptions](#exceptions)
6. [Configuration](#configuration)
7. [Examples](#examples)

---

## SDK Classes

### AgentMessaging[T_OneWay, T_Conversation, T_Meeting]

Main SDK class providing access to all messaging capabilities and agent management.

#### Generic Type Parameters

- **T_OneWay**: Type for fire-and-forget message payloads
- **T_Conversation**: Type for request-response message payloads
- **T_Meeting**: Type for meeting message payloads

#### Lifecycle Methods

```python
def __init__(config: Optional[Config] = None) -> None:
    """
    Initialize the SDK with optional configuration.
    
    Args:
        config: Optional Config object. If None, loads from environment variables.
    
    Example:
        from agent_messaging import AgentMessaging, Config
        
        config = Config(database=DatabaseConfig(host="prod-db"))
        sdk = AgentMessaging[Notification, Query, MeetingMsg](config=config)
    """

async def __aenter__() -> AgentMessaging:
    """
    Enter async context manager.
    
    Initializes database connection pool and prepares repositories.
    
    Returns:
        Self for use in async with block.
    
    Raises:
        DatabaseError: If connection pool initialization fails.
    
    Example:
        async with AgentMessaging[dict, dict, dict]() as sdk:
            await sdk.register_organization("org_001", "My Org")
    """

async def __aexit__(
    exc_type: Optional[Type[BaseException]],
    exc_val: Optional[BaseException],
    exc_tb: Optional[TracebackType]
) -> None:
    """
    Exit async context manager.
    
    Closes database connection pool and cleans up resources.
    
    Args:
        exc_type: Exception type if exception occurred
        exc_val: Exception value if exception occurred
        exc_tb: Exception traceback if exception occurred
    """
```

#### Organization Management

```python
async def register_organization(
    external_id: str,
    name: str
) -> UUID:
    """
    Register a new organization.
    
    Args:
        external_id: Unique external identifier (e.g., "org_001", "company-acme")
        name: Human-readable organization name
    
    Returns:
        UUID of the created organization
    
    Raises:
        ValueError: If external_id or name is empty
        DatabaseError: If database operation fails
    
    Example:
        org_id = await sdk.register_organization(
            "org_001",
            "Acme Corporation"
        )
    """

async def get_organization(external_id: str) -> Organization:
    """
    Retrieve organization by external ID.
    
    Args:
        external_id: Organization's external identifier
    
    Returns:
        Organization object with id, external_id, name, timestamps
    
    Raises:
        OrganizationNotFoundError: If organization doesn't exist
        RuntimeError: If SDK not initialized
    
    Example:
        org = await sdk.get_organization("org_001")
        print(f"Organization: {org.name}")
    """

async def deregister_organization(external_id: str) -> bool:
    """
    Deregister/delete an organization.
    
    Cascades delete to all agents and their sessions.
    
    Args:
        external_id: Organization's external identifier
    
    Returns:
        True if organization was deleted, False if not found
    
    Raises:
        RuntimeError: If SDK not initialized
    
    Example:
        success = await sdk.deregister_organization("org_001")
    """
```

#### Agent Management

```python
async def register_agent(
    external_id: str,
    organization_external_id: str,
    name: str
) -> UUID:
    """
    Register a new agent within an organization.
    
    Args:
        external_id: Unique external identifier for the agent
        organization_external_id: External ID of the organization
        name: Human-readable agent name
    
    Returns:
        UUID of the created agent
    
    Raises:
        ValueError: If parameters are empty
        OrganizationNotFoundError: If organization doesn't exist
        DatabaseError: If database operation fails
    
    Example:
        agent_id = await sdk.register_agent(
            "alice",
            "org_001",
            "Alice Agent"
        )
    """

async def get_agent(external_id: str) -> Agent:
    """
    Retrieve agent by external ID.
    
    Args:
        external_id: Agent's external identifier
    
    Returns:
        Agent object with id, external_id, organization_id, name, timestamps
    
    Raises:
        AgentNotFoundError: If agent doesn't exist
        RuntimeError: If SDK not initialized
    
    Example:
        agent = await sdk.get_agent("alice")
        print(f"Agent: {agent.name}")
    """

async def deregister_agent(external_id: str) -> bool:
    """
    Deregister/delete an agent.
    
    Cascades delete to all their messages and sessions.
    
    Args:
        external_id: Agent's external identifier
    
    Returns:
        True if agent was deleted, False if not found
    
    Raises:
        RuntimeError: If SDK not initialized
    
    Example:
        success = await sdk.deregister_agent("alice")
    """
```

#### Message Search

```python
async def search_messages(
    search_query: str,
    sender_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    session_id: Optional[str] = None,
    meeting_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Search messages using full-text search with optional context filtering.
    
    Uses PostgreSQL websearch_to_tsquery for ranking and relevance.
    
    Args:
        search_query: Full-text search query (supports AND, OR, NOT, phrases)
        sender_id: Optional filter by sender's external ID
        recipient_id: Optional filter by recipient's external ID
        session_id: Optional filter by conversation session ID
        meeting_id: Optional filter by meeting ID
        limit: Maximum number of results (default 50, max 500)
        offset: Pagination offset (default 0)
    
    Returns:
        List of message dictionaries with id, sender, recipient, content, 
        timestamp, and relevance ranking
    
    Raises:
        ValueError: If search_query is empty or limit > 500
        RuntimeError: If SDK not initialized
    
    Example:
        results = await sdk.search_messages(
            "database migration",
            sender_id="alice",
            limit=20
        )
        for msg in results:
            print(f"Match: {msg['content']} (rank: {msg['ts_rank']})")
    """
```

#### Event Handler Registration

```python
def register_event_handler(self, event_type: MeetingEventType) -> Callable:
    """
    Decorator for registering meeting event handlers.
    
    Args:
        event_type: Type of meeting event to handle
    
    Returns:
        Decorator function
    
    Raises:
        ValueError: If event_type is invalid
    
    Example:
        @sdk.register_event_handler(MeetingEventType.TURN_CHANGED)
        async def on_turn_changed(event: MeetingEventPayload) -> None:
            print(f"Turn changed to: {event.data['current_speaker_id']}")
    """
```

#### Messaging Properties

```python
@property
def one_way(self) -> OneWayMessenger[T_OneWay]:
    """
    Access one-way messaging interface.
    
    Returns:
        OneWayMessenger instance for sending fire-and-forget messages
    
    Raises:
        RuntimeError: If SDK not initialized
    """

@property
def conversation(self) -> Conversation[T_Conversation]:
    """
    Access unified conversation interface (sync and async).
    
    Returns:
        Conversation instance for request-response and async messaging
    
    Raises:
        RuntimeError: If SDK not initialized
    """

@property
def meeting(self) -> MeetingManager[T_Meeting]:
    """
    Access meeting management interface.
    
    Returns:
        MeetingManager instance for multi-agent meetings
    
    Raises:
        RuntimeError: If SDK not initialized
    """
```

---

## Messaging Classes

### OneWayMessenger[T]

One-to-many fire-and-forget messaging.

```python
async def send(
    sender_external_id: str,
    recipient_external_ids: List[str],
    message: T,
    metadata: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Send a one-way message to multiple recipients.
    
    Handler is invoked asynchronously for each recipient.
    Message is stored even if handler invocation fails.
    
    Args:
        sender_external_id: External ID of sender
        recipient_external_ids: List of recipient external IDs
        message: Message payload (T type)
        metadata: Optional custom metadata dict for tracking
    
    Returns:
        List of message IDs (UUIDs as strings)
    
    Raises:
        ValueError: If parameters are invalid
        AgentNotFoundError: If sender or any recipient doesn't exist
        NoHandlerRegisteredError: If no handler is registered
    
    Example:
        msg_ids = await sdk.one_way.send(
            "notification_service",
            ["alice", "bob", "charlie"],
            Notification(type="alert", text="System maintenance"),
            metadata={"priority": "high"}
        )
        print(f"Sent {len(msg_ids)} messages")
    """

async def get_sent_messages(
    sender_external_id: str,
    limit: int = 100,
    offset: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Get messages sent by an agent.
    
    Args:
        sender_external_id: Sender's external ID
        limit: Maximum results (default 100)
        offset: Pagination offset
        date_from: Optional start date filter
        date_to: Optional end date filter
    
    Returns:
        List of message dictionaries
    """

async def get_received_messages(
    recipient_external_id: str,
    include_read: bool = True,
    limit: int = 100,
    offset: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Get messages received by an agent.
    
    Args:
        recipient_external_id: Recipient's external ID
        include_read: Include already read messages
        limit: Maximum results
        offset: Pagination offset
        date_from: Optional start date filter
        date_to: Optional end date filter
    
    Returns:
        List of message dictionaries
    """

async def mark_messages_read(
    recipient_external_id: str,
    sender_external_id: Optional[str] = None
) -> int:
    """
    Mark messages as read.
    
    Args:
        recipient_external_id: Recipient's external ID
        sender_external_id: Optional filter by specific sender
    
    Returns:
        Number of messages marked as read
    """

async def get_message_count(
    agent_external_id: str,
    role: str = "recipient",
    read_status: Optional[bool] = None
) -> int:
    """
    Get count of messages with optional filters.
    
    Args:
        agent_external_id: Agent's external ID
        role: "recipient" or "sender"
        read_status: None=all, True=read, False=unread
    
    Returns:
        Message count
    """
```

### Conversation[T]

Unified interface for synchronous and asynchronous conversations.

```python
async def send_and_wait(
    sender_external_id: str,
    recipient_external_id: str,
    message: T,
    timeout: float = 30.0,
    metadata: Optional[Dict[str, Any]] = None
) -> T:
    """
    Send message and wait for response (blocking).
    
    Acquires PostgreSQL advisory lock for coordination.
    Handler is invoked immediately. If handler responds within 100ms,
    response is auto-sent. Otherwise, waits for async response.
    
    Args:
        sender_external_id: Sender's external ID
        recipient_external_id: Recipient's external ID
        message: Message payload
        timeout: Max seconds to wait for response (default 30)
        metadata: Optional custom metadata
    
    Returns:
        Response message from recipient
    
    Raises:
        TimeoutError: If response not received within timeout
        AgentNotFoundError: If agents don't exist
        NoHandlerRegisteredError: If no handler registered
        SessionLockError: If lock acquisition fails
    
    Example:
        response = await sdk.conversation.send_and_wait(
            "alice",
            "support_agent",
            Query(text="How do I reset password?"),
            timeout=60.0
        )
        print(f"Response: {response.answer}")
    """

async def send_no_wait(
    sender_external_id: str,
    recipient_external_id: str,
    message: T,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Send message without waiting for response (non-blocking).
    
    Returns immediately. Recipient handler processes asynchronously.
    
    Args:
        sender_external_id: Sender's external ID
        recipient_external_id: Recipient's external ID
        message: Message payload
        metadata: Optional custom metadata
    
    Raises:
        ValueError: If parameters invalid
        AgentNotFoundError: If agents don't exist
    
    Example:
        await sdk.conversation.send_no_wait(
            "alice",
            "bob",
            TaskRequest(task="process_data")
        )
    """

async def end_conversation(
    agent_external_id: str,
    other_agent_external_id: str
) -> None:
    """
    End an active conversation session.
    
    Args:
        agent_external_id: One agent's external ID
        other_agent_external_id: Other agent's external ID
    
    Raises:
        SessionStateError: If session not found or already ended
    """

async def get_unread_messages(
    agent_external_id: str
) -> List[T]:
    """
    Get all unread messages for an agent.
    
    Returns:
        List of unread messages
    """

async def get_or_wait_for_response(
    agent_a_external_id: str,
    agent_b_external_id: str,
    timeout: Optional[float] = None
) -> Optional[T]:
    """
    Get response from active conversation or wait for one.
    
    Checks message queue first, then waits with timeout.
    
    Args:
        agent_a_external_id: First agent
        agent_b_external_id: Second agent
        timeout: Optional timeout in seconds
    
    Returns:
        Response message or None if timeout
    """

async def resume_agent_handler(
    agent_external_id: str
) -> None:
    """
    Resume handler execution for waiting agent.
    
    Used in async conversation pattern to trigger processing.
    
    Args:
        agent_external_id: Agent's external ID
    """

async def get_active_sessions(
    agent_external_id: str
) -> List[Dict[str, Any]]:
    """
    Get all active conversation sessions for an agent.
    
    Returns:
        List of session information dictionaries
    """

async def get_messages_in_session(
    session_id: str,
    include_read: bool = True
) -> List[Dict[str, Any]]:
    """
    Get all messages in a conversation session.
    
    Args:
        session_id: Session UUID
        include_read: Include read messages
    
    Returns:
        List of messages in chronological order
    """

async def get_conversation_history(
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Get full conversation history for a session.
    
    Args:
        session_id: Session UUID
    
    Returns:
        Complete conversation with all messages and metadata
    """

async def get_session_info(
    session_id: str
) -> Dict[str, Any]:
    """
    Get detailed information about a session.
    
    Includes participants, status, message counts, unread count.
    
    Args:
        session_id: Session UUID
    
    Returns:
        Session information dictionary
    """

async def get_session_statistics(
    agent_id: str
) -> Dict[str, Any]:
    """
    Get conversation statistics for an agent.
    
    Args:
        agent_id: Agent UUID or external ID
    
    Returns:
        Statistics including active sessions, unread count, total messages
    """
```

### MeetingManager[T]

Multi-agent turn-based meeting coordination.

```python
async def create_meeting(
    organizer_external_id: str,
    participant_external_ids: List[str],
    turn_duration: Optional[float] = None
) -> UUID:
    """
    Create a new meeting.
    
    Args:
        organizer_external_id: External ID of meeting organizer
        participant_external_ids: List of participant external IDs
        turn_duration: Optional duration per turn in seconds
    
    Returns:
        UUID of created meeting
    
    Raises:
        ValueError: If parameters invalid
        AgentNotFoundError: If organizer or participant not found
    
    Example:
        meeting_id = await sdk.meeting.create_meeting(
            "alice",
            ["bob", "charlie", "diana"],
            turn_duration=30.0
        )
    """

async def get_meeting(meeting_id: UUID) -> Optional[Meeting]:
    """
    Get meeting details.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        Meeting object or None if not found
    """

async def get_participants(meeting_id: UUID) -> List[MeetingParticipant]:
    """
    Get list of participants in meeting.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        List of participant objects with status and join info
    """

async def update_participant_status(
    meeting_id: UUID,
    agent_id: UUID,
    status: ParticipantStatus
) -> None:
    """
    Update participant status.
    
    Args:
        meeting_id: Meeting UUID
        agent_id: Agent UUID
        status: New participant status
    """

async def attend_meeting(
    agent_external_id: str,
    meeting_id: UUID
) -> bool:
    """
    Mark agent as attending meeting.
    
    Args:
        agent_external_id: Agent's external ID
        meeting_id: Meeting UUID
    
    Returns:
        True if joined successfully
    """

async def start_meeting(
    host_external_id: str,
    meeting_id: UUID
) -> None:
    """
    Start a meeting (organizer only).
    
    Begins turn-based speaking with first participant.
    
    Args:
        host_external_id: Organizer's external ID
        meeting_id: Meeting UUID
    
    Raises:
        MeetingPermissionError: If not organizer
        MeetingStateError: If meeting not in ready state
    """

async def speak(
    agent_external_id: str,
    meeting_id: UUID,
    message: T,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID:
    """
    Speak in meeting during your turn.
    
    Requires having the speaking turn (lock coordination).
    
    Args:
        agent_external_id: Agent's external ID
        meeting_id: Meeting UUID
        message: Message payload
        metadata: Optional custom metadata
    
    Returns:
        UUID of message
    
    Raises:
        NotYourTurnError: If agent doesn't have the turn
        MeetingNotActiveError: If meeting not active
    """

async def end_meeting(
    host_external_id: str,
    meeting_id: UUID
) -> None:
    """
    End a meeting (organizer only).
    
    Args:
        host_external_id: Organizer's external ID
        meeting_id: Meeting UUID
    
    Raises:
        MeetingPermissionError: If not organizer
    """

async def leave_meeting(
    agent_external_id: str,
    meeting_id: UUID
) -> None:
    """
    Leave a meeting.
    
    Args:
        agent_external_id: Agent's external ID
        meeting_id: Meeting UUID
    """

async def get_meeting_status(meeting_id: UUID) -> Optional[Dict]:
    """
    Get current meeting status.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        Meeting status information
    """

async def get_meeting_history(meeting_id: UUID) -> List[Dict]:
    """
    Get all messages in a meeting.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        Chronological list of messages
    """

async def get_meeting_details(meeting_id: str) -> Dict[str, Any]:
    """
    Get detailed meeting information.
    
    Includes participants, status, timing, message counts.
    
    Args:
        meeting_id: Meeting UUID as string
    
    Returns:
        Detailed meeting information
    """

async def get_participant_history(meeting_id: str) -> List[Dict[str, Any]]:
    """
    Get full participant history.
    
    Args:
        meeting_id: Meeting UUID as string
    
    Returns:
        List of all participants with join/leave times and status
    """

async def get_meeting_statistics(agent_id: str) -> Dict[str, Any]:
    """
    Get meeting statistics for an agent.
    
    Args:
        agent_id: Agent UUID or external ID
    
    Returns:
        Aggregate statistics for agent's meetings
    """

async def get_participation_analysis(meeting_id: str) -> Dict[str, Any]:
    """
    Get detailed participation analysis.
    
    Includes speaking time, message counts, participation rates per agent.
    
    Args:
        meeting_id: Meeting UUID as string
    
    Returns:
        Per-agent participation metrics
    """

async def get_meeting_timeline(meeting_id: str) -> Dict[str, Any]:
    """
    Get complete meeting timeline.
    
    Chronological view of all events and messages.
    
    Args:
        meeting_id: Meeting UUID as string
    
    Returns:
        Timeline with timestamps for all events
    """

async def get_turn_statistics(meeting_id: str) -> Dict[str, Any]:
    """
    Get turn-taking analysis.
    
    Turn counts, order, duration per agent.
    
    Args:
        meeting_id: Meeting UUID as string
    
    Returns:
        Per-agent turn statistics
    """
```

---

## Handler System

The Agent Messaging Protocol uses two distinct handler systems:

1. **Global Message Handlers** - Process message content (business logic)
2. **Instance Event Handlers** - React to meeting lifecycle events (integration logic)

For a comprehensive guide on when and how to use each system, see [Handler Systems Architecture](architecture/handler-systems.md).

### Global Message Handlers

Message handlers process the content of messages sent between agents. They are registered globally using decorators and apply to all SDK instances.

#### Available Handler Types

```python
from agent_messaging import (
    register_one_way_handler,
    register_conversation_handler,
    register_message_notification_handler,
    MessageContext
)
```

#### One-Way Message Handler

Handles fire-and-forget messages. The sender doesn't wait for a response.

```python
from typing import TypedDict

class Notification(TypedDict):
    title: str
    text: str
    priority: str

@register_one_way_handler
async def handle_notification(
    message: Notification,  # ← Type hint for IDE support
    context: MessageContext
) -> None:
    """
    Handle one-way notifications.
    
    Called asynchronously for each recipient. Return value is ignored.
    
    Args:
        message: The notification payload
        context: Message routing information
    """
    print(f"[{context.receiver_id}] Received from {context.sender_id}: {message['text']}")
```

#### Conversation Message Handler

Handles request-response messages. The sender blocks waiting for a response.

```python
from pydantic import BaseModel

class Query(BaseModel):
    question: str
    context: str = ""

class Response(BaseModel):
    answer: str
    confidence: float = 1.0

@register_conversation_handler
async def handle_query(
    message: Query,  # ← Type hint for request
    context: MessageContext
) -> Response:  # ← Type hint for response
    """
    Handle synchronous conversation (request-response).
    
    If response is returned within timeout, it's automatically sent.
    Otherwise, the handler continues async and sender times out.
    
    Args:
        message: The query payload
        context: Message routing information (includes session_id)
    
    Returns:
        Response payload to send back to sender
    """
    answer = process_question(message.question)
    return Response(answer=answer, confidence=0.95)
```

#### Message Notification Handler

Notifies agents when messages arrive while they're not actively waiting.

```python
@register_message_notification_handler
async def notify_agent(
    message: dict,
    context: MessageContext
) -> None:
    """
    Handle message arrival notifications.
    
    Called when a message arrives for an agent that is NOT currently
    locked/waiting (i.e., send_no_wait was used).
    
    Use this for push notifications, UI updates, etc.
    
    Args:
        message: The message payload
        context: Message routing information
    """
    send_push_notification(
        context.receiver_id,
        f"New message from {context.sender_id}"
    )
```

### Instance Event Handlers

Event handlers react to meeting lifecycle events. They are registered per-SDK-instance and allow different behaviors for different contexts.

#### Available Event Types

```python
from agent_messaging.models import MeetingEventType, MeetingEvent

MeetingEventType.MEETING_STARTED       # Meeting begins
MeetingEventType.MEETING_ENDED         # Meeting ends
MeetingEventType.TURN_CHANGED          # Speaking turn changes
MeetingEventType.PARTICIPANT_JOINED    # Agent joins meeting
MeetingEventType.PARTICIPANT_LEFT      # Agent leaves meeting
MeetingEventType.TIMEOUT_OCCURRED      # Speaker timeout
```

#### Registration Example

```python
async with AgentMessaging() as sdk:
    # Register event handler for this SDK instance
    async def on_meeting_started(event: MeetingEvent):
        """Called when a meeting starts."""
        print(f"Meeting {event.meeting_id} started!")
        print(f"Host: {event.data.host_id}")
        print(f"Participants: {event.data.participant_ids}")
    
    sdk._event_handler.register_handler(
        MeetingEventType.MEETING_STARTED,
        on_meeting_started
    )
    
    # Use SDK with event handlers
    meeting_id = await sdk.meeting.create_meeting("alice", ["bob"])
    await sdk.meeting.start_meeting("alice", meeting_id)
    # → Triggers on_meeting_started event
```

### Handler Type Safety

The SDK uses generic types at compile time but these are erased at runtime. **Use explicit type hints** for IDE support and static type checking:

#### ✅ Good: With Type Hints

```python
from typing import TypedDict

class Notification(TypedDict):
    type: str
    text: str

@register_one_way_handler
async def handle(message: Notification, context: MessageContext) -> None:
    # IDE knows message.text exists!
    print(message['text'])
```

#### ❌ Bad: Without Type Hints

```python
@register_one_way_handler
async def handle(message, context):
    # IDE doesn't know what 'message' contains
    # No autocomplete, no type checking
    print(message['text'])  # Might fail at runtime!
```

#### Pydantic for Runtime Validation

For runtime type checking, use Pydantic models:

```python
from pydantic import BaseModel

class Notification(BaseModel):
    text: str
    priority: str = "normal"

@register_one_way_handler
async def handle(message: dict, context: MessageContext) -> None:
    try:
        # Validate at runtime
        notif = Notification(**message)
        print(f"Valid: {notif.text}")
    except ValidationError as e:
        print(f"Invalid message: {e}")
```

### Handler Context

The `MessageContext` object provides routing information for all message handlers:

```python
from dataclasses import dataclass

@dataclass
class MessageContext:
    """Context passed to all message handlers."""
    
    sender_id: str                    # Sender's external ID
    receiver_id: str                  # Receiver's external ID
    organization_id: str              # Organization external ID
    handler_context: HandlerContext   # Which handler type (ONE_WAY, CONVERSATION, etc.)
    message_id: Optional[int]         # Message database ID
    session_id: Optional[str]         # Session ID (conversations only)
    meeting_id: Optional[int]         # Meeting ID (meetings only)
    metadata: dict[str, Any]          # Custom metadata
```

### Removed Handlers (v0.4.0)

The following handlers were removed in v0.4.0:

- ❌ `register_meeting_handler()` - Meeting messages are handled internally
- ❌ `register_system_handler()` - Never invoked, use event handlers instead
- ❌ `HandlerContext.MEETING` - Removed enum value
- ❌ `HandlerContext.SYSTEM` - Removed enum value

**Migration**: Use **instance event handlers** for meeting lifecycle events instead.

---

## Models and Data Types

### Organization Model

```python
from agent_messaging import Organization

class Organization:
    id: UUID                          # Internal UUID
    external_id: str                  # External identifier
    name: str                         # Organization name
    created_at: datetime              # Creation timestamp
    updated_at: datetime              # Last update timestamp
```

### Agent Model

```python
from agent_messaging import Agent

class Agent:
    id: UUID                          # Internal UUID
    external_id: str                  # External identifier
    organization_id: UUID             # Parent organization UUID
    name: str                         # Agent name
    created_at: datetime              # Creation timestamp
    updated_at: datetime              # Last update timestamp
```

### Session Model

```python
from agent_messaging import Session, SessionStatus

class Session:
    id: UUID                          # Session UUID
    agent_a_id: UUID                  # First agent
    agent_b_id: UUID                  # Second agent
    status: SessionStatus             # "active" | "waiting" | "ended"
    locked_agent_id: Optional[UUID]   # Agent holding lock
    created_at: datetime              # Creation time
    updated_at: datetime              # Last update time
    ended_at: Optional[datetime]      # End time if ended
```

### Meeting Model

```python
from agent_messaging import Meeting, MeetingStatus

class Meeting:
    id: UUID                          # Meeting UUID
    host_id: UUID                     # Organizer agent UUID
    status: MeetingStatus             # "created" | "ready" | "active" | "ended"
    current_speaker_id: Optional[UUID] # Agent with speaking turn
    turn_duration: Optional[float]    # Turn timeout in seconds
    turn_started_at: Optional[datetime] # When current turn started
    created_at: datetime              # Creation time
    started_at: Optional[datetime]    # Start time
    ended_at: Optional[datetime]      # End time
```

### MeetingParticipant Model

```python
from agent_messaging import MeetingParticipant, ParticipantStatus

class MeetingParticipant:
    id: UUID                          # Participant record UUID
    meeting_id: UUID                  # Meeting UUID
    agent_id: UUID                    # Agent UUID
    status: ParticipantStatus         # invited|attending|waiting|speaking|left
    join_order: int                   # Order for round-robin turns
    is_locked: bool                   # Has lock for speaking turn
    joined_at: Optional[datetime]     # Join timestamp
    left_at: Optional[datetime]       # Leave timestamp
```

### Message Model

```python
from agent_messaging import Message, MessageType

class Message(Generic[T]):
    id: UUID                          # Message UUID
    sender_id: UUID                   # Sender agent UUID
    recipient_id: Optional[UUID]      # Recipient agent UUID (one-way/conversation)
    session_id: Optional[UUID]        # Session UUID (conversations)
    meeting_id: Optional[UUID]        # Meeting UUID (meetings)
    message_type: MessageType         # Message type enum
    content: T                        # User-defined payload
    read_at: Optional[datetime]       # When message was read
    created_at: datetime              # Creation timestamp
    metadata: Optional[Dict]          # Optional custom metadata
```

### Message Type Enum

```python
from agent_messaging import MessageType

class MessageType(str, Enum):
    USER_DEFINED = "user_defined"    # Application message
    SYSTEM = "system"                # System message
    TIMEOUT = "timeout"              # Timeout notification
    ENDING = "ending"                # Session/meeting ending
```

### Meeting Event Models

```python
from agent_messaging import MeetingEventType, MeetingEventPayload

class MeetingEventType(str, Enum):
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
    TURN_CHANGED = "turn_changed"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    TIMEOUT_OCCURRED = "timeout_occurred"

class MeetingEventPayload:
    meeting_id: UUID
    event_type: MeetingEventType
    timestamp: datetime
    data: Dict[str, Any]             # Event-specific data
```

---

## Exceptions

### Exception Hierarchy

All exceptions inherit from `AgentMessagingError`.

```
AgentMessagingError (base)
├── AgentNotFoundError
├── OrganizationNotFoundError
├── SessionError
│   ├── SessionStateError
│   └── SessionLockError
├── MeetingError
│   ├── MeetingNotFoundError
│   ├── MeetingNotActiveError
│   ├── MeetingStateError
│   ├── NotYourTurnError
│   └── MeetingPermissionError
├── HandlerError
│   ├── NoHandlerRegisteredError
│   └── HandlerTimeoutError
├── TimeoutError
└── DatabaseError
```

### Exception Classes

```python
from agent_messaging import (
    AgentMessagingError,
    AgentNotFoundError,
    OrganizationNotFoundError,
    SessionError,
    SessionStateError,
    SessionLockError,
    MeetingError,
    MeetingNotFoundError,
    MeetingNotActiveError,
    MeetingStateError,
    NotYourTurnError,
    MeetingPermissionError,
    NoHandlerRegisteredError,
    HandlerTimeoutError,
    TimeoutError,
    DatabaseError
)

# Raised when agent doesn't exist
raise AgentNotFoundError("Agent 'alice' not found")

# Raised when organization doesn't exist
raise OrganizationNotFoundError("Organization 'org_001' not found")

# Raised when session in invalid state
raise SessionStateError("Session already ended")

# Raised when lock acquisition fails
raise SessionLockError("Failed to acquire session lock")

# Raised when no handler registered
raise NoHandlerRegisteredError("No handler for one-way messages")

# Raised when handler exceeds timeout
raise HandlerTimeoutError("Handler timed out after 30s")

# Raised when operation exceeds timeout
raise TimeoutError("Response not received within 30s")

# Raised for database errors
raise DatabaseError("Connection pool exhausted")

# Meeting-specific exceptions
raise MeetingNotFoundError("Meeting not found")
raise MeetingNotActiveError("Meeting is not active")
raise NotYourTurnError("It's not your turn to speak")
raise MeetingPermissionError("Only organizer can start meeting")
```

---

## Configuration

### Config Class

```python
from agent_messaging import Config, DatabaseConfig, MessagingConfig

# Create configuration programmatically
config = Config(
    database=DatabaseConfig(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        database="agent_messaging",
        max_pool_size=20
    ),
    messaging=MessagingConfig(
        default_sync_timeout=30.0,
        default_meeting_turn_duration=60.0,
        handler_timeout=30.0
    ),
    debug=False,
    log_level="INFO"
)

# Or load from environment variables
config = Config()  # Loads POSTGRES_*, HANDLER_*, etc.
```

### DatabaseConfig

```python
class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "agent_messaging"
    max_pool_size: int = 20
    min_pool_size: int = 5
    connect_timeout_sec: int = 10
    
    @property
    def dsn(self) -> str:
        """PostgreSQL DSN string for connection."""
        return f"postgres://{user}:{password}@{host}:{port}/{database}"
```

### MessagingConfig

```python
class MessagingConfig(BaseModel):
    default_sync_timeout: float = 30.0
    default_meeting_turn_duration: float = 60.0
    handler_timeout: float = 30.0
```

### Environment Variables

```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DATABASE=agent_messaging
POSTGRES_MAX_POOL_SIZE=20
POSTGRES_MIN_POOL_SIZE=5
POSTGRES_CONNECT_TIMEOUT_SEC=10

# Messaging Timeouts
DEFAULT_SYNC_TIMEOUT=30.0
DEFAULT_MEETING_TURN_DURATION=60.0
HANDLER_TIMEOUT=30.0

# Logging
DEBUG=false
LOG_LEVEL=INFO
```

---

## Examples

### Example 1: One-Way Notifications

```python
import asyncio
from agent_messaging import (
    AgentMessaging,
    register_one_way_handler,
    MessageContext
)

@register_one_way_handler
async def handle_notification(message: dict, context: MessageContext) -> None:
    print(f"{context.sender_id} → {context.receiver_id}: {message['text']}")

async def main():
    async with AgentMessaging[dict, dict, dict]() as sdk:
        # Setup
        await sdk.register_organization("acme", "Acme Corp")
        await sdk.register_agent("alice", "acme", "Alice")
        await sdk.register_agent("bob", "acme", "Bob")
        
        # Send notification
        await sdk.one_way.send(
            "alice",
            ["bob"],
            {"text": "System maintenance at 3 PM"}
        )

asyncio.run(main())
```

### Example 2: Synchronous Conversations

```python
import asyncio
from agent_messaging import (
    AgentMessaging,
    register_conversation_handler,
    MessageContext
)

@register_conversation_handler
async def handle_query(message: dict, context: MessageContext) -> dict:
    return {
        "answer": f"Answer to: {message['question']}"
    }

async def main():
    async with AgentMessaging[dict, dict, dict]() as sdk:
        # Setup
        await sdk.register_organization("acme", "Acme Corp")
        await sdk.register_agent("alice", "acme", "Alice")
        await sdk.register_agent("support", "acme", "Support Agent")
        
        # Send request and wait for response
        response = await sdk.conversation.send_and_wait(
            "alice",
            "support",
            {"question": "How do I reset my password?"},
            timeout=60.0
        )
        print(f"Response: {response['answer']}")

asyncio.run(main())
```

### Example 3: Multi-Agent Meetings

```python
import asyncio
from agent_messaging import (
    AgentMessaging,
    register_meeting_handler,
    MessageContext,
    MeetingEventType
)

@register_meeting_handler
async def handle_meeting_turn(message: dict, context: MessageContext) -> dict:
    return {"contribution": f"My thoughts on {message['topic']}..."}

async def main():
    async with AgentMessaging[dict, dict, dict]() as sdk:
        # Setup
        await sdk.register_organization("acme", "Acme Corp")
        await sdk.register_agent("alice", "acme", "Alice")
        await sdk.register_agent("bob", "acme", "Bob")
        await sdk.register_agent("charlie", "acme", "Charlie")
        
        # Create and start meeting
        meeting_id = await sdk.meeting.create_meeting(
            "alice",
            ["bob", "charlie"],
            turn_duration=30.0
        )
        
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)
        
        # Speak
        await sdk.meeting.speak("alice", meeting_id, {"topic": "Q4 Planning"})
        # ... bob and charlie speak in their turns
        
        # End meeting
        await sdk.meeting.end_meeting("alice", meeting_id)

asyncio.run(main())
```

---

## Best Practices

### 1. Always use async context manager

```python
# ✅ Good
async with AgentMessaging[dict, dict, dict]() as sdk:
    await sdk.register_organization("org", "Org")

# ❌ Bad - resources not cleaned up
sdk = AgentMessaging[dict, dict, dict]()
# ... use sdk
```

### 2. Register handlers before creating SDK

```python
# ✅ Good
@register_one_way_handler
async def my_handler(msg, ctx):
    pass

async with AgentMessaging[dict, dict, dict]() as sdk:
    await sdk.one_way.send(...)
```

### 3. Use timeout values for conversation waits

```python
# ✅ Good - timeout specified
try:
    response = await sdk.conversation.send_and_wait(
        "alice", "bob",
        message,
        timeout=30.0  # Explicit timeout
    )
except TimeoutError:
    print("No response received")

# ⚠️ Caution - long timeout
response = await sdk.conversation.send_and_wait(
    "alice", "bob",
    message,
    timeout=300.0  # 5 minute wait!
)
```

### 4. Handle exceptions appropriately

```python
from agent_messaging import (
    AgentNotFoundError,
    NoHandlerRegisteredError,
    TimeoutError
)

try:
    await sdk.one_way.send("alice", ["bob"], message)
except AgentNotFoundError:
    print("One of the agents doesn't exist")
except NoHandlerRegisteredError:
    print("No handler registered for this message type")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 5. Use metadata for tracking

```python
# Store request ID for correlation
import uuid
request_id = str(uuid.uuid4())

await sdk.one_way.send(
    "alice",
    ["bob"],
    message,
    metadata={"request_id": request_id, "priority": "high"}
)

# Later search and filter by metadata
results = await sdk.search_messages(
    "query_text",
    metadata_filter={"priority": "high"}
)
```

### 6. Validate agent existence before operations

```python
try:
    agent = await sdk.get_agent("alice")
except AgentNotFoundError:
    print("Agent not registered yet")
    agent_id = await sdk.register_agent("alice", "org_id", "Alice")
```

### 7. Use conversation sessions for related messages

```python
# For multiple back-and-forth messages, use same session
session = await sdk.conversation.send_and_wait(...)
# Both messages are part of same session automatically
```

### 8. Monitor meeting events

```python
@sdk.register_event_handler(MeetingEventType.TURN_CHANGED)
async def on_turn_changed(event):
    print(f"Turn changed: {event.data['current_speaker_id']}")

@sdk.register_event_handler(MeetingEventType.TIMEOUT_OCCURRED)
async def on_timeout(event):
    print(f"Agent timed out: {event.data['timed_out_agent_id']}")
```

---

## Changelog

### v0.3.1 (Current - December 16, 2025)

**New Features:**
- ✨ **Automatic Schema Initialization** - Database schema is now automatically initialized on SDK startup
  - Enabled by default for improved developer experience
  - Fully idempotent - safe to call multiple times
  - Can be disabled via `Config(auto_initialize_schema=False)` or `AUTO_INITIALIZE_SCHEMA=false`
  - Works with all deployment scenarios (Docker, Kubernetes, local development)
- ✅ Backward compatible - `scripts/init_db.py` still works for manual initialization

### v0.3.0 (December 2025)

**Features:**
- ✅ Four communication patterns (one-way, sync conversation, async conversation, meetings)
- ✅ Multi-agent turn-based meeting coordination
- ✅ PostgreSQL-backed persistence with psqlpy
- ✅ Handler registration system with global handlers
- ✅ Event system for meeting lifecycle
- ✅ Message metadata and filtering
- ✅ Full-text search with PostgreSQL
- ✅ Advanced analytics (participation, timeline, turn statistics)
- ✅ Comprehensive error handling
- ✅ Async-first architecture

**Improvements:**
- Phase 11: Unified Conversation class (sync and async)
- Phase 10: Major refactoring and optimization
- Phase 5-7: Core features and resilience
- Phase 4: Advanced features (metadata, filtering, search)

### v0.1.0-0.2.0

Foundation phases with core architecture and messaging patterns.

---

## Support and Documentation

- **README**: See `README.md` for quick start
- **Quick Start**: See `docs/quick-start.md` for tutorials
- **Examples**: See `examples/` for working examples
- **Testing**: See `tests/` for comprehensive test coverage
- **GitHub**: Report issues at https://github.com/Ganzzi/agent_messaging

---

**Last Updated:** December 16, 2025  
**Status:** Production Ready  
**Version:** v0.3.0
