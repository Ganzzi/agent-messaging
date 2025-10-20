"""Unit tests for MeetingManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agent_messaging.messaging.meeting import MeetingManager
from agent_messaging.models import (
    Agent,
    Meeting,
    MeetingStatus,
    ParticipantStatus,
    MeetingParticipant,
)
from agent_messaging.exceptions import (
    AgentNotFoundError,
    MeetingPermissionError,
    MeetingError,
    NotYourTurnError,
)


@pytest.fixture
def mock_meeting_repo():
    """Mock meeting repository for testing."""
    repo = MagicMock()
    repo.create = AsyncMock(return_value=uuid4())
    repo.get_meeting = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.add_participant = AsyncMock()
    repo.update_participant_status = AsyncMock()
    repo.get_participants = AsyncMock(return_value=[])
    repo.get_participant = AsyncMock(return_value=None)
    repo.update_meeting_status = AsyncMock()
    repo.set_current_speaker = AsyncMock()
    repo.get_current_speaker = AsyncMock(return_value=None)
    repo.record_event = AsyncMock(return_value=uuid4())
    repo.get_meeting_history = AsyncMock(return_value=[])
    repo.start_meeting = AsyncMock()
    repo.end_meeting = AsyncMock()
    repo._execute = AsyncMock()
    return repo


@pytest.fixture
def mock_message_repo():
    """Mock message repository for testing."""
    repo = MagicMock()
    repo.create = AsyncMock(return_value=uuid4())
    return repo


@pytest.fixture
def mock_agent_repo():
    """Mock agent repository for testing."""
    repo = MagicMock()
    repo.get_by_external_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_event_handler():
    """Mock event handler for testing."""
    handler = MagicMock()
    handler.emit_event = AsyncMock()
    handler.emit_participant_joined = AsyncMock()
    handler.emit_meeting_started = AsyncMock()
    handler.emit_turn_changed = AsyncMock()
    handler.emit_meeting_ended = AsyncMock()
    handler.emit_participant_left = AsyncMock()
    return handler


@pytest.fixture
def meeting_manager(
    mock_meeting_repo,
    mock_message_repo,
    mock_agent_repo,
    mock_event_handler,
):
    """MeetingManager instance for testing."""
    return MeetingManager(
        meeting_repo=mock_meeting_repo,
        message_repo=mock_message_repo,
        agent_repo=mock_agent_repo,
        event_handler=mock_event_handler,
    )


@pytest.fixture
def sample_meeting():
    """Sample meeting for testing."""
    return Meeting(
        id=uuid4(),
        host_id=uuid4(),
        status=MeetingStatus.CREATED,
        current_speaker_id=None,
        turn_duration=None,
        turn_started_at=None,
        created_at=MagicMock(),
        started_at=None,
        ended_at=None,
    )


class TestMeetingManager:
    """Test cases for MeetingManager."""

    @pytest.mark.asyncio
    async def test_create_meeting_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo
    ):
        """Test successful meeting creation."""
        # Setup mock host
        host = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.create = AsyncMock(return_value=uuid4())

        # Create meeting
        meeting_id = await meeting_manager.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["bob", "charlie"],
            turn_duration=60.0,
        )

        # Verify meeting was created
        assert meeting_id is not None
        mock_meeting_repo.create.assert_called_once()
        call_args = mock_meeting_repo.create.call_args
        assert call_args[1]["host_id"] == host.id
        assert call_args[1]["turn_duration"] == 60.0

    @pytest.mark.asyncio
    async def test_create_meeting_host_not_found(self, meeting_manager, mock_agent_repo):
        """Test meeting creation with non-existent host."""
        mock_agent_repo.get_by_external_id = AsyncMock(side_effect=AgentNotFoundError("alice"))

        with pytest.raises(AgentNotFoundError):
            await meeting_manager.create_meeting("alice", ["bob"], 60.0)

    @pytest.mark.asyncio
    async def test_attend_meeting_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test successful meeting attendance."""
        # Setup mock agent and meeting
        agent = Agent(
            id=uuid4(),
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        participant = MeetingParticipant(
            id=uuid4(),
            meeting_id=sample_meeting.id,
            agent_id=agent.id,
            status=ParticipantStatus.INVITED,
            join_order=1,
            joined_at=None,
            left_at=None,
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=agent)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)
        mock_meeting_repo.get_participant = AsyncMock(return_value=participant)

        # Attend meeting
        result = await meeting_manager.attend_meeting("bob", sample_meeting.id)

        # Verify success
        assert result is True
        mock_meeting_repo.update_participant_status.assert_called_once_with(
            participant_id=participant.id,
            status=ParticipantStatus.ATTENDING,
        )

    @pytest.mark.asyncio
    async def test_start_meeting_success(
        self,
        meeting_manager,
        mock_agent_repo,
        mock_meeting_repo,
        sample_meeting,
        mock_event_handler,
    ):
        """Test successful meeting start."""
        # Setup host and meeting
        host = Agent(
            id=sample_meeting.host_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)
        mock_meeting_repo.get_participants = AsyncMock(
            return_value=[MagicMock(agent_id=uuid4(), status=ParticipantStatus.ATTENDING)]
        )

        # Start meeting
        await meeting_manager.start_meeting("alice", sample_meeting.id)

        # Verify meeting started
        mock_meeting_repo.start_meeting.assert_called_with(
            sample_meeting.id,
        )
        mock_event_handler.emit_meeting_started.assert_called()

    @pytest.mark.asyncio
    async def test_start_meeting_not_host(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test starting meeting by non-host."""
        # Setup non-host agent
        non_host = Agent(
            id=uuid4(),  # Different from host_id
            external_id="bob",
            organization_id=uuid4(),
            name="Bob",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        mock_agent_repo.get_by_external_id = AsyncMock(return_value=non_host)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)

        with pytest.raises(MeetingPermissionError, match="Agent 'bob' is not the host"):
            await meeting_manager.start_meeting("bob", sample_meeting.id)

    @pytest.mark.asyncio
    async def test_speak_success(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting, mock_message_repo
    ):
        """Test successful speaking in meeting."""
        # Setup speaker and active meeting
        speaker = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=speaker.id,
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=speaker)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=active_meeting)
        mock_meeting_repo.get_participant = AsyncMock(
            return_value=MeetingParticipant(
                id=uuid4(),
                meeting_id=active_meeting.id,
                agent_id=speaker.id,
                status=ParticipantStatus.ATTENDING,
                join_order=1,
                joined_at=MagicMock(),
                left_at=None,
            )
        )
        mock_meeting_repo.get_participants = AsyncMock(
            return_value=[
                MeetingParticipant(
                    id=uuid4(),
                    meeting_id=active_meeting.id,
                    agent_id=speaker.id,
                    status=ParticipantStatus.ATTENDING,
                    join_order=1,
                    joined_at=MagicMock(),
                    left_at=None,
                )
            ]
        )
        mock_message_repo.create = AsyncMock(return_value=uuid4())

        # Speak
        message_id = await meeting_manager.speak(
            "alice", active_meeting.id, {"text": "Hello everyone!"}
        )

        # Verify message created
        assert message_id is not None
        mock_message_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_not_your_turn(
        self, meeting_manager, mock_agent_repo, mock_meeting_repo, sample_meeting
    ):
        """Test speaking when it's not your turn."""
        # Setup speaker and meeting where different agent has turn
        speaker = Agent(
            id=uuid4(),
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        other_agent_id = uuid4()
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=other_agent_id,  # Different agent has turn
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )
        participant = MeetingParticipant(
            id=uuid4(),
            meeting_id=active_meeting.id,
            agent_id=speaker.id,
            status=ParticipantStatus.ATTENDING,
            join_order=1,
            joined_at=MagicMock(),
            left_at=None,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=speaker)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=active_meeting)
        mock_meeting_repo.get_participant = AsyncMock(return_value=participant)

        with pytest.raises(NotYourTurnError, match="It's not alice's turn"):
            await meeting_manager.speak("alice", active_meeting.id, {"text": "Hello!"})

    @pytest.mark.asyncio
    async def test_end_meeting_success(
        self,
        meeting_manager,
        mock_agent_repo,
        mock_meeting_repo,
        sample_meeting,
        mock_event_handler,
    ):
        """Test successful meeting end."""
        # Setup host and active meeting
        host = Agent(
            id=sample_meeting.host_id,
            external_id="alice",
            organization_id=uuid4(),
            name="Alice",
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
        active_meeting = Meeting(
            id=sample_meeting.id,
            host_id=sample_meeting.host_id,
            status=MeetingStatus.ACTIVE,
            current_speaker_id=sample_meeting.current_speaker_id,
            turn_duration=sample_meeting.turn_duration,
            turn_started_at=sample_meeting.turn_started_at,
            created_at=sample_meeting.created_at,
            started_at=sample_meeting.started_at,
            ended_at=sample_meeting.ended_at,
        )

        mock_agent_repo.get_by_external_id = AsyncMock(return_value=host)
        mock_meeting_repo.get_by_id = AsyncMock(return_value=active_meeting)

        # End meeting
        await meeting_manager.end_meeting("alice", active_meeting.id)

        # Verify meeting ended
        mock_meeting_repo.end_meeting.assert_called_with(
            active_meeting.id,
        )
        mock_event_handler.emit_meeting_ended.assert_called()

    @pytest.mark.asyncio
    async def test_get_meeting_status(self, meeting_manager, mock_meeting_repo, sample_meeting):
        """Test getting meeting status."""
        mock_meeting_repo.get_by_id = AsyncMock(return_value=sample_meeting)
        mock_meeting_repo.get_participants = AsyncMock(
            return_value=[
                MagicMock(agent_id=uuid4(), status=ParticipantStatus.ATTENDING, join_order=1)
            ]
        )

        status = await meeting_manager.get_meeting_status(sample_meeting.id)

        # Verify status returned
        assert status is not None
        assert "meeting_id" in status
        assert "participants" in status
        assert "current_speaker" in status

    @pytest.mark.asyncio
    async def test_get_meeting_history(self, meeting_manager, mock_message_repo):
        """Test getting meeting history."""
        meeting_id = uuid4()
        mock_messages = [
            {
                "id": uuid4(),
                "sender_id": uuid4(),
                "message_type": "user_defined",
                "content": {"text": "Hello"},
                "created_at": MagicMock(),
                "metadata": None,
            },
            {
                "id": uuid4(),
                "sender_id": uuid4(),
                "message_type": "user_defined",
                "content": {"text": "Hi back"},
                "created_at": MagicMock(),
                "metadata": None,
            },
        ]
        # Mock the direct query execution
        mock_result = MagicMock()
        mock_result.result.return_value = mock_messages
        mock_message_repo._execute = AsyncMock(return_value=mock_result)

        history = await meeting_manager.get_meeting_history(meeting_id)

        # Verify history returned
        assert len(history) == 2
        assert history[0]["content"]["text"] == "Hello"
        assert history[1]["content"]["text"] == "Hi back"
        mock_message_repo._execute.assert_called_once()
