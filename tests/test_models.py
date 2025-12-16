"""Unit tests for all Pydantic models."""

import pytest
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, Optional

from agent_messaging.models import (
    # Enums
    MessageType,
    SessionType,
    SessionStatus,
    MeetingStatus,
    ParticipantStatus,
    MeetingEventType,
    # Core Models
    Organization,
    Agent,
    Session,
    Meeting,
    MeetingParticipant,
    Message,
    MeetingEvent,
    # Meeting Event Data Models
    MeetingEventPayload,
    # DTOs
    CreateOrganizationRequest,
    CreateAgentRequest,
    CreateMeetingRequest,
    # Response Models
    OrganizationResponse,
    AgentResponse,
)
from agent_messaging.handlers import MessageContext


class TestEnums:
    """Test all enum classes."""

    def test_message_type_enum(self):
        """Test MessageType enum values."""
        assert MessageType.USER_DEFINED == "user_defined"
        assert MessageType.SYSTEM == "system"
        assert MessageType.TIMEOUT == "timeout"
        assert MessageType.ENDING == "ending"

        # Test all values are strings
        for member in MessageType:
            assert isinstance(member.value, str)

    def test_session_type_enum(self):
        """Test SessionType enum values."""
        assert SessionType.SYNC == "sync"
        # ASYNC removed - sessions are now unified

    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.WAITING == "waiting"
        assert SessionStatus.ENDED == "ended"

    def test_meeting_status_enum(self):
        """Test MeetingStatus enum values."""
        assert MeetingStatus.CREATED == "created"
        assert MeetingStatus.READY == "ready"
        assert MeetingStatus.ACTIVE == "active"
        assert MeetingStatus.ENDED == "ended"

    def test_participant_status_enum(self):
        """Test ParticipantStatus enum values."""
        assert ParticipantStatus.INVITED == "invited"
        assert ParticipantStatus.ATTENDING == "attending"
        assert ParticipantStatus.WAITING == "waiting"
        assert ParticipantStatus.SPEAKING == "speaking"
        assert ParticipantStatus.LEFT == "left"

    def test_meeting_event_type_enum(self):
        """Test MeetingEventType enum values."""
        assert MeetingEventType.MEETING_STARTED == "meeting_started"
        assert MeetingEventType.MEETING_ENDED == "meeting_ended"
        assert MeetingEventType.TURN_CHANGED == "turn_changed"
        assert MeetingEventType.PARTICIPANT_JOINED == "participant_joined"
        assert MeetingEventType.PARTICIPANT_LEFT == "participant_left"
        assert MeetingEventType.TIMEOUT_OCCURRED == "timeout_occurred"


class TestCoreModels:
    """Test core data models."""

    def test_organization_model(self):
        """Test Organization model."""
        org_id = uuid4()
        created_at = datetime.now()
        updated_at = datetime.now()

        org = Organization(
            id=org_id,
            external_id="org_001",
            name="Test Organization",
            created_at=created_at,
            updated_at=updated_at,
        )

        assert org.id == org_id
        assert org.external_id == "org_001"
        assert org.name == "Test Organization"
        assert org.created_at == created_at
        assert org.updated_at == updated_at

    def test_agent_model(self):
        """Test Agent model."""
        agent_id = uuid4()
        org_id = uuid4()
        created_at = datetime.now()
        updated_at = datetime.now()

        agent = Agent(
            id=agent_id,
            external_id="agent_001",
            organization_id=org_id,
            name="Test Agent",
            created_at=created_at,
            updated_at=updated_at,
        )

        assert agent.id == agent_id
        assert agent.external_id == "agent_001"
        assert agent.organization_id == org_id
        assert agent.name == "Test Agent"
        assert agent.created_at == created_at
        assert agent.updated_at == updated_at

    def test_session_model(self):
        """Test Session model."""
        session_id = uuid4()
        agent_a_id = uuid4()
        agent_b_id = uuid4()
        created_at = datetime.now()
        updated_at = datetime.now()
        ended_at = datetime.now()

        session = Session(
            id=session_id,
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            status=SessionStatus.ACTIVE,
            locked_agent_id=None,
            created_at=created_at,
            updated_at=updated_at,
            ended_at=ended_at,
        )

        assert session.id == session_id
        assert session.agent_a_id == agent_a_id
        assert session.agent_b_id == agent_b_id
        assert session.status == SessionStatus.ACTIVE
        assert session.locked_agent_id is None
        assert session.created_at == created_at
        assert session.updated_at == updated_at
        assert session.ended_at == ended_at

    def test_session_model_optional_fields(self):
        """Test Session model with optional fields."""
        session = Session(
            id=uuid4(),
            agent_a_id=uuid4(),
            agent_b_id=uuid4(),
            status=SessionStatus.WAITING,
            locked_agent_id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            ended_at=None,
        )

        assert session.locked_agent_id is not None
        assert session.ended_at is None

    def test_meeting_model(self):
        """Test Meeting model."""
        meeting_id = uuid4()
        host_id = uuid4()
        current_speaker_id = uuid4()
        created_at = datetime.now()
        started_at = datetime.now()
        ended_at = datetime.now()
        turn_started_at = datetime.now()

        meeting = Meeting(
            id=meeting_id,
            host_id=host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=current_speaker_id,
            turn_duration=30.0,
            turn_started_at=turn_started_at,
            created_at=created_at,
            started_at=started_at,
            ended_at=ended_at,
        )

        assert meeting.id == meeting_id
        assert meeting.host_id == host_id
        assert meeting.status == MeetingStatus.ACTIVE
        assert meeting.current_speaker_id == current_speaker_id
        assert meeting.turn_duration == 30.0
        assert meeting.turn_started_at == turn_started_at
        assert meeting.created_at == created_at
        assert meeting.started_at == started_at
        assert meeting.ended_at == ended_at

    def test_meeting_model_optional_fields(self):
        """Test Meeting model with optional fields."""
        meeting = Meeting(
            id=uuid4(),
            host_id=uuid4(),
            status=MeetingStatus.CREATED,
            current_speaker_id=None,
            turn_duration=None,
            turn_started_at=None,
            created_at=datetime.now(),
            started_at=None,
            ended_at=None,
        )

        assert meeting.current_speaker_id is None
        assert meeting.turn_duration is None
        assert meeting.turn_started_at is None
        assert meeting.started_at is None
        assert meeting.ended_at is None

    def test_meeting_participant_model(self):
        """Test MeetingParticipant model."""
        participant_id = uuid4()
        meeting_id = uuid4()
        agent_id = uuid4()
        joined_at = datetime.now()
        left_at = datetime.now()

        participant = MeetingParticipant(
            id=participant_id,
            meeting_id=meeting_id,
            agent_id=agent_id,
            status=ParticipantStatus.SPEAKING,
            join_order=1,
            is_locked=True,
            joined_at=joined_at,
            left_at=left_at,
        )

        assert participant.id == participant_id
        assert participant.meeting_id == meeting_id
        assert participant.agent_id == agent_id
        assert participant.status == ParticipantStatus.SPEAKING
        assert participant.join_order == 1
        assert participant.is_locked is True
        assert participant.joined_at == joined_at
        assert participant.left_at == left_at

    def test_meeting_participant_model_defaults(self):
        """Test MeetingParticipant model defaults."""
        participant = MeetingParticipant(
            id=uuid4(),
            meeting_id=uuid4(),
            agent_id=uuid4(),
            status=ParticipantStatus.ATTENDING,
            join_order=2,
            joined_at=datetime.now(),
        )

        assert participant.is_locked is False
        assert participant.left_at is None

    def test_message_model_generic(self):
        """Test generic Message model."""
        message_id = uuid4()
        sender_id = uuid4()
        recipient_id = uuid4()
        content = {"text": "Hello, world!"}
        created_at = datetime.now()
        metadata = {"priority": "high"}

        message = Message[Dict[str, Any]](
            id=message_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=None,
            meeting_id=None,
            message_type=MessageType.USER_DEFINED,
            content=content,
            read_at=None,
            created_at=created_at,
            metadata=metadata,
        )

        assert message.id == message_id
        assert message.sender_id == sender_id
        assert message.recipient_id == recipient_id
        assert message.session_id is None
        assert message.meeting_id is None
        assert message.message_type == MessageType.USER_DEFINED
        assert message.content == content
        assert message.read_at is None
        assert message.created_at == created_at
        assert message.metadata == metadata

    def test_message_model_optional_fields(self):
        """Test Message model with optional fields."""
        message = Message[str](
            id=uuid4(),
            sender_id=uuid4(),
            recipient_id=None,
            session_id=uuid4(),
            meeting_id=uuid4(),
            message_type=MessageType.SYSTEM,
            content="System message",
            read_at=datetime.now(),
            created_at=datetime.now(),
            metadata=None,
        )

        assert message.recipient_id is None
        assert message.session_id is not None
        assert message.meeting_id is not None
        assert message.read_at is not None
        assert message.metadata is None

    def test_meeting_event_model(self):
        """Test MeetingEvent model."""
        event_id = uuid4()
        meeting_id = uuid4()
        agent_id = uuid4()
        created_at = datetime.now()
        data = {"speaker_id": str(uuid4())}

        event = MeetingEvent(
            id=event_id,
            meeting_id=meeting_id,
            event_type="turn_changed",
            agent_id=agent_id,
            data=data,
            created_at=created_at,
        )

        assert event.id == event_id
        assert event.meeting_id == meeting_id
        assert event.event_type == "turn_changed"
        assert event.agent_id == agent_id
        assert event.data == data
        assert event.created_at == created_at

    def test_meeting_event_model_optional_fields(self):
        """Test MeetingEvent model with optional fields."""
        event = MeetingEvent(
            id=uuid4(),
            meeting_id=uuid4(),
            event_type="meeting_started",
            agent_id=None,
            data=None,
            created_at=datetime.now(),
        )

        assert event.agent_id is None
        assert event.data is None


class TestAPIContextModels:
    """Test API context models."""

    def test_message_context_model(self):
        """Test MessageContext model."""
        from agent_messaging.handlers import HandlerContext

        sender_id = "alice"
        receiver_id = "bob"
        organization_id = "org1"
        message_id = 123
        session_id = "session-123"
        meeting_id = 456

        context = MessageContext(
            sender_id=sender_id,
            receiver_id=receiver_id,
            organization_id=organization_id,
            handler_context=HandlerContext.CONVERSATION,
            message_id=message_id,
            session_id=session_id,
            meeting_id=meeting_id,
        )

        assert context.sender_id == sender_id
        assert context.receiver_id == receiver_id
        assert context.organization_id == organization_id
        assert context.handler_context == HandlerContext.CONVERSATION
        assert context.message_id == message_id
        assert context.session_id == session_id
        assert context.meeting_id == meeting_id

    def test_message_context_optional_fields(self):
        """Test MessageContext with optional fields."""
        from agent_messaging.handlers import HandlerContext

        context = MessageContext(
            sender_id="alice",
            receiver_id="bob",
            organization_id="org1",
            handler_context=HandlerContext.ONE_WAY,
        )

        assert context.message_id is None
        assert context.session_id is None
        assert context.meeting_id is None
        assert context.metadata == {}

    def test_meeting_event_payload_model(self):
        """Test MeetingEventPayload model."""
        meeting_id = uuid4()
        event_type = MeetingEventType.TURN_CHANGED
        timestamp = datetime.now()
        data = {"next_speaker": "alice", "turn_number": 2}

        payload = MeetingEventPayload(
            meeting_id=meeting_id, event_type=event_type, timestamp=timestamp, data=data
        )

        assert payload.meeting_id == meeting_id
        assert payload.event_type == event_type
        assert payload.timestamp == timestamp
        assert payload.data == data

    def test_meeting_event_payload_default_data(self):
        """Test MeetingEventPayload with default data."""
        payload = MeetingEventPayload(
            meeting_id=uuid4(),
            event_type=MeetingEventType.MEETING_STARTED,
            timestamp=datetime.now(),
        )

        assert payload.data == {}


class TestDTOs:
    """Test Data Transfer Objects."""

    def test_create_organization_request(self):
        """Test CreateOrganizationRequest."""
        request = CreateOrganizationRequest(external_id="org_001", name="Test Organization")

        assert request.external_id == "org_001"
        assert request.name == "Test Organization"

    def test_create_organization_request_validation(self):
        """Test CreateOrganizationRequest validation."""
        # Valid request
        request = CreateOrganizationRequest(external_id="a", name="a")
        assert request.external_id == "a"
        assert request.name == "a"

        # Invalid - empty external_id
        with pytest.raises(ValueError):
            CreateOrganizationRequest(external_id="", name="Test")

        # Invalid - empty name
        with pytest.raises(ValueError):
            CreateOrganizationRequest(external_id="org_001", name="")

    def test_create_agent_request(self):
        """Test CreateAgentRequest."""
        request = CreateAgentRequest(
            external_id="agent_001", organization_external_id="org_001", name="Test Agent"
        )

        assert request.external_id == "agent_001"
        assert request.organization_external_id == "org_001"
        assert request.name == "Test Agent"

    def test_create_agent_request_validation(self):
        """Test CreateAgentRequest validation."""
        # Valid request
        request = CreateAgentRequest(external_id="a", organization_external_id="b", name="c")
        assert request.external_id == "a"

        # Invalid - empty external_id
        with pytest.raises(ValueError):
            CreateAgentRequest(external_id="", organization_external_id="org_001", name="Agent")

    def test_create_meeting_request(self):
        """Test CreateMeetingRequest."""
        request = CreateMeetingRequest(
            organizer_id="alice", participant_ids=["bob", "charlie"], turn_duration=30.0
        )

        assert request.organizer_id == "alice"
        assert request.participant_ids == ["bob", "charlie"]
        assert request.turn_duration == 30.0

    def test_create_meeting_request_optional_duration(self):
        """Test CreateMeetingRequest with optional turn_duration."""
        request = CreateMeetingRequest(organizer_id="alice", participant_ids=["bob"])

        assert request.turn_duration is None

    def test_create_meeting_request_validation(self):
        """Test CreateMeetingRequest validation."""
        # Valid request
        request = CreateMeetingRequest(organizer_id="alice", participant_ids=["bob"])
        assert request.participant_ids == ["bob"]

        # Invalid - empty participant_ids
        with pytest.raises(ValueError):
            CreateMeetingRequest(organizer_id="alice", participant_ids=[])


class TestResponseModels:
    """Test response models."""

    def test_organization_response(self):
        """Test OrganizationResponse."""
        org_id = uuid4()
        created_at = datetime.now()

        response = OrganizationResponse(
            id=org_id, external_id="org_001", name="Test Organization", created_at=created_at
        )

        assert response.id == org_id
        assert response.external_id == "org_001"
        assert response.name == "Test Organization"
        assert response.created_at == created_at

    def test_agent_response(self):
        """Test AgentResponse."""
        agent_id = uuid4()
        org_id = uuid4()
        created_at = datetime.now()

        response = AgentResponse(
            id=agent_id,
            external_id="agent_001",
            organization_id=org_id,
            name="Test Agent",
            created_at=created_at,
        )

        assert response.id == agent_id
        assert response.external_id == "agent_001"
        assert response.organization_id == org_id
        assert response.name == "Test Agent"
        assert response.created_at == created_at


class TestModelSerialization:
    """Test model serialization and validation."""

    def test_model_json_serialization(self):
        """Test that models can be JSON serialized."""
        org = Organization(
            id=uuid4(),
            external_id="org_001",
            name="Test",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        json_str = org.model_dump_json()
        assert isinstance(json_str, str)
        assert "org_001" in json_str

    def test_model_dict_serialization(self):
        """Test that models can be dict serialized."""
        agent = Agent(
            id=uuid4(),
            external_id="agent_001",
            organization_id=uuid4(),
            name="Test Agent",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        data = agent.model_dump()
        assert isinstance(data, dict)
        assert data["external_id"] == "agent_001"
        assert "id" in data

    def test_model_validation(self):
        """Test model validation."""
        # Valid model
        message = Message[str](
            id=uuid4(), sender_id=uuid4(), content="test", created_at=datetime.now()
        )
        assert message.content == "test"

        # Should handle complex content
        complex_message = Message[Dict[str, Any]](
            id=uuid4(),
            sender_id=uuid4(),
            content={"type": "complex", "data": [1, 2, 3]},
            created_at=datetime.now(),
        )
        assert complex_message.content["type"] == "complex"

    def test_enum_serialization(self):
        """Test enum serialization."""
        session = Session(
            id=uuid4(),
            agent_a_id=uuid4(),
            agent_b_id=uuid4(),
            status=SessionStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        data = session.model_dump()
        assert data["status"] == "active"

    def test_uuid_serialization(self):
        """Test UUID serialization."""
        test_uuid = uuid4()
        org = Organization(
            id=test_uuid,
            external_id="test",
            name="test",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        data = org.model_dump(mode="json")
        assert data["id"] == str(test_uuid)  # Should be string in JSON

    def test_datetime_serialization(self):
        """Test datetime serialization."""
        test_time = datetime(2025, 10, 19, 12, 0, 0)
        meeting = Meeting(
            id=uuid4(), host_id=uuid4(), status=MeetingStatus.CREATED, created_at=test_time
        )

        data = meeting.model_dump(mode="json")
        # Should serialize to ISO format
        assert "2025-10-19T12:00:00" in data["created_at"]
