# Agent Messaging Protocol - API Design

## Package Structure

```
agent_messaging/
├── __init__.py                 # Main exports
├── client.py                   # AgentMessaging main class
├── config.py                   # Configuration management
├── models.py                   # Data models (Pydantic)
├── exceptions.py               # Custom exceptions
│
├── database/
│   ├── __init__.py
│   ├── manager.py              # PostgreSQL manager (psqlpy)
│   └── repositories/
│       ├── __init__.py
│       ├── base.py             # Base repository
│       ├── organization.py     # Organization repository
│       ├── agent.py            # Agent repository
│       ├── message.py          # Message repository
│       ├── session.py          # Session repository
│       └── meeting.py          # Meeting repository
│
├── messaging/
│   ├── __init__.py
│   ├── one_way.py              # OneWayMessenger
│   ├── sync_conversation.py    # SyncConversation
│   ├── async_conversation.py   # AsyncConversation
│   └── meeting.py              # MeetingManager
│
├── handlers/
│   ├── __init__.py
│   ├── registry.py             # Handler registry
│   └── events.py               # Event system
│
└── utils/
    ├── __init__.py
    ├── locks.py                # Advisory lock utilities
    └── timeouts.py             # Timeout utilities
```

---

## Core API

### 1. Main SDK Class: AgentMessaging

**Purpose:** Primary entry point for the SDK.

```python
from typing import TypeVar, Generic, Callable, Optional
from uuid import UUID
from agent_messaging.models import MessageContext

# Generic type for user-defined messages
MessageType = TypeVar('MessageType')


class AgentMessaging(Generic[MessageType]):
    """
    Main SDK class for agent messaging.
    
    Usage:
        async with AgentMessaging[MyMessage](config) as sdk:
            # Register organization and agents
            await sdk.register_organization("org_001", "My Organization")
            await sdk.register_agent("agent_alice", "org_001", "Alice")
            
            # Register message handler
            @sdk.register_handler("agent_alice")
            async def alice_handler(message: MyMessage, context: MessageContext):
                print(f"Alice received: {message}")
                return MyMessage(text="Thanks!")
            
            # Send messages
            await sdk.one_way.send("agent_alice", "agent_bob", message)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the SDK.
        
        Args:
            config: Optional configuration. If None, loads from environment.
        """
        ...
    
    async def initialize(self) -> None:
        """
        Initialize database connection pool.
        Must be called before using the SDK.
        """
        ...
    
    async def close(self) -> None:
        """
        Close database connections and cleanup resources.
        Should be called when shutting down.
        """
        ...
    
    # ========================================================================
    # Organization & Agent Management
    # ========================================================================
    
    async def register_organization(
        self,
        external_id: str,
        name: str
    ) -> UUID:
        """
        Register an organization.
        
        Args:
            external_id: External identifier for the organization
            name: Human-readable name
        
        Returns:
            Internal UUID for the organization
        
        Raises:
            OrganizationAlreadyExistsError: If external_id already exists
        """
        ...
    
    async def register_agent(
        self,
        external_id: str,
        organization_external_id: str,
        name: str
    ) -> UUID:
        """
        Register an agent.
        
        Args:
            external_id: External identifier for the agent
            organization_external_id: External ID of the agent's organization
            name: Human-readable name
        
        Returns:
            Internal UUID for the agent
        
        Raises:
            AgentAlreadyExistsError: If external_id already exists
            OrganizationNotFoundError: If organization doesn't exist
        """
        ...
    
    async def get_agent(self, external_id: str) -> Agent:
        """
        Get agent by external ID.
        
        Args:
            external_id: External identifier for the agent
        
        Returns:
            Agent model
        
        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        ...
    
    async def get_organization(self, external_id: str) -> Organization:
        """
        Get organization by external ID.
        
        Args:
            external_id: External identifier for the organization
        
        Returns:
            Organization model
        
        Raises:
            OrganizationNotFoundError: If organization doesn't exist
        """
        ...
    
    # ========================================================================
    # Handler Registration
    # ========================================================================
    
    def register_handler(
        self,
        agent_external_id: str
    ) -> Callable:
        """
        Decorator to register a message handler for an agent.
        
        The handler will be called when messages are sent to this agent.
        
        Args:
            agent_external_id: External ID of the agent
        
        Returns:
            Decorator function
        
        Usage:
            @sdk.register_handler("agent_alice")
            async def handle_message(message: MyMessage, context: MessageContext):
                # Process message
                return response_message  # Optional
        
        Handler Signature:
            async def handler(
                message: MessageType,
                context: MessageContext
            ) -> Optional[MessageType]:
                ...
        """
        ...
    
    def register_event_handler(
        self,
        event_type: MeetingEvent
    ) -> Callable:
        """
        Decorator to register an event handler for meeting events.
        
        Args:
            event_type: Type of event to handle
        
        Returns:
            Decorator function
        
        Usage:
            @sdk.register_event_handler(MeetingEvent.AGENT_SPOKE)
            async def on_agent_spoke(meeting_id: UUID, agent_id: str, data: dict):
                print(f"Agent {agent_id} spoke in meeting {meeting_id}")
        
        Event Handler Signature:
            async def handler(
                meeting_id: UUID,
                agent_external_id: Optional[str],
                data: dict[str, Any]
            ) -> None:
                ...
        """
        ...
    
    # ========================================================================
    # Messaging Access
    # ========================================================================
    
    @property
    def one_way(self) -> OneWayMessenger[MessageType]:
        """Access one-way messaging."""
        ...
    
    @property
    def sync_conversation(self) -> SyncConversation[MessageType]:
        """Access synchronous conversation."""
        ...
    
    @property
    def async_conversation(self) -> AsyncConversation[MessageType]:
        """Access asynchronous conversation."""
        ...
    
    @property
    def meeting(self) -> MeetingManager[MessageType]:
        """Access meeting management."""
        ...
    
    # ========================================================================
    # Context Manager Support
    # ========================================================================
    
    async def __aenter__(self) -> "AgentMessaging[MessageType]":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
```

---

### 2. One-Way Messaging

```python
class OneWayMessenger(Generic[MessageType]):
    """
    Simple one-way message delivery.
    
    No session management, no waiting for response.
    Handler is invoked immediately for the recipient.
    """
    
    async def send(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None:
        """
        Send a one-way message.
        
        The recipient's handler will be invoked immediately (if registered).
        
        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send
        
        Raises:
            AgentNotFoundError: If sender or recipient doesn't exist
            HandlerNotRegisteredError: If recipient has no handler
        
        Example:
            await sdk.one_way.send(
                "agent_alice",
                "agent_bob",
                MyMessage(text="Hello!")
            )
        """
        ...
```

---

### 3. Synchronous Conversation

```python
class SyncConversation(Generic[MessageType]):
    """
    Synchronous two-agent conversation with blocking waits.
    
    - Sender waits for response (blocked)
    - Session managed automatically
    - Timeout support
    """
    
    async def send_and_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType,
        timeout: Optional[float] = None
    ) -> MessageType:
        """
        Send a message and wait for response.
        
        The sender will be blocked until:
        1. The recipient replies, OR
        2. The timeout expires
        
        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send
            timeout: Optional timeout in seconds (default from config)
        
        Returns:
            Response message from recipient
        
        Raises:
            AgentNotFoundError: If sender or recipient doesn't exist
            ConversationTimeoutError: If timeout expires
            ConversationEndedError: If conversation ended while waiting
        
        Example:
            response = await sdk.sync_conversation.send_and_wait(
                "agent_alice",
                "agent_bob",
                MyMessage(text="What's your name?"),
                timeout=30.0
            )
            print(f"Bob replied: {response.text}")
        """
        ...
    
    async def reply(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None:
        """
        Reply to a waiting agent.
        
        This should be called by the agent that received a message via
        send_and_wait(). The sender will be unblocked and receive this message.
        
        Args:
            sender_external_id: External ID of replying agent
            recipient_external_id: External ID of waiting agent
            message: Reply message
        
        Raises:
            AgentNotFoundError: If sender or recipient doesn't exist
            SessionNotFoundError: If no active session exists
            InvalidSessionStateError: If recipient is not waiting
        
        Example:
            # In Bob's handler
            async def bob_handler(message: MyMessage, context: MessageContext):
                if context.requires_reply:
                    await sdk.sync_conversation.reply(
                        "agent_bob",
                        context.sender_external_id,
                        MyMessage(text="I'm Bob!")
                    )
        """
        ...
    
    async def end_conversation(
        self,
        requester_external_id: str,
        other_external_id: str
    ) -> None:
        """
        End the conversation session.
        
        Both agents will be unlocked. If either agent is waiting,
        they will receive a ConversationEndedError.
        
        Args:
            requester_external_id: External ID of agent ending conversation
            other_external_id: External ID of other agent
        
        Raises:
            AgentNotFoundError: If either agent doesn't exist
            SessionNotFoundError: If no active session exists
        
        Example:
            await sdk.sync_conversation.end_conversation(
                "agent_alice",
                "agent_bob"
            )
        """
        ...
```

---

### 4. Asynchronous Conversation

```python
class AsyncConversation(Generic[MessageType]):
    """
    Asynchronous two-agent conversation without blocking.
    
    - Sender continues without waiting
    - Messages queued for recipient
    - Recipient retrieves messages when ready
    """
    
    async def send(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: MessageType
    ) -> None:
        """
        Send a message without waiting for response.
        
        The message is queued for the recipient. The sender continues
        immediately without blocking.
        
        Args:
            sender_external_id: External ID of sender agent
            recipient_external_id: External ID of recipient agent
            message: Message to send
        
        Raises:
            AgentNotFoundError: If sender or recipient doesn't exist
        
        Example:
            await sdk.async_conversation.send(
                "agent_alice",
                "agent_bob",
                MyMessage(text="Hey Bob!")
            )
            # Alice continues immediately
        """
        ...
    
    async def get_unread_messages(
        self,
        agent_external_id: str
    ) -> list[MessageType]:
        """
        Get all unread messages for an agent.
        
        Messages are marked as read after retrieval.
        
        Args:
            agent_external_id: External ID of agent
        
        Returns:
            List of unread messages (ordered by creation time)
        
        Raises:
            AgentNotFoundError: If agent doesn't exist
        
        Example:
            messages = await sdk.async_conversation.get_unread_messages("agent_bob")
            for msg in messages:
                print(f"Message: {msg.text}")
        """
        ...
    
    async def get_messages_from_agent(
        self,
        recipient_external_id: str,
        sender_external_id: str,
        mark_read: bool = True
    ) -> list[MessageType]:
        """
        Get messages from a specific agent.
        
        Args:
            recipient_external_id: External ID of receiving agent
            sender_external_id: External ID of sending agent
            mark_read: Whether to mark messages as read (default: True)
        
        Returns:
            List of messages from sender (ordered by creation time)
        
        Raises:
            AgentNotFoundError: If either agent doesn't exist
        
        Example:
            alice_messages = await sdk.async_conversation.get_messages_from_agent(
                "agent_bob",
                "agent_alice"
            )
        """
        ...
    
    async def wait_for_message(
        self,
        recipient_external_id: str,
        sender_external_id: str,
        timeout: Optional[float] = None
    ) -> Optional[MessageType]:
        """
        Wait for a message from a specific agent.
        
        Blocks until a message arrives or timeout expires.
        
        Args:
            recipient_external_id: External ID of receiving agent
            sender_external_id: External ID of sending agent to wait for
            timeout: Optional timeout in seconds
        
        Returns:
            Message from sender, or None if timeout
        
        Raises:
            AgentNotFoundError: If either agent doesn't exist
        
        Example:
            message = await sdk.async_conversation.wait_for_message(
                "agent_bob",
                "agent_alice",
                timeout=60.0
            )
            if message:
                print(f"Alice said: {message.text}")
            else:
                print("Alice didn't respond")
        """
        ...
    
    async def resume_agent_handler(
        self,
        agent_external_id: str
    ) -> None:
        """
        Resume an agent that stopped working during a conversation.
        
        This is typically called by the system when it detects an agent
        has stopped. It waits for any pending messages to be sent, then
        invokes the agent's handler.
        
        Args:
            agent_external_id: External ID of agent to resume
        
        Raises:
            AgentNotFoundError: If agent doesn't exist
            HandlerNotRegisteredError: If agent has no handler
        
        Example:
            # System detects agent_bob stopped
            await sdk.async_conversation.resume_agent_handler("agent_bob")
        """
        ...
```

---

### 5. Meeting Management

```python
class MeetingManager(Generic[MessageType]):
    """
    Multi-agent meeting coordination.
    
    - Turn-based speaking
    - Host controls
    - Timeout management
    - Event system
    """
    
    async def create_meeting(
        self,
        host_external_id: str,
        agent_external_ids: list[str],
        turn_duration: Optional[float] = None
    ) -> UUID:
        """
        Create a new meeting.
        
        All agents' handlers will be invoked to notify them of the meeting.
        
        Args:
            host_external_id: External ID of meeting host
            agent_external_ids: List of agent external IDs to invite (including host)
            turn_duration: Optional time limit per speaking turn (seconds)
        
        Returns:
            Meeting ID
        
        Raises:
            AgentNotFoundError: If any agent doesn't exist
            InvalidMeetingError: If agent list invalid (e.g., duplicate agents)
        
        Example:
            meeting_id = await sdk.meeting.create_meeting(
                "agent_alice",  # host
                ["agent_alice", "agent_bob", "agent_charlie"],
                turn_duration=60.0
            )
        """
        ...
    
    async def attend_meeting(
        self,
        agent_external_id: str,
        meeting_id: UUID,
        timeout: Optional[float] = None
    ) -> MessageType:
        """
        Agent attends the meeting and waits for their turn.
        
        The agent will be blocked until:
        1. It's their turn to speak, OR
        2. The meeting ends, OR
        3. The timeout expires
        
        Args:
            agent_external_id: External ID of attending agent
            meeting_id: Meeting ID
            timeout: Optional timeout in seconds
        
        Returns:
            Message indicating turn signal or meeting ended
        
        Raises:
            AgentNotFoundError: If agent doesn't exist
            MeetingNotFoundError: If meeting doesn't exist
            AgentNotInMeetingError: If agent not invited
            MeetingTimeoutError: If timeout expires
        
        Example:
            # In agent's handler after receiving meeting invitation
            turn_signal = await sdk.meeting.attend_meeting(
                "agent_bob",
                meeting_id,
                timeout=300.0
            )
            # Bob's turn to speak!
        """
        ...
    
    async def start_meeting(
        self,
        host_external_id: str,
        meeting_id: UUID,
        initial_message: MessageType,
        next_speaker_external_id: Optional[str] = None
    ) -> None:
        """
        Start the meeting (host only).
        
        The host provides an initial message and optionally specifies
        the first speaker. If no speaker specified, uses round-robin.
        
        After starting, the host is locked until their next turn.
        
        Args:
            host_external_id: External ID of meeting host
            meeting_id: Meeting ID
            initial_message: Host's opening message
            next_speaker_external_id: Optional ID of first speaker
        
        Raises:
            AgentNotFoundError: If host or next speaker doesn't exist
            MeetingNotFoundError: If meeting doesn't exist
            NotMeetingHostError: If caller is not the host
            InvalidMeetingStateError: If meeting not ready (agents haven't attended)
        
        Example:
            await sdk.meeting.start_meeting(
                "agent_alice",
                meeting_id,
                MyMessage(text="Welcome everyone! Let's begin."),
                next_speaker_external_id="agent_bob"
            )
        """
        ...
    
    async def speak(
        self,
        speaker_external_id: str,
        meeting_id: UUID,
        message: MessageType,
        next_speaker_external_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> MessageType:
        """
        Current speaker speaks and passes turn.
        
        The speaker is locked after speaking. The next speaker is unlocked.
        If no next speaker specified, uses round-robin.
        
        The speaker waits (blocked) until their next turn or meeting ends.
        
        Args:
            speaker_external_id: External ID of current speaker
            meeting_id: Meeting ID
            message: Speaker's message
            next_speaker_external_id: Optional ID of next speaker
            timeout: Optional timeout for waiting (seconds)
        
        Returns:
            Message indicating next turn signal or meeting ended
        
        Raises:
            AgentNotFoundError: If speaker or next speaker doesn't exist
            MeetingNotFoundError: If meeting doesn't exist
            NotCurrentSpeakerError: If caller is not current speaker
            AgentNotInMeetingError: If next speaker not in meeting
            MeetingTimeoutError: If timeout expires while waiting
        
        Example:
            # Agent Bob's turn
            next_signal = await sdk.meeting.speak(
                "agent_bob",
                meeting_id,
                MyMessage(text="I think we should..."),
                next_speaker_external_id="agent_charlie",
                timeout=300.0
            )
            # Now it's Bob's turn again (or meeting ended)
        """
        ...
    
    async def end_meeting(
        self,
        host_external_id: str,
        meeting_id: UUID
    ) -> None:
        """
        End the meeting (host only).
        
        All agents are unlocked and receive meeting ended notification.
        
        Args:
            host_external_id: External ID of meeting host
            meeting_id: Meeting ID
        
        Raises:
            AgentNotFoundError: If host doesn't exist
            MeetingNotFoundError: If meeting doesn't exist
            NotMeetingHostError: If caller is not the host
        
        Example:
            await sdk.meeting.end_meeting("agent_alice", meeting_id)
        """
        ...
    
    async def leave_meeting(
        self,
        agent_external_id: str,
        meeting_id: UUID
    ) -> None:
        """
        Agent leaves the meeting.
        
        Agent must not be the host. If agent is current speaker, waits
        for their turn to finish before removing them.
        
        Args:
            agent_external_id: External ID of leaving agent
            meeting_id: Meeting ID
        
        Raises:
            AgentNotFoundError: If agent doesn't exist
            MeetingNotFoundError: If meeting doesn't exist
            AgentNotInMeetingError: If agent not in meeting
            HostCannotLeaveError: If agent is the host
        
        Example:
            await sdk.meeting.leave_meeting("agent_bob", meeting_id)
        """
        ...
    
    async def get_meeting_status(
        self,
        meeting_id: UUID
    ) -> MeetingStatus:
        """
        Get current meeting status.
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Meeting status including current speaker, participants, state
        
        Raises:
            MeetingNotFoundError: If meeting doesn't exist
        
        Example:
            status = await sdk.meeting.get_meeting_status(meeting_id)
            print(f"Current speaker: {status.current_speaker}")
            print(f"Participants: {status.participants}")
            print(f"State: {status.state}")
        """
        ...
    
    async def get_meeting_history(
        self,
        meeting_id: UUID
    ) -> list[MessageType]:
        """
        Get meeting conversation history.
        
        Returns all messages in chronological order, including system
        messages (timeouts, joins, leaves).
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            List of messages with metadata
        
        Raises:
            MeetingNotFoundError: If meeting doesn't exist
        
        Example:
            history = await sdk.meeting.get_meeting_history(meeting_id)
            for msg in history:
                print(f"{msg.sender}: {msg.content}")
        """
        ...
```

---

## Data Models

### Core Models

```python
from pydantic import BaseModel, Field
from typing import Optional, Any, Generic, TypeVar
from uuid import UUID
from datetime import datetime
from enum import Enum


class Organization(BaseModel):
    """Organization model."""
    id: UUID
    external_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class Agent(BaseModel):
    """Agent model."""
    id: UUID
    external_id: str
    organization_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class SessionType(str, Enum):
    """Session type enum."""
    SYNC = "sync"
    ASYNC = "async"


class SessionStatus(str, Enum):
    """Session status enum."""
    ACTIVE = "active"
    WAITING = "waiting"
    ENDED = "ended"


class Session(BaseModel):
    """Conversation session model."""
    id: UUID
    agent_a_id: UUID
    agent_b_id: UUID
    session_type: SessionType
    status: SessionStatus
    locked_agent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime] = None


class MeetingStatus(str, Enum):
    """Meeting status enum."""
    CREATED = "created"
    READY = "ready"
    ACTIVE = "active"
    ENDED = "ended"


class Meeting(BaseModel):
    """Meeting model."""
    id: UUID
    host_id: UUID
    status: MeetingStatus
    current_speaker_id: Optional[UUID] = None
    turn_duration: Optional[float] = None
    turn_started_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class ParticipantStatus(str, Enum):
    """Meeting participant status enum."""
    INVITED = "invited"
    ATTENDING = "attending"
    WAITING = "waiting"
    SPEAKING = "speaking"
    LEFT = "left"


class MeetingParticipant(BaseModel):
    """Meeting participant model."""
    id: UUID
    meeting_id: UUID
    agent_id: UUID
    status: ParticipantStatus
    join_order: int
    is_locked: bool
    joined_at: datetime
    left_at: Optional[datetime] = None


class MeetingEvent(str, Enum):
    """Meeting event types."""
    AGENT_JOINED = "agent_joined"
    AGENT_SPOKE = "agent_spoke"
    AGENT_LEFT = "agent_left"
    AGENT_TIMED_OUT = "agent_timed_out"
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"


MessageType = TypeVar('MessageType')


class Message(BaseModel, Generic[MessageType]):
    """Message model."""
    id: UUID
    sender_id: UUID
    recipient_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    message_type: str
    content: MessageType  # User-defined message type
    read_at: Optional[datetime] = None
    created_at: datetime
    metadata: Optional[dict[str, Any]] = None


class MessageContext(BaseModel):
    """Context provided to message handlers."""
    sender_external_id: str
    sender_name: str
    recipient_external_id: str
    recipient_name: str
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    message_type: str
    requires_reply: bool = False  # True for sync conversations
    is_meeting_message: bool = False
    metadata: Optional[dict[str, Any]] = None


class MeetingStatusResponse(BaseModel):
    """Meeting status response."""
    meeting_id: UUID
    status: MeetingStatus
    host_external_id: str
    current_speaker_external_id: Optional[str] = None
    participants: list[str]  # List of agent external IDs
    participant_count: int
    turn_duration: Optional[float] = None
    turn_started_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
```

---

## Configuration

```python
from pydantic import BaseModel, Field
from typing import Optional
import os


class Config(BaseModel):
    """SDK configuration."""
    
    # Database settings
    postgres_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    postgres_password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    postgres_db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "agent_messaging"))
    
    # Connection pool settings
    max_pool_size: int = Field(default=10, description="Maximum connections in pool")
    
    # Timeout settings (in seconds)
    default_conversation_timeout: float = Field(default=300.0, description="5 minutes")
    default_meeting_timeout: float = Field(default=600.0, description="10 minutes")
    default_turn_duration: float = Field(default=60.0, description="1 minute per turn")
    
    # Behavior settings
    enable_turn_timeout: bool = Field(default=True, description="Enable automatic turn timeout")
    auto_invoke_handlers: bool = Field(default=True, description="Automatically invoke handlers")
```

---

## Usage Examples

### Example 1: Simple One-Way Notification

```python
from agent_messaging import AgentMessaging
from pydantic import BaseModel


class NotificationMessage(BaseModel):
    text: str
    priority: str


async def main():
    async with AgentMessaging[NotificationMessage]() as sdk:
        # Register agents
        await sdk.register_organization("org_001", "My Org")
        await sdk.register_agent("agent_alice", "org_001", "Alice")
        await sdk.register_agent("agent_bob", "org_001", "Bob")
        
        # Register handler for Bob
        @sdk.register_handler("agent_bob")
        async def bob_handler(message: NotificationMessage, context):
            print(f"Bob received: {message.text} (Priority: {message.priority})")
        
        # Send notification
        await sdk.one_way.send(
            "agent_alice",
            "agent_bob",
            NotificationMessage(text="Server restart in 5 minutes", priority="high")
        )
```

### Example 2: Synchronous Interview

```python
class InterviewMessage(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None


async def main():
    async with AgentMessaging[InterviewMessage]() as sdk:
        # Setup...
        
        @sdk.register_handler("agent_bob")
        async def bob_handler(message: InterviewMessage, context):
            if message.question:
                # Bob answers the question
                answer = f"My answer to '{message.question}' is..."
                if context.requires_reply:
                    await sdk.sync_conversation.reply(
                        "agent_bob",
                        context.sender_external_id,
                        InterviewMessage(answer=answer)
                    )
        
        # Alice interviews Bob
        questions = [
            "What's your experience?",
            "Why this role?",
            "Any questions for us?"
        ]
        
        for question in questions:
            response = await sdk.sync_conversation.send_and_wait(
                "agent_alice",
                "agent_bob",
                InterviewMessage(question=question),
                timeout=60.0
            )
            print(f"Bob: {response.answer}")
        
        await sdk.sync_conversation.end_conversation("agent_alice", "agent_bob")
```

### Example 3: Meeting with Turn-Based Speaking

```python
class MeetingMessage(BaseModel):
    speaker: str
    content: str


async def main():
    async with AgentMessaging[MeetingMessage]() as sdk:
        # Setup agents...
        
        # Register handlers for all agents
        @sdk.register_handler("agent_alice")
        async def alice_handler(message: MeetingMessage, context):
            if context.is_meeting_message:
                # Attend meeting
                await sdk.meeting.attend_meeting("agent_alice", context.meeting_id)
        
        # Similar handlers for Bob and Charlie...
        
        # Register event handlers
        @sdk.register_event_handler(MeetingEvent.AGENT_SPOKE)
        async def on_spoke(meeting_id, agent_id, data):
            print(f"{agent_id} spoke: {data['message']}")
        
        # Alice creates meeting
        meeting_id = await sdk.meeting.create_meeting(
            "agent_alice",
            ["agent_alice", "agent_bob", "agent_charlie"],
            turn_duration=60.0
        )
        
        # Wait for agents to attend (in their handlers)
        await asyncio.sleep(1)
        
        # Start meeting
        await sdk.meeting.start_meeting(
            "agent_alice",
            meeting_id,
            MeetingMessage(speaker="Alice", content="Let's discuss the project"),
            next_speaker_external_id="agent_bob"
        )
        
        # Agents speak in their turns...
        # When done:
        await sdk.meeting.end_meeting("agent_alice", meeting_id)
```

---

## Summary

This API design provides:

✓ **Type-safe generic message support**  
✓ **Clean async/await interface**  
✓ **Context manager support**  
✓ **Comprehensive error handling**  
✓ **Flexible handler system**  
✓ **Event-driven architecture**  
✓ **Intuitive method names**  
✓ **Rich documentation**

Next steps:
1. Review and approve API design
2. Begin implementation
3. Write comprehensive tests
4. Create example applications
