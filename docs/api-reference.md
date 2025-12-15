# Agent Messaging Protocol - API Reference

## Table of Contents

- [AgentMessaging Class](#agentmessaging-class)
- [OneWayMessenger](#onewaymessenger)
- [Conversation](#conversation)
- [MeetingManager](#meetingmanager)
- [Exceptions](#exceptions)
- [Models](#models)

---

## AgentMessaging Class

The main SDK entry point for all messaging operations.

### Constructor

```python
AgentMessaging[T](config: Optional[Config] = None) -> AgentMessaging[T]
```

**Parameters:**
- `config` (Optional[Config]): Configuration object. If None, loads from environment variables.

**Generic Type:**
- `T`: User-defined message type (must be JSON-serializable or Pydantic model)

### Context Manager Methods

```python
async def __aenter__(self) -> AgentMessaging[T]
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

Initialize and cleanup database connections. Always use as async context manager.

### Organization Management

```python
async def register_organization(
    external_id: str,
    name: str
) -> str
```

Register a new organization.

**Parameters:**
- `external_id` (str): Unique external identifier
- `name` (str): Human-readable name

**Returns:** Organization UUID

**Raises:** ValueError, DatabaseError

```python
async def get_organization(external_id: str) -> Organization
```

Get organization by external ID.

**Parameters:**
- `external_id` (str): Organization external ID

**Returns:** Organization model

**Raises:** ValueError, OrganizationNotFoundError

### Agent Management

```python
async def register_agent(
    external_id: str,
    organization_external_id: str,
    name: str
) -> str
```

Register a new agent.

**Parameters:**
- `external_id` (str): Unique agent external identifier
- `organization_external_id` (str): Parent organization external ID
- `name` (str): Human-readable agent name

**Returns:** Agent UUID

**Raises:** ValueError, OrganizationNotFoundError, DatabaseError

```python
async def get_agent(external_id: str) -> Agent
```

Get agent by external ID.

**Parameters:**
- `external_id` (str): Agent external ID

**Returns:** Agent model

**Raises:** ValueError, AgentNotFoundError

```python
async def deregister_organization(external_id: str) -> bool
```

Deregister (delete) an organization.

**WARNING:** This will cascade delete all related agents, sessions, messages, and meetings associated with this organization due to foreign key constraints. Use with caution in production environments.

**Parameters:**
- `external_id` (str): Organization external ID

**Returns:** True if organization was deleted, False if not found

**Raises:** ValueError

```python
async def deregister_agent(external_id: str) -> bool
```

Deregister (delete) an agent.

**WARNING:** This will cascade delete all related sessions, messages, and meeting participations associated with this agent due to foreign key constraints. Use with caution in production environments.

**Parameters:**
- `external_id` (str): Agent external ID

**Returns:** True if agent was deleted, False if not found

**Raises:** ValueError

### Handler Registration

The Agent Messaging SDK provides different handler types for different messaging patterns. Each handler type is designed for a specific communication pattern and has distinct behavior.

#### Overview of Handler Types

1. **One-Way Handlers** - For fire-and-forget notifications (no response expected)
2. **Conversation Handlers** - For request-response messaging (response required)
3. **Meeting Handlers** - For turn-based multi-agent meetings
4. **System Handlers** - For internal system events (timeouts, errors, etc.)
5. **Event Handlers** - For meeting lifecycle events (started, ended, turn changed, etc.)

#### One-Way Handler Registration

```python
def register_one_way_handler(agent_external_id: str) -> Callable
```

Register a one-way message handler for an agent. One-way handlers process fire-and-forget messages where no response is expected. The handler is invoked asynchronously and the sender does not wait for completion.

**Parameters:**
- `agent_external_id` (str): The agent's external ID

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(message: T, context: HandlerContext) -> None:
    # Process notification, no return value needed
    pass
```

**Use Cases:**
- Notifications and alerts
- Broadcasting updates
- Logging and monitoring
- Event notifications

**Example:**
```python
@sdk.register_one_way_handler("notification_agent")
async def handle_notification(message: dict, context: HandlerContext):
    print(f"Notification received: {message['title']}")
    # No return value - fire and forget
```

#### Conversation Handler Registration

```python
def register_conversation_handler(agent_external_id: str) -> Callable
```

Register a conversation handler for an agent. Conversation handlers process request-response messages where the sender blocks and waits for the handler's response. This is synchronous from the sender's perspective.

**Parameters:**
- `agent_external_id` (str): The agent's external ID

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(message: T, context: HandlerContext) -> T:
    # Process request and return response
    return response_message
```

**Use Cases:**
- Request-response patterns
- API-like interactions
- Q&A and support systems
- Task processing with results

**Example:**
```python
@sdk.register_conversation_handler("support_agent")
async def handle_query(message: dict, context: HandlerContext) -> dict:
    question = message['question']
    answer = await process_question(question)
    return {"answer": answer}  # Sender receives this response
```

#### Meeting Handler Registration

```python
def register_meeting_handler(agent_external_id: str) -> Callable
```

Register a meeting handler for an agent. Meeting handlers process messages during active meetings when it's the agent's turn to speak. The handler is invoked in the context of a multi-agent meeting with turn-based coordination.

**Parameters:**
- `agent_external_id` (str): The agent's external ID

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(message: T, context: HandlerContext) -> Optional[T]:
    # Process meeting message and optionally return response
    return response_message  # Optional
```

**Use Cases:**
- Multi-agent discussions
- Round-robin collaboration
- Brainstorming sessions
- Panel discussions

**Example:**
```python
@sdk.register_meeting_handler("participant_agent")
async def handle_meeting_turn(message: dict, context: HandlerContext) -> dict:
    meeting_id = context.meeting_id
    # Process meeting message
    return {"contribution": "My thoughts are..."}
```

#### System Handler Registration

```python
def register_system_handler() -> Callable
```

Register a global system message handler. System handlers process internal messages like timeouts, errors, and system events. This is a global handler (not agent-specific) that receives system-level notifications.

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(message: dict, context: HandlerContext) -> None:
    # Process system message
    pass
```

**Use Cases:**
- Timeout notifications
- Error handling and recovery
- System monitoring
- Health checks

**Example:**
```python
@sdk.register_system_handler()
async def handle_system_event(message: dict, context: HandlerContext) -> None:
    if message.get("type") == "timeout":
        logger.warning(f"Agent {context.recipient_external_id} timed out")
    elif message.get("type") == "error":
        logger.error(f"System error: {message.get('error')}")
```

#### Event Handler Registration

```python
def register_event_handler(event_type: MeetingEventType) -> Callable
```

Register an event handler for meeting lifecycle events. Event handlers are invoked when specific meeting events occur (meeting started, turn changed, meeting ended, etc.). These are type-safe handlers that receive structured event data.

**Parameters:**
- `event_type` (MeetingEventType): Type of meeting event to handle
  - `MEETING_STARTED` - Meeting has begun
  - `TURN_CHANGED` - Speaking turn has changed
  - `TURN_TIMEOUT` - Current speaker exceeded time limit
  - `PARTICIPANT_JOINED` - New participant joined
  - `PARTICIPANT_LEFT` - Participant left meeting
  - `MEETING_ENDED` - Meeting has concluded
  - `MEETING_ERROR` - Error occurred in meeting

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(event: MeetingEvent) -> None:
    # event.meeting_id: UUID
    # event.timestamp: datetime
    # event.data: Type-safe event data (varies by event type)
    pass
```

**Use Cases:**
- Meeting orchestration
- Participant monitoring
- Meeting analytics
- Automated facilitation

**Example:**
```python
from agent_messaging.handlers import MeetingEventType
from agent_messaging.models import TurnChangedEventData

@sdk.register_event_handler(MeetingEventType.TURN_CHANGED)
async def on_turn_changed(event: MeetingEvent):
    data: TurnChangedEventData = event.data
    print(f"Meeting {event.meeting_id}: Turn changed")
    print(f"Previous: {data.previous_speaker_id}")
    print(f"Current: {data.current_speaker_id}")

@sdk.register_event_handler(MeetingEventType.MEETING_ENDED)
async def on_meeting_ended(event: MeetingEvent):
    print(f"Meeting {event.meeting_id} has ended")
```

#### Handler Context

All handlers receive a `HandlerContext` object with information about the message:

```python
class HandlerContext:
    sender_external_id: str          # Who sent the message
    recipient_external_id: str       # Who is receiving
    session_id: Optional[UUID]       # Conversation session ID
    meeting_id: Optional[UUID]       # Meeting ID (for meetings)
    message_type: str                # Type of message
```

#### Checking Handler Registration

```python
def has_handler() -> bool
```

Check if any handler is registered.

**Returns:** True if at least one handler is registered

### Messaging Properties

```python
@property
def one_way(self) -> OneWayMessenger[T]
```

One-way messaging interface.

```python
@property
def conversation(self) -> Conversation[T]
```

Unified conversation interface (sync and async patterns).

```python
@property
def meeting(self) -> MeetingManager[T]
```

Meeting management interface.

---

## OneWayMessenger

Fire-and-forget messaging for one-to-many notifications.

### Constructor

```python
OneWayMessenger[T](
    handler_registry: HandlerRegistry,
    message_repo: MessageRepository,
    agent_repo: AgentRepository
)
```

### Methods

```python
async def send(
    sender_external_id: str,
    recipient_external_ids: List[str],
    message: T,
    metadata: Optional[Dict[str, Any]] = None
) -> List[str]
```

Send one-way message to multiple recipients (broadcast).

**Parameters:**
- `sender_external_id` (str): Sender external ID
- `recipient_external_ids` (List[str]): List of recipient external IDs
- `message` (T): Message content
- `metadata` (Optional[Dict[str, Any]]): Optional custom metadata to attach (for tracking, filtering, etc.)

**Returns:** List of message UUIDs (one per recipient)

**Raises:** ValueError, AgentNotFoundError, NoHandlerRegisteredError

**Example:**
```python
message_ids = await sdk.one_way.send(
    sender_external_id="notification_service",
    recipient_external_ids=["alice", "bob"],
    message={"type": "alert", "content": "System update"},
    metadata={"priority": "high", "request_id": "req-123"}
)
```

**Architecture Note:** Updated to support one-to-many pattern. Handlers are invoked
concurrently for all recipients.

### Query Methods

```python
async def get_sent_messages(
    sender_external_id: str,
    limit: int = 100,
    offset: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]
```

Get one-way messages sent by an agent.

**Parameters:**
- `sender_external_id` (str): External ID of sender agent
- `limit` (int): Maximum number of messages to return (default: 100)
- `offset` (int): Offset for pagination (default: 0)
- `date_from` (Optional[datetime]): Optional start date filter (inclusive)
- `date_to` (Optional[datetime]): Optional end date filter (inclusive)

**Returns:** List of message dictionaries with sender/recipient info and content

**Response Structure:**
```python
[
    {
        "message_id": str,
        "sender_id": str,
        "recipient_id": str,
        "content": dict,
        "read_at": Optional[datetime],
        "created_at": datetime,
        "metadata": dict
    },
    ...
]
```

**Raises:** ValueError, AgentNotFoundError

**Example:**
```python
messages = await sdk.one_way.get_sent_messages("alice")
recent = await sdk.one_way.get_sent_messages(
    "alice",
    date_from=datetime(2025, 1, 1),
    date_to=datetime(2025, 1, 31)
)
```

```python
async def get_received_messages(
    recipient_external_id: str,
    include_read: bool = True,
    limit: int = 100,
    offset: int = 0,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]
```

Get one-way messages received by an agent.

**Parameters:**
- `recipient_external_id` (str): External ID of recipient agent
- `include_read` (bool): Include already-read messages (default: True)
- `limit` (int): Maximum number of messages to return (default: 100)
- `offset` (int): Offset for pagination (default: 0)
- `date_from` (Optional[datetime]): Optional start date filter (inclusive)
- `date_to` (Optional[datetime]): Optional end date filter (inclusive)

**Returns:** List of message dictionaries with sender/recipient info and content

**Response Structure:** Same as `get_sent_messages`

**Raises:** ValueError, AgentNotFoundError

**Example:**
```python
all_messages = await sdk.one_way.get_received_messages("bob")
unread = await sdk.one_way.get_received_messages(
    "bob",
    include_read=False
)
```

```python
async def mark_messages_read(
    recipient_external_id: str,
    sender_external_id: Optional[str] = None
) -> int
```

Mark one-way messages as read for a recipient.

**Parameters:**
- `recipient_external_id` (str): External ID of recipient agent
- `sender_external_id` (Optional[str]): If provided, only mark messages from this sender as read

**Returns:** Number of messages marked as read

**Raises:** ValueError, AgentNotFoundError

**Example:**
```python
# Mark all received messages as read
count = await sdk.one_way.mark_messages_read("bob")

# Mark messages from specific sender as read
count = await sdk.one_way.mark_messages_read("bob", sender_external_id="alice")
```

```python
async def get_message_count(
    agent_external_id: str,
    role: str = "recipient",
    read_status: Optional[bool] = None
) -> int
```

Get count of one-way messages for an agent.

**Parameters:**
- `agent_external_id` (str): Agent external ID
- `role` (str): Either "sender" or "recipient" (default: "recipient")
- `read_status` (Optional[bool]): Filter by read status (None = all, True = read only, False = unread only)

**Returns:** Count of messages matching criteria

**Raises:** ValueError, AgentNotFoundError

**Example:**
```python
# Total received messages
total = await sdk.one_way.get_message_count("bob")

# Unread messages
unread = await sdk.one_way.get_message_count("bob", read_status=False)

# Messages sent by alice
sent = await sdk.one_way.get_message_count("alice", role="sender")
```

---

## Conversation

Unified conversation class supporting both sync and async messaging patterns.

### Constructor

```python
Conversation[T](
    handler_registry: HandlerRegistry,
    message_repo: MessageRepository,
    session_repo: SessionRepository,
    agent_repo: AgentRepository
)
```

### Methods

```python
async def send_and_wait(
    sender_external_id: str,
    recipient_external_id: str,
    message: T,
    timeout: float = 30.0,
    metadata: Optional[Dict[str, Any]] = None
) -> T
```

Send message and block until response (synchronous pattern).

**Parameters:**
- `sender_external_id` (str): Sender external ID
- `recipient_external_id` (str): Recipient external ID
- `message` (T): Request message
- `timeout` (float): Max wait time in seconds (default: 30.0)
- `metadata` (Optional[Dict[str, Any]]): Optional custom metadata to attach

**Returns:** Response message

**Raises:** ValueError, AgentNotFoundError, NoHandlerRegisteredError, TimeoutError, SessionStateError

**Example:**
```python
response = await sdk.conversation.send_and_wait(
    sender_external_id="customer",
    recipient_external_id="support_agent",
    message=SupportQuery(question="How do I reset my password?"),
    timeout=60.0,
    metadata={"request_id": "req-123", "priority": "high"}
)
```

```python
async def send_no_wait(
    sender_external_id: str,
    recipient_external_id: str,
    message: T,
    metadata: Optional[Dict[str, Any]] = None
) -> None
```

Send message without blocking (asynchronous pattern).

**Parameters:**
- `sender_external_id` (str): Sender external ID
- `recipient_external_id` (str): Recipient external ID
- `message` (T): Message content
- `metadata` (Optional[Dict[str, Any]]): Optional custom metadata to attach

**Raises:** ValueError, AgentNotFoundError

**Example:**
```python
await sdk.conversation.send_no_wait(
    sender_external_id="alice",
    recipient_external_id="bob",
    message=ChatMessage(text="Hello Bob!"),
    metadata={"message_type": "greeting"}
)
```

```python
async def get_unread_messages(
    agent_external_id: str
) -> List[T]
```

Get all unread messages for an agent.

**Parameters:**
- `agent_external_id` (str): Agent external ID

**Returns:** List of unread messages

**Raises:** AgentNotFoundError

```python
async def get_or_wait_for_response(
    agent_external_id: str,
    other_agent_external_id: str,
    timeout: Optional[float] = None
) -> Optional[T]
```

Check for messages from specific agent, wait if none available.

**Parameters:**
- `agent_external_id` (str): Receiving agent external ID
- `other_agent_external_id` (str): Sending agent external ID
- `timeout` (Optional[float]): Max wait time (None = wait forever)

**Returns:** Message content or None if timeout

**Raises:** AgentNotFoundError, TimeoutError

```python
async def end_conversation(
    agent_a_external_id: str,
    agent_b_external_id: str
) -> None
```

End conversation between two agents.

**Parameters:**
- `agent_a_external_id` (str): First agent external ID
- `agent_b_external_id` (str): Second agent external ID

**Raises:** ValueError, AgentNotFoundError, RuntimeError

```python
async def resume_agent_handler(
    agent_external_id: str
) -> None
```

Resume agent handler for system recovery (process unread messages).

**Parameters:**
- `agent_external_id` (str): Agent external ID

**Raises:** AgentNotFoundError

**Architecture Note:** Unified SyncConversation and AsyncConversation into single
Conversation class. Sessions intelligently handle both blocking waits and message
queues based on the method called.

### Query Methods

```python
async def get_conversation_history(
    session_id: str
) -> List[Dict[str, Any]]
```

Get full conversation history with formatted message details.

**Parameters:**
- `session_id` (str): Session ID (UUID as string)

**Returns:** List of messages with sender info, timestamps, and content

**Raises:** ValueError

**Example:**
```python
history = await sdk.conversation.get_conversation_history(session_id)
for msg in history:
    print(f"{msg['sender_id']}: {msg['content']}")
```

```python
async def get_session_info(
    session_id: str
) -> Dict[str, Any]
```

Get detailed session information including statistics.

**Parameters:**
- `session_id` (str): Session ID (UUID as string)

**Returns:** Dictionary with session details, participants, and message counts

**Response Structure:**
```python
{
    "session_id": str,
    "agent_a": {"id": str, "name": str},
    "agent_b": {"id": str, "name": str},
    "status": str,
    "is_locked": bool,
    "locked_by": Optional[str],
    "message_count": int,
    "read_count": int,
    "unread_count": int,
    "created_at": datetime,
    "updated_at": datetime,
    "ended_at": Optional[datetime]
}
```

**Raises:** ValueError

**Example:**
```python
info = await sdk.conversation.get_session_info(session_id)
print(f"Status: {info['status']}")
print(f"Unread: {info['unread_count']}")
```

```python
async def get_session_statistics(
    agent_id: str
) -> Dict[str, Any]
```

Get message statistics for an agent across all sessions.

**Parameters:**
- `agent_id` (str): Agent external ID

**Returns:** Dictionary with conversation statistics

**Response Structure:**
```python
{
    "agent_id": str,
    "total_conversations": int,
    "total_messages": int,
    "unread_count": int,
    "sent_count": int,
    "received_count": int,
    "unique_conversation_partners": int
}
```

**Raises:** AgentNotFoundError

**Example:**
```python
stats = await sdk.conversation.get_session_statistics("alice")
print(f"Alice has {stats['total_conversations']} conversations")
print(f"Total messages sent: {stats['sent_count']}")
```

---

## MeetingManager

Multi-agent meetings with turn-based coordination.

### Constructor

```python
MeetingManager[T](
    meeting_repo: MeetingRepository,
    message_repo: MessageRepository,
    agent_repo: AgentRepository,
    event_handler: MeetingEventHandler
)
```


### Methods

```python
async def create_meeting(
    organizer_external_id: str,
    participant_external_ids: List[str],
    turn_duration: Optional[float] = None
) -> UUID
```

Create new meeting.

**Parameters:**
- `organizer_external_id` (str): Organizer external ID
- `participant_external_ids` (List[str]): Participant external IDs
- `turn_duration` (Optional[float]): Seconds per turn

**Returns:** Meeting UUID

**Raises:** AgentNotFoundError

```python
async def attend_meeting(
    agent_external_id: str,
    meeting_id: UUID
) -> bool
```

Join meeting as participant.

**Parameters:**
- `agent_external_id` (str): Agent external ID
- `meeting_id` (UUID): Meeting UUID

**Returns:** True if joined successfully

**Raises:** AgentNotFoundError, MeetingNotFoundError

```python
async def start_meeting(
    organizer_external_id: str,
    meeting_id: UUID,
    initial_message: Optional[T] = None,
    next_speaker: Optional[str] = None
) -> None
```

Start meeting.

**Parameters:**
- `organizer_external_id` (str): Organizer external ID
- `meeting_id` (UUID): Meeting UUID
- `initial_message` (Optional[T]): Opening message
- `next_speaker` (Optional[str]): First speaker external ID

**Raises:** MeetingPermissionError, MeetingNotFoundError

```python
async def speak(
    speaker_external_id: str,
    meeting_id: UUID,
    message: T,
    next_speaker: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> UUID
```

Speak in meeting (when it's your turn).

**Parameters:**
- `speaker_external_id` (str): Speaker external ID
- `meeting_id` (UUID): Meeting UUID
- `message` (T): Message content
- `next_speaker` (Optional[str]): Next speaker external ID
- `metadata` (Optional[Dict[str, Any]]): Optional custom metadata to attach

**Returns:** Message UUID

**Raises:** ValueError, AgentNotFoundError, MeetingError, MeetingNotFoundError

**Example:**
```python
message_id = await sdk.meeting.speak(
    speaker_external_id="alice",
    meeting_id=meeting_id,
    message=ContributionMessage(text="I think we should..."),
    next_speaker="bob",
    metadata={"speaking_duration": 45.2}
)
```

```python
async def pass_turn(
    agent_external_id: str,
    meeting_id: UUID
) -> None
```

Pass turn to next participant.

**Parameters:**
- `agent_external_id` (str): Current speaker external ID
- `meeting_id` (UUID): Meeting UUID

**Raises:** MeetingError, MeetingNotFoundError

```python
async def end_meeting(
    organizer_external_id: str,
    meeting_id: UUID
) -> None
```

End meeting (organizer only).

**Parameters:**
- `organizer_external_id` (str): Organizer external ID
- `meeting_id` (UUID): Meeting UUID

**Raises:** MeetingPermissionError, MeetingNotFoundError

```python
async def get_meeting_status(meeting_id: UUID) -> Dict[str, Any]
```

Get meeting status and participants.

**Parameters:**
- `meeting_id` (UUID): Meeting UUID

**Returns:** Status dictionary with participants, current speaker, etc.

**Raises:** MeetingNotFoundError

```python
async def get_meeting_history(meeting_id: UUID) -> List[Dict[str, Any]]
```

Get meeting message history.

**Parameters:**
- `meeting_id` (UUID): Meeting UUID

**Returns:** List of message dictionaries

**Raises:** MeetingNotFoundError

### Query Methods

```python
async def get_meeting_details(
    meeting_id: str
) -> Dict[str, Any]
```

Get detailed meeting information including participants and statistics.

**Parameters:**
- `meeting_id` (str): Meeting ID (UUID as string)

**Returns:** Dictionary with meeting details and current status

**Response Structure:**
```python
{
    "meeting_id": str,
    "host": {"id": str, "name": str},
    "status": str,
    "current_speaker": Optional[{"id": str, "name": str}],
    "turn_duration_seconds": Optional[float],
    "turn_started_at": Optional[datetime],
    "created_at": datetime,
    "started_at": Optional[datetime],
    "ended_at": Optional[datetime],
    "participant_count": int,
    "attending_count": int,
    "message_count": int
}
```

**Raises:** ValueError, MeetingNotFoundError

**Example:**
```python
details = await sdk.meeting.get_meeting_details(meeting_id)
print(f"Host: {details['host']['name']}")
print(f"Status: {details['status']}")
print(f"Participants: {details['participant_count']}")
```

```python
async def get_participant_history(
    meeting_id: str
) -> List[Dict[str, Any]]
```

Get full participant history for a meeting.

**Parameters:**
- `meeting_id` (str): Meeting ID (UUID as string)

**Returns:** List of participants with detailed information

**Response Structure:**
```python
[
    {
        "participant_id": str,
        "agent_id": str,
        "agent_name": str,
        "status": str,
        "join_order": int,
        "is_locked": bool,
        "joined_at": Optional[datetime],
        "left_at": Optional[datetime]
    },
    ...
]
```

**Raises:** ValueError, MeetingNotFoundError

**Example:**
```python
participants = await sdk.meeting.get_participant_history(meeting_id)
for p in participants:
    print(f"{p['agent_name']} (order: {p['join_order']})")
```

```python
async def get_meeting_statistics(
    agent_id: str
) -> Dict[str, Any]
```

Get meeting statistics for an agent (as organizer or participant).

**Parameters:**
- `agent_id` (str): Agent external ID

**Returns:** Dictionary with meeting statistics

**Response Structure:**
```python
{
    "agent_id": str,
    "hosted_meetings": int,
    "participated_meetings": int,
    "active_hosted": int,
    "total_messages_sent": int,
    "meetings_spoke_in": int,
    "avg_meeting_duration_seconds": Optional[float]
}
```

**Raises:** AgentNotFoundError

**Example:**
```python
stats = await sdk.meeting.get_meeting_statistics("alice")
print(f"Hosted meetings: {stats['hosted_meetings']}")
print(f"Avg duration: {stats['avg_meeting_duration_seconds']}s")
```

---

## Exceptions

### Base Exceptions

```python
class AgentMessagingError(Exception):
    """Base exception for all SDK errors."""
    pass
```

### Organization Exceptions

```python
class OrganizationNotFoundError(AgentMessagingError):
    """Organization not found."""
    pass
```

### Agent Exceptions

```python
class AgentNotFoundError(AgentMessagingError):
    """Agent not found."""
    pass
```

### Handler Exceptions

```python
class NoHandlerRegisteredError(AgentMessagingError):
    """No handler registered for agent."""
    pass

class HandlerTimeoutError(AgentMessagingError):
    """Handler execution timed out."""
    pass

class HandlerError(AgentMessagingError):
    """Handler execution failed."""
    pass
```

### Session Exceptions

```python
class SessionLockError(AgentMessagingError):
    """Session already locked by another agent."""
    pass

class SessionStateError(AgentMessagingError):
    """Session is in invalid state for operation."""
    pass
```

### Meeting Exceptions

```python
class MeetingNotFoundError(AgentMessagingError):
    """Meeting not found."""
    pass

class MeetingPermissionError(AgentMessagingError):
    """Insufficient permissions for meeting operation."""
    pass

class MeetingError(AgentMessagingError):
    """General meeting error."""
    pass
```

### Timeout Exceptions

```python
class TimeoutError(AgentMessagingError):
    """Operation timed out."""
    pass
```

---

## Models

### Core Models

```python
class Organization(BaseModel):
    id: UUID
    external_id: str
    name: str
    created_at: datetime
    updated_at: datetime

class Agent(BaseModel):
    id: UUID
    external_id: str
    organization_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
```

### Message Models

```python
class MessageContext(BaseModel):
    sender_id: str
    recipient_id: str
    message_id: UUID
    timestamp: datetime
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None

class Message(BaseModel, Generic[T]):
    id: UUID
    sender_id: UUID
    recipient_id: Optional[UUID]
    session_id: Optional[UUID]
    meeting_id: Optional[UUID]
    message_type: MessageType
    content: Dict[str, Any]  # JSON-serialized T
    read_at: Optional[datetime]
    created_at: datetime
    metadata: Dict[str, Any]
```

### Session Models

```python
class Session(BaseModel):
    id: UUID
    agent_a_id: UUID
    agent_b_id: UUID
    session_type: SessionType
    status: SessionStatus
    locked_agent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime]
```

### Meeting Models

```python
class Meeting(BaseModel):
    id: UUID
    host_id: UUID
    status: MeetingStatus
    current_speaker_id: Optional[UUID]
    turn_duration: Optional[float]
    turn_started_at: Optional[datetime]
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]

class MeetingParticipant(BaseModel):
    id: UUID
    meeting_id: UUID
    agent_id: UUID
    status: ParticipantStatus
    join_order: int
    is_locked: bool
    joined_at: datetime
    left_at: Optional[datetime]
```

### Event Models

```python
class MeetingEventType(str, Enum):
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
    TURN_CHANGED = "turn_changed"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    TIMEOUT_OCCURRED = "timeout_occurred"

class MeetingEventPayload(BaseModel):
    meeting_id: UUID
    event_type: MeetingEventType
    timestamp: datetime
    data: Dict[str, Any]
```

### Enums

```python
class MessageType(str, Enum):
    USER_DEFINED = "user_defined"
    SYSTEM = "system"
    TIMEOUT = "timeout"
    ENDING = "ending"

class SessionType(str, Enum):
    SYNC = "sync"
    ASYNC = "async"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    ENDED = "ended"

class MeetingStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    ACTIVE = "active"
    ENDED = "ended"

class ParticipantStatus(str, Enum):
    INVITED = "invited"
    ATTENDING = "attending"
    WAITING = "waiting"
    SPEAKING = "speaking"
    LEFT = "left"
```

---

## Configuration

### Config Class

```python
class Config(BaseSettings):
    database: DatabaseConfig
    messaging: MessagingConfig
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
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
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
```

### MessagingConfig

```python
class MessagingConfig(BaseModel):
    default_sync_timeout: float = 30.0
    default_meeting_turn_duration: float = 60.0
    handler_timeout: float = 30.0
```

---

## Type Signatures

For type checking and IDE support:

```python
from typing import TypeVar
T = TypeVar('T')  # User message type

# SDK instances
sdk: AgentMessaging[MyMessage]

# Messenger instances
one_way: OneWayMessenger[MyMessage]
sync_conv: SyncConversation[MyMessage]
async_conv: AsyncConversation[MyMessage]
meeting_mgr: MeetingManager[MyMessage]

# Handler functions
async def message_handler(message: MyMessage, context: MessageContext) -> Optional[MyMessage]:
    pass

async def event_handler(event: MeetingEventPayload) -> None:
    pass
```

---

*This API reference covers all public interfaces. For implementation details, see the source code.*