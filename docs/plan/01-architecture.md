# Agent Messaging Protocol - Architecture Design

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Application                         │
│  (AI Agent Controllers, Business Logic, Message Handlers)   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ imports & uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Agent Messaging SDK                         │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │              AgentMessaging (Main API)                  │ │
│ │  - register_organization() / register_agent()           │ │
│ │  - register_handler() / register_event_handler()        │ │
│ │  - one_way, sync_conv, async_conv, meeting              │ │
│ └────────┬──────────────────┬────────────┬─────────────────┘ │
│          │                  │            │                   │
│ ┌────────▼────────┐ ┌──────▼──────┐ ┌──▼──────────────┐    │
│ │  OneWay         │ │  Sync       │ │  Async          │    │
│ │  Messenger      │ │  Conversation│ │  Conversation   │    │
│ └─────────────────┘ └─────────────┘ └─────────────────┘    │
│          │                  │            │                   │
│          └──────────────────┴────────────┘                   │
│                         │                                    │
│                  ┌──────▼─────────┐                          │
│                  │    Meeting     │                          │
│                  │    Manager     │                          │
│                  └────────────────┘                          │
│                         │                                    │
│          ┌──────────────┴──────────────┐                     │
│          │                             │                     │
│ ┌────────▼────────┐         ┌─────────▼──────────┐          │
│ │  Handler        │         │   Event            │          │
│ │  Registry       │         │   System           │          │
│ └─────────────────┘         └────────────────────┘          │
│          │                             │                     │
│          └──────────────┬──────────────┘                     │
│                         │                                    │
│          ┌──────────────▼──────────────┐                     │
│          │    Repository Layer         │                     │
│          │  - OrganizationRepo         │                     │
│          │  - AgentRepo                │                     │
│          │  - MessageRepo              │                     │
│          │  - SessionRepo              │                     │
│          │  - MeetingRepo              │                     │
│          └─────────────┬───────────────┘                     │
│                        │                                     │
│          ┌─────────────▼───────────────┐                     │
│          │   PostgreSQL Manager        │                     │
│          │   (psqlpy Connection Pool)  │                     │
│          └─────────────┬───────────────┘                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         │ SQL queries
                         ▼
              ┌──────────────────────┐
              │   PostgreSQL         │
              │   Database           │
              │   - Tables           │
              │   - Indexes          │
              │   - Advisory Locks   │
              └──────────────────────┘
```

---

## Core Components

### 1. AgentMessaging (Main SDK Class)

**Purpose:** Primary entry point for the SDK. Manages lifecycle and provides access to all messaging capabilities.

**Responsibilities:**
- Initialize database connection pool
- Register organizations and agents
- Provide access to messaging classes
- Manage handler registry
- Manage event system
- Cleanup resources on shutdown

**Key Methods:**
```python
class AgentMessaging:
    async def initialize() -> None
    async def close() -> None
    
    async def register_organization(external_id: str, name: str) -> UUID
    async def register_agent(external_id: str, org_external_id: str, name: str) -> UUID
    
    def register_handler(agent_external_id: str) -> Callable
    def register_event_handler(event_type: MeetingEvent) -> Callable
    
    @property
    def one_way() -> OneWayMessenger
    
    @property
    def sync_conversation() -> SyncConversation
    
    @property
    def async_conversation() -> AsyncConversation
    
    @property
    def meeting() -> MeetingManager
```

---

### 2. Messaging Components

#### 2.1 OneWayMessenger

**Purpose:** Simple one-way message delivery with handler invocation.

**Key Features:**
- No session management
- Immediate handler invocation
- No waiting for response

**Methods:**
```python
class OneWayMessenger:
    async def send(
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None
```

#### 2.2 SyncConversation

**Purpose:** Synchronous two-agent conversation with blocking waits.

**Key Features:**
- Session creation per agent pair
- Sender locking (blocking)
- Timeout support
- Session termination

**Methods:**
```python
class SyncConversation:
    async def send_and_wait(
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType,
        timeout: Optional[float] = None
    ) -> MessageType | TimeoutError
    
    async def reply(
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None
    
    async def end_conversation(
        requester_external_id: str,
        other_external_id: str
    ) -> None
```

#### 2.3 AsyncConversation

**Purpose:** Asynchronous two-agent conversation without blocking.

**Key Features:**
- Non-blocking sends
- Message queue management
- Unread message tracking
- Agent recovery mechanism

**Methods:**
```python
class AsyncConversation:
    async def send(
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None
    
    async def get_unread_messages(
        agent_external_id: str
    ) -> list[MessageType]
    
    async def get_messages_from_agent(
        recipient_external_id: str,
        sender_external_id: str,
        mark_read: bool = True
    ) -> list[MessageType]
    
    async def wait_for_message(
        recipient_external_id: str,
        sender_external_id: str,
        timeout: Optional[float] = None
    ) -> MessageType | None
    
    async def resume_agent_handler(
        agent_external_id: str
    ) -> None
```

#### 2.4 MeetingManager

**Purpose:** Multi-agent meeting coordination with turn-based speaking.

**Key Features:**
- Meeting session management
- Turn-based speaking with timeouts
- Host controls
- Attendance tracking
- Event system
- History tracking

**Methods:**
```python
class MeetingManager:
    async def create_meeting(
        host_external_id: str,
        agent_external_ids: list[str],
        turn_duration: Optional[float] = None
    ) -> UUID  # meeting_id
    
    async def attend_meeting(
        agent_external_id: str,
        meeting_id: UUID,
        timeout: Optional[float] = None
    ) -> MessageType | TimeoutError
    
    async def start_meeting(
        host_external_id: str,
        meeting_id: UUID,
        initial_message: MessageType,
        next_speaker_external_id: Optional[str] = None
    ) -> None
    
    async def speak(
        speaker_external_id: str,
        meeting_id: UUID,
        message: MessageType,
        next_speaker_external_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> MessageType | TimeoutError
    
    async def end_meeting(
        host_external_id: str,
        meeting_id: UUID
    ) -> None
    
    async def leave_meeting(
        agent_external_id: str,
        meeting_id: UUID
    ) -> None
    
    async def get_meeting_status(
        meeting_id: UUID
    ) -> MeetingStatus
    
    async def get_meeting_history(
        meeting_id: UUID
    ) -> list[MessageType]
```

---

### 3. Handler System

#### 3.1 Handler Registry

**Purpose:** Store and retrieve agent message handlers.

**Design:**
```python
class HandlerRegistry:
    _handlers: dict[str, Callable]  # agent_external_id -> handler
    
    def register(agent_external_id: str, handler: Callable) -> None
    def get(agent_external_id: str) -> Optional[Callable]
    def has_handler(agent_external_id: str) -> bool
    
    async def invoke(
        agent_external_id: str,
        message: MessageType,
        context: MessageContext
    ) -> Any
```

**Handler Signature:**
```python
async def agent_handler(
    message: MessageType,
    context: MessageContext
) -> Optional[MessageType]:
    """
    User-defined handler for processing incoming messages.
    
    Args:
        message: The incoming message (user-defined type)
        context: Context with sender info, session info, etc.
    
    Returns:
        Optional response message
    """
    pass
```

#### 3.2 Event System

**Purpose:** Allow users to hook into meeting lifecycle events.

**Event Types:**
```python
class MeetingEvent(Enum):
    AGENT_JOINED = "agent_joined"
    AGENT_SPOKE = "agent_spoke"
    AGENT_LEFT = "agent_left"
    AGENT_TIMED_OUT = "agent_timed_out"
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
```

**Event Handler Signature:**
```python
async def event_handler(
    event_type: MeetingEvent,
    meeting_id: UUID,
    agent_external_id: Optional[str],
    data: dict[str, Any]
) -> None:
    """
    User-defined handler for meeting events.
    """
    pass
```

---

### 4. Repository Layer

**Purpose:** Abstract database operations and provide clean data access.

#### Base Repository
```python
class BaseRepository:
    def __init__(self, db_manager: PostgreSQLManager)
    
    async def execute(query: str, params: list) -> Any
    async def fetch_one(query: str, params: list) -> Optional[tuple]
    async def fetch_all(query: str, params: list) -> list[tuple]
```

#### Specific Repositories

**OrganizationRepository:**
- create, get_by_id, get_by_external_id, update, delete

**AgentRepository:**
- create, get_by_id, get_by_external_id, get_by_organization, update, delete

**MessageRepository:**
- create, get_by_id, get_by_session, get_unread, mark_read, get_conversation_history

**SessionRepository:**
- create_conversation, get_conversation, update_conversation, end_conversation
- lock_agent, unlock_agent, get_locked_agents

**MeetingRepository:**
- create_meeting, get_meeting, update_meeting, end_meeting
- add_participant, remove_participant, get_participants
- set_current_speaker, get_current_speaker
- add_message, get_messages

---

### 5. PostgreSQL Manager

**Purpose:** Manage connection pool and provide connections.

**Key Features:**
- Connection pooling with psqlpy
- Context manager for connections
- Query execution helpers
- Connection lifecycle management

**Usage:**
```python
class PostgreSQLManager:
    async def initialize() -> None
    async def close() -> None
    
    @asynccontextmanager
    async def connection() -> Connection
    
    async def execute(query: str, params: list) -> Any
```

---

## Data Flow Diagrams

### One-Way Message Flow

```
User Code
   │
   │ send(sender, recipient, message)
   ▼
OneWayMessenger
   │
   ├─► MessageRepository.create(message)
   │
   ├─► HandlerRegistry.get(recipient)
   │
   └─► invoke_handler(message)
          │
          ▼
     User Handler Function
```

### Sync Conversation Flow (Send and Wait)

```
Agent A Code
   │
   │ send_and_wait(A, B, message)
   ▼
SyncConversation
   │
   ├─► SessionRepository.get_or_create_session(A, B)
   │
   ├─► MessageRepository.create(message)
   │
   ├─► Check if B is waiting?
   │      │
   │      ├─► No: Invoke B's handler
   │      │      │
   │      │      └─► HandlerRegistry.invoke(B, message)
   │      │
   │      └─► Yes: B is already waiting
   │
   ├─► SessionRepository.lock_agent(A)
   │
   └─► Wait for unlock or timeout
          │
          ▼
   (A is blocked here)
          │
          │ (When B replies)
          ▼
Agent B Code
   │
   │ reply(B, A, response)
   ▼
SyncConversation
   │
   ├─► MessageRepository.create(response)
   │
   ├─► SessionRepository.unlock_agent(A)
   │
   └─► SessionRepository.lock_agent(B)
          │
          ▼
   (B is now blocked)
          │
          ▼
Agent A Code
   │
   │ (Unblocked, receives response)
   │
   └─► Handle response
```

### Meeting Flow (Turn-Based Speaking)

```
Host Code
   │
   │ create_meeting(host, [A, B, C])
   ▼
MeetingManager
   │
   ├─► MeetingRepository.create_meeting()
   │
   └─► Invoke handlers for all agents
          │
          ├─► HandlerRegistry.invoke(A)
          ├─► HandlerRegistry.invoke(B)
          └─► HandlerRegistry.invoke(C)

Agent A/B/C Code
   │
   │ attend_meeting(meeting_id)
   ▼
MeetingManager
   │
   ├─► MeetingRepository.add_participant(agent)
   │
   └─► Lock agent (wait for turn)
          │
          ▼
   (Agents blocked here)

Host Code
   │
   │ start_meeting(meeting_id, "Welcome!")
   ▼
MeetingManager
   │
   ├─► MeetingRepository.add_message(host, "Welcome!")
   │
   ├─► MeetingRepository.set_current_speaker(A)
   │
   ├─► EventSystem.emit(MEETING_STARTED)
   │
   ├─► Unlock Agent A
   │
   └─► Lock Host
          │
          ▼
   (Host blocked, A unblocked)

Agent A Code
   │
   │ (Receives turn signal)
   │
   │ speak(meeting_id, "Hello everyone!")
   ▼
MeetingManager
   │
   ├─► MeetingRepository.add_message(A, "Hello everyone!")
   │
   ├─► EventSystem.emit(AGENT_SPOKE, A)
   │
   ├─► MeetingRepository.set_current_speaker(B)
   │
   ├─► Unlock Agent B
   │
   └─► Lock Agent A
          │
          ▼
   (A blocked, B unblocked)

   ... (continue round-robin)
```

---

## State Machines

### Conversation Session States

```
┌──────────┐
│  IDLE    │
└────┬─────┘
     │ create_session()
     ▼
┌──────────┐
│ ACTIVE   │◄─────┐
└────┬─────┘      │
     │            │ reply()
     │ send()     │
     ▼            │
┌──────────┐      │
│ WAITING  │──────┘
└────┬─────┘
     │
     │ end_conversation()
     ▼
┌──────────┐
│  ENDED   │
└──────────┘
```

### Meeting States

```
┌───────────┐
│  CREATED  │
└─────┬─────┘
      │ All agents attended
      ▼
┌───────────┐
│ READY     │
└─────┬─────┘
      │ start_meeting()
      ▼
┌───────────┐
│  ACTIVE   │◄─────┐
└─────┬─────┘      │
      │            │ speak()
      │ speak()    │
      ▼            │
┌───────────┐      │
│ SPEAKING  │──────┘
└─────┬─────┘
      │
      │ end_meeting()
      ▼
┌───────────┐
│  ENDED    │
└───────────┘
```

### Agent States in Meeting

```
┌───────────┐
│ INVITED   │
└─────┬─────┘
      │ attend_meeting()
      ▼
┌───────────┐
│ ATTENDING │
└─────┬─────┘
      │ start_meeting()
      ▼
┌───────────┐
│  WAITING  │◄─────┐
└─────┬─────┘      │
      │            │ next turn
      │ my turn    │
      ▼            │
┌───────────┐      │
│ SPEAKING  │──────┘
└─────┬─────┘
      │
      │ leave_meeting() or end_meeting()
      ▼
┌───────────┐
│   LEFT    │
└───────────┘
```

---

## Concurrency & Locking Strategy

### PostgreSQL Advisory Locks

**Purpose:** Coordinate agent locking across distributed processes.

**Lock IDs:**
- Agent locks: `hash(agent_external_id)`
- Session locks: `hash(session_id)`
- Meeting locks: `hash(meeting_id)`

**Usage:**
```python
# Lock agent
await conn.execute("SELECT pg_advisory_lock($1)", [lock_id])

# Try lock with timeout
await conn.execute("SELECT pg_try_advisory_lock($1)", [lock_id])

# Unlock agent
await conn.execute("SELECT pg_advisory_unlock($1)", [lock_id])
```

### asyncio Coordination

**Timeout Management:**
```python
try:
    result = await asyncio.wait_for(
        wait_for_unlock(agent_id),
        timeout=timeout_seconds
    )
except asyncio.TimeoutError:
    return TimeoutError("Agent did not respond")
```

**Event Coordination:**
```python
# Use asyncio.Event for signaling
unlock_event = asyncio.Event()

# Waiting side
await unlock_event.wait()

# Unlocking side
unlock_event.set()
```

---

## Error Handling Strategy

### Exception Hierarchy

```
AgentMessagingError (base)
├── AgentNotFoundError
├── OrganizationNotFoundError
├── SessionError
│   ├── SessionNotFoundError
│   ├── SessionAlreadyExistsError
│   └── InvalidSessionStateError
├── MeetingError
│   ├── MeetingNotFoundError
│   ├── NotMeetingHostError
│   ├── AgentNotInMeetingError
│   └── InvalidMeetingStateError
├── HandlerError
│   ├── HandlerNotRegisteredError
│   └── HandlerExecutionError
└── TimeoutError
    ├── ConversationTimeoutError
    ├── MeetingTimeoutError
    └── SpeakingTimeoutError
```

### Error Propagation

1. **Repository Layer:** Raise specific database errors
2. **Messaging Layer:** Catch and convert to domain errors
3. **Handler Execution:** Wrap in HandlerExecutionError
4. **User Code:** Receives clean, documented exceptions

---

## Performance Considerations

### Connection Pooling
- Default pool size: 10 connections
- Configurable based on load
- Monitor pool exhaustion

### Database Indexes
- Index on `external_id` columns
- Index on `session_id` in messages
- Index on `meeting_id` in participants
- Index on `recipient_id` + `read_at` for unread queries

### Batch Operations
- Bulk message creation for meetings
- Batch participant registration

### Caching Strategy
- Cache agent ID lookups (external_id -> UUID)
- Cache organization lookups
- Invalidate on updates

---

## Security Considerations

### Authentication
- SDK doesn't handle auth (user's responsibility)
- External IDs trusted from caller

### Authorization
- Host-only operations validated
- Agent membership validated
- Session participation validated

### SQL Injection Prevention
- Always use parameterized queries
- No string concatenation for SQL

### Data Privacy
- Message content not logged
- Configurable retention policies
- Support for soft deletes

---

## Scalability Considerations

### Horizontal Scaling
- Stateless design (state in PostgreSQL)
- Multiple SDK instances can run concurrently
- PostgreSQL advisory locks work across processes

### Vertical Scaling
- Connection pool tuning
- Database query optimization
- Index optimization

### Future Enhancements
- Redis for event broadcasting
- Message queue for handler invocation
- Separate read replicas for history queries

---

## Technology Choices Rationale

### Why psqlpy?
- High performance async driver
- Native PostgreSQL features (advisory locks)
- Type-safe parameter binding
- Active development

### Why PostgreSQL?
- Robust locking mechanisms
- ACID transactions
- JSONB support for flexible message types
- Mature and reliable

### Why asyncio?
- Native Python async/await
- Efficient I/O handling
- Easy timeout management
- Good ecosystem support

### Why Pydantic?
- Type safety
- Data validation
- Easy serialization
- Great documentation

---

## Next Steps

1. Review and approve architecture
2. Refine database schema (see `02-database-schema.md`)
3. Define detailed API interfaces (see `03-api-design.md`)
4. Begin implementation (Phase 1)
