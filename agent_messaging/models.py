"""Pydantic models for Agent Messaging Protocol."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


# Generic type for user-defined messages
T = TypeVar("T")


# ============================================================================
# Enums
# ============================================================================


class MessageType(str, Enum):
    """Types of messages in the system."""

    USER_DEFINED = "user_defined"
    SYSTEM = "system"
    TIMEOUT = "timeout"
    ENDING = "ending"


class SessionType(str, Enum):
    """Types of conversation sessions."""

    SYNC = "sync"
    ASYNC = "async"
    CONVERSATION = "conversation"


class SessionStatus(str, Enum):
    """Status of conversation sessions."""

    ACTIVE = "active"
    WAITING = "waiting"
    ENDED = "ended"


class MeetingStatus(str, Enum):
    """Status of meetings."""

    CREATED = "created"
    READY = "ready"
    ACTIVE = "active"
    ENDED = "ended"


class ParticipantStatus(str, Enum):
    """Status of meeting participants."""

    INVITED = "invited"
    ATTENDING = "attending"
    WAITING = "waiting"
    SPEAKING = "speaking"
    LEFT = "left"


class MeetingEventType(str, Enum):
    """Types of meeting events."""

    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
    TURN_CHANGED = "turn_changed"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    TIMEOUT_OCCURRED = "timeout_occurred"


# ============================================================================
# Core Models
# ============================================================================


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


class Meeting(BaseModel):
    """Meeting model."""

    id: UUID
    host_id: UUID
    status: MeetingStatus
    current_speaker_id: Optional[UUID] = None
    turn_duration: Optional[float] = None  # seconds
    turn_started_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MeetingParticipant(BaseModel):
    """Meeting participant model."""

    id: UUID
    meeting_id: UUID
    agent_id: UUID
    status: ParticipantStatus
    join_order: int
    is_locked: bool = False
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None


class Message(Generic[T], BaseModel):
    """Generic message model."""

    id: UUID
    sender_id: UUID
    recipient_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    message_type: MessageType = MessageType.USER_DEFINED
    content: T
    read_at: Optional[datetime] = None
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class MeetingEvent(BaseModel):
    """Meeting event model."""

    id: UUID
    meeting_id: UUID
    event_type: str  # Using str to allow custom event types
    agent_id: Optional[UUID] = None
    data: Optional[Dict[str, Any]] = None
    created_at: datetime


# ============================================================================
# API Context Models
# ============================================================================


class MessageContext(BaseModel):
    """Context provided to message handlers."""

    sender_id: str
    recipient_id: str
    message_id: UUID
    timestamp: datetime
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None


# ============================================================================
# Meeting Event Data Models (Type-Safe)
# ============================================================================


class MeetingStartedEventData(BaseModel):
    """Data for meeting started event."""

    host_id: UUID
    participant_ids: list[UUID]


class MeetingEndedEventData(BaseModel):
    """Data for meeting ended event."""

    host_id: UUID


class TurnChangedEventData(BaseModel):
    """Data for turn changed event."""

    previous_speaker_id: Optional[UUID] = None
    current_speaker_id: Optional[UUID] = None


class ParticipantJoinedEventData(BaseModel):
    """Data for participant joined event."""

    agent_id: UUID


class ParticipantLeftEventData(BaseModel):
    """Data for participant left event."""

    agent_id: UUID


class TimeoutOccurredEventData(BaseModel):
    """Data for timeout occurred event."""

    timed_out_agent_id: UUID
    next_speaker_id: UUID


class MeetingEventPayload(BaseModel):
    """Payload for meeting events (deprecated - use specific event classes)."""

    meeting_id: UUID
    event_type: MeetingEventType
    timestamp: datetime
    data: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Create/Update DTOs
# ============================================================================


class CreateOrganizationRequest(BaseModel):
    """Request to create an organization."""

    external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)


class CreateAgentRequest(BaseModel):
    """Request to create an agent."""

    external_id: str = Field(..., min_length=1, max_length=255)
    organization_external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)


class CreateMeetingRequest(BaseModel):
    """Request to create a meeting."""

    organizer_id: str
    participant_ids: list[str] = Field(..., min_items=1)
    turn_duration: Optional[float] = None


# ============================================================================
# Response Models
# ============================================================================


class OrganizationResponse(BaseModel):
    """Organization response."""

    id: UUID
    external_id: str
    name: str
    created_at: datetime


class AgentResponse(BaseModel):
    """Agent response."""

    id: UUID
    external_id: str
    organization_id: UUID
    name: str
    created_at: datetime
