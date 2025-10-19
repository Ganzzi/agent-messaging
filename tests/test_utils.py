"""Unit tests for utility modules (locks and timeouts)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agent_messaging.utils.locks import AdvisoryLock, SessionLock
from agent_messaging.utils.timeouts import MeetingTimeoutManager
from agent_messaging.models import MeetingStatus, ParticipantStatus, MessageType


class TestAdvisoryLock:
    """Test cases for AdvisoryLock class."""

    @pytest.fixture
    def mock_connection(self):
        """Mock database connection."""
        conn = MagicMock()
        conn.fetch_val = AsyncMock()
        conn.execute = AsyncMock()
        return conn

    def test_generate_lock_key(self):
        """Test lock key generation from UUID."""
        session_id = uuid4()
        lock_key = AdvisoryLock.generate_lock_key(session_id)

        # Should be a positive integer
        assert isinstance(lock_key, int)
        assert lock_key > 0
        assert lock_key < 2**63  # Within PostgreSQL bigint range

        # Same UUID should generate same key
        lock_key2 = AdvisoryLock.generate_lock_key(session_id)
        assert lock_key == lock_key2

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, mock_connection):
        """Test successful lock acquisition."""
        mock_connection.fetch_val.return_value = True

        result = await AdvisoryLock.acquire_lock(mock_connection, 12345)

        assert result is True
        mock_connection.fetch_val.assert_called_once_with(
            "SELECT pg_try_advisory_lock($1)", [12345]
        )


class TestSessionLock:
    """Test cases for SessionLock class."""

    @pytest.fixture
    def session_id(self):
        """Test session ID."""
        return uuid4()

    @pytest.fixture
    def session_lock(self, session_id):
        """SessionLock instance."""
        return SessionLock(session_id)

    @pytest.fixture
    def mock_connection(self):
        """Mock database connection."""
        conn = MagicMock()
        conn.fetch_val = AsyncMock()
        conn.execute = AsyncMock()
        return conn

    def test_initialization(self, session_lock, session_id):
        """Test SessionLock initialization."""
        assert session_lock.session_id == session_id
        assert session_lock.lock_key == AdvisoryLock.generate_lock_key(session_id)

    @pytest.mark.asyncio
    async def test_acquire_success(self, session_lock, mock_connection):
        """Test successful session lock acquisition."""
        mock_connection.fetch_val.return_value = True

        result = await session_lock.acquire(mock_connection)

        assert result is True
        mock_connection.fetch_val.assert_called_once_with(
            "SELECT pg_try_advisory_lock($1)", [session_lock.lock_key]
        )


class TestMeetingTimeoutManager:
    """Test cases for MeetingTimeoutManager class."""

    @pytest.fixture
    def mock_meeting_repo(self):
        """Mock meeting repository."""
        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        repo.get_participants = AsyncMock()
        repo.set_current_speaker = AsyncMock()
        return repo

    @pytest.fixture
    def mock_message_repo(self):
        """Mock message repository."""
        repo = MagicMock()
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def timeout_manager(self, mock_meeting_repo, mock_message_repo):
        """MeetingTimeoutManager instance."""
        return MeetingTimeoutManager(mock_meeting_repo, mock_message_repo)

    def test_initialization(self, timeout_manager):
        """Test timeout manager initialization."""
        assert timeout_manager._meeting_repo is not None
        assert timeout_manager._message_repo is not None
        assert timeout_manager._timeout_tasks == {}
        assert timeout_manager._check_interval == 5.0

    @pytest.mark.asyncio
    async def test_start_turn_timeout_no_duration(self, timeout_manager):
        """Test starting timeout with no duration (should not start)."""
        meeting_id = uuid4()
        speaker_id = uuid4()

        await timeout_manager.start_turn_timeout(meeting_id, speaker_id, None)

        # Should not create any timeout task
        assert meeting_id not in timeout_manager._timeout_tasks
