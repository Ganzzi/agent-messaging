# Agent Messaging Protocol - API Reference

## Table of Contents

- [AgentMessaging Class](#agentmessaging-class)
- [OneWayMessenger](#onewaymessenger)
- [SyncConversation](#syncconversation)
- [AsyncConversation](#asyncconversation)
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

### Handler Registration

```python
def register_handler(agent_external_id: str) -> Callable
```

Decorator to register message handler for an agent.

**Parameters:**
- `agent_external_id` (str): Agent external ID

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(message: T, context: MessageContext) -> Optional[T]:
    pass
```

```python
def register_event_handler(event_type: MeetingEventType) -> Callable
```

Decorator to register meeting event handler.

**Parameters:**
- `event_type` (MeetingEventType): Type of meeting event

**Returns:** Decorator function

**Handler Signature:**
```python
async def handler(event: MeetingEventPayload) -> None:
    pass
```

```python
def has_handler(agent_external_id: str) -> bool
```

Check if agent has registered handler.

**Parameters:**
- `agent_external_id` (str): Agent external ID

**Returns:** True if handler registered

### Messaging Properties

```python
@property
def one_way(self) -> OneWayMessenger[T]
```

One-way messaging interface.

```python
@property
def sync_conversation(self) -> SyncConversation[T]
```

Synchronous conversation interface.

```python
@property
def async_conversation(self) -> AsyncConversation[T]
```

Asynchronous conversation interface.

```python
@property
def meeting(self) -> MeetingManager[T]
```

Meeting management interface.

---

## OneWayMessenger

Fire-and-forget messaging for notifications.

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
    from_agent_id: str,
    to_agent_id: str,
    message: T
) -> UUID
```

Send one-way message.

**Parameters:**
- `from_agent_id` (str): Sender external ID
- `to_agent_id` (str): Recipient external ID
- `message` (T): Message content

**Returns:** Message UUID

**Raises:** AgentNotFoundError, NoHandlerRegisteredError

---

## SyncConversation

Blocking request-response conversations.

### Constructor

```python
SyncConversation[T](
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
    timeout: float = 30.0
) -> T
```

Send message and wait for response.

**Parameters:**
- `sender_external_id` (str): Sender external ID
- `recipient_external_id` (str): Recipient external ID
- `message` (T): Request message
- `timeout` (float): Max wait time in seconds

**Returns:** Response message

**Raises:** AgentNotFoundError, NoHandlerRegisteredError, TimeoutError

```python
async def reply(
    session_id: UUID,
    responder_external_id: str,
    message: T
) -> None
```

Reply to synchronous conversation.

**Parameters:**
- `session_id` (UUID): Session UUID from MessageContext
- `responder_external_id` (str): Responder external ID
- `message` (T): Response message

**Raises:** RuntimeError, SessionStateError, AgentNotFoundError

```python
async def end_conversation(
    agent_external_id: str,
    other_agent_external_id: str
) -> None
```

End conversation between two agents.

**Parameters:**
- `agent_external_id` (str): One agent external ID
- `other_agent_external_id` (str): Other agent external ID

**Raises:** ValueError, AgentNotFoundError, RuntimeError

---

## AsyncConversation

Non-blocking message queues.

### Constructor

```python
AsyncConversation[T](
    handler_registry: HandlerRegistry,
    message_repo: MessageRepository,
    session_repo: SessionRepository,
    agent_repo: AgentRepository
)
```

### Methods

```python
async def send(
    sender_external_id: str,
    recipient_external_id: str,
    message: T
) -> UUID
```

Send message asynchronously.

**Parameters:**
- `sender_external_id` (str): Sender external ID
- `recipient_external_id` (str): Recipient external ID
- `message` (T): Message content

**Returns:** Conversation UUID

**Raises:** AgentNotFoundError

```python
async def get_unread_messages(agent_external_id: str) -> List[T]
```

Get unread messages for agent.

**Parameters:**
- `agent_external_id` (str): Agent external ID

**Returns:** List of message contents

**Raises:** AgentNotFoundError

```python
async def get_messages_from_agent(
    recipient_external_id: str,
    sender_external_id: str
) -> List[T]
```

Get messages from specific sender.

**Parameters:**
- `recipient_external_id` (str): Recipient external ID
- `sender_external_id` (str): Sender external ID

**Returns:** List of message contents

**Raises:** AgentNotFoundError

```python
async def wait_for_message(
    recipient_external_id: str,
    sender_external_id: str,
    timeout: float = 30.0
) -> Optional[T]
```

Wait for message from specific sender.

**Parameters:**
- `recipient_external_id` (str): Recipient external ID
- `sender_external_id` (str): Sender external ID
- `timeout` (float): Max wait time in seconds

**Returns:** Message content or None if timeout

**Raises:** AgentNotFoundError

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
    next_speaker: Optional[str] = None
) -> UUID
```

Speak in meeting (when it's your turn).

**Parameters:**
- `speaker_external_id` (str): Speaker external ID
- `meeting_id` (UUID): Meeting UUID
- `message` (T): Message content
- `next_speaker` (Optional[str]): Next speaker external ID

**Returns:** Message UUID

**Raises:** MeetingError, MeetingNotFoundError

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