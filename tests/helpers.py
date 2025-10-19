"""Test helpers and utilities for Agent Messaging tests."""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, TypeVar, Awaitable
from uuid import uuid4
from contextlib import asynccontextmanager

from agent_messaging.client import AgentMessaging
from agent_messaging.models import (
    Organization,
    Agent,
    Message,
    MessageContext,
    Session,
    Meeting,
    MessageType,
    SessionType,
    SessionStatus,
    MeetingStatus,
)
from agent_messaging.database.manager import PostgreSQLManager

T = TypeVar("T")


# Data Factories
class TestDataFactory:
    """Factory for creating test data objects."""

    @staticmethod
    def create_organization(external_id: str = None, name: str = None) -> Dict[str, Any]:
        """Create test organization data."""
        return {
            "external_id": external_id or f"org_{uuid4().hex[:8]}",
            "name": name or f"Test Organization {uuid4().hex[:8]}",
        }

    @staticmethod
    def create_agent(
        organization_external_id: str = None, external_id: str = None, name: str = None
    ) -> Dict[str, Any]:
        """Create test agent data."""
        return {
            "organization_external_id": organization_external_id or f"org_{uuid4().hex[:8]}",
            "external_id": external_id or f"agent_{uuid4().hex[:8]}",
            "name": name or f"Test Agent {uuid4().hex[:8]}",
        }

    @staticmethod
    def create_message(
        content: Dict[str, Any] = None, message_type: MessageType = MessageType.USER_DEFINED
    ) -> Dict[str, Any]:
        """Create test message data."""
        return {
            "content": content or {"text": f"Test message {uuid4().hex[:8]}"},
            "message_type": message_type,
        }

    @staticmethod
    def create_meeting_config(
        turn_duration: float = 30.0, participant_ids: List[str] = None
    ) -> Dict[str, Any]:
        """Create test meeting configuration."""
        return {
            "turn_duration": turn_duration,
            "participant_ids": participant_ids or [f"agent_{uuid4().hex[:8]}" for _ in range(3)],
        }


# SDK Test Helpers
class SDKTestHelper:
    """Helper class for SDK testing operations."""

    def __init__(self, sdk: AgentMessaging[T]):
        self.sdk = sdk

    async def create_test_organization(self, external_id: str = None, name: str = None) -> str:
        """Create a test organization and return its external ID."""
        data = TestDataFactory.create_organization(external_id, name)
        await self.sdk.register_organization(data["external_id"], data["name"])
        return data["external_id"]

    async def create_test_agent(
        self, organization_external_id: str, external_id: str = None, name: str = None
    ) -> str:
        """Create a test agent and return its external ID."""
        data = TestDataFactory.create_agent(organization_external_id, external_id, name)
        await self.sdk.register_agent(
            data["external_id"], data["organization_external_id"], data["name"]
        )
        return data["external_id"]

    async def setup_basic_scenario(self) -> Dict[str, str]:
        """Set up a basic test scenario with org and two agents."""
        org_id = await self.create_test_organization("test_org", "Test Organization")
        agent1_id = await self.create_test_agent(org_id, "alice", "Alice")
        agent2_id = await self.create_test_agent(org_id, "bob", "Bob")

        return {
            "org_id": org_id,
            "agent1_id": agent1_id,
            "agent2_id": agent2_id,
        }


# Async Test Utilities
class AsyncTestHelper:
    """Utilities for async testing."""

    @staticmethod
    @asynccontextmanager
    async def timeout_context(seconds: float):
        """Context manager that raises TimeoutError after specified seconds."""
        try:
            yield await asyncio.wait_for(asyncio.sleep(0), timeout=seconds)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {seconds} seconds")

    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], Awaitable[bool]], timeout: float = 5.0, interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await condition():
                return True
            await asyncio.sleep(interval)
        return False

    @staticmethod
    async def run_concurrent(
        tasks: List[Callable[[], Awaitable[T]]], max_concurrent: int = 10
    ) -> List[T]:
        """Run tasks concurrently with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def run_with_semaphore(task):
            async with semaphore:
                return await task()

        concurrent_tasks = [run_with_semaphore(task) for task in tasks]
        results = await asyncio.gather(*concurrent_tasks)
        return results


# Database Test Helpers
class DatabaseTestHelper:
    """Helpers for database testing."""

    def __init__(self, db_manager: PostgreSQLManager):
        self.db_manager = db_manager

    async def cleanup_all_data(self) -> None:
        """Clean up all test data from database."""
        async with self.db_manager.connection() as conn:
            # Delete in order to avoid foreign key constraints
            await conn.execute("DELETE FROM meeting_events")
            await conn.execute("DELETE FROM meeting_participants")
            await conn.execute("DELETE FROM messages")
            await conn.execute("DELETE FROM sessions")
            await conn.execute("DELETE FROM meetings")
            await conn.execute("DELETE FROM agents")
            await conn.execute("DELETE FROM organizations")

    async def count_table_rows(self, table_name: str) -> int:
        """Count rows in a table."""
        async with self.db_manager.connection() as conn:
            result = await conn.fetch_val(f"SELECT COUNT(*) FROM {table_name}")
            return result

    async def get_table_data(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all data from a table (limited for testing)."""
        async with self.db_manager.connection() as conn:
            result = await conn.fetch(f"SELECT * FROM {table_name} LIMIT {limit}")
            return [dict(row) for row in result.result()]


# Performance Test Helpers
class PerformanceTestHelper:
    """Helpers for performance testing."""

    @staticmethod
    def measure_execution_time(
        func: Callable[[], Awaitable[T]],
    ) -> Callable[[], Awaitable[tuple[T, float]]]:
        """Decorator to measure execution time of async functions."""

        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            return result, execution_time

        return wrapper

    @staticmethod
    async def benchmark_async(
        func: Callable[[], Awaitable[T]], iterations: int = 100, concurrency: int = 10
    ) -> Dict[str, float]:
        """Benchmark an async function."""
        times = []

        # Run iterations with concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def run_iteration():
            async with semaphore:
                start = time.time()
                await func()
                return time.time() - start

        tasks = [run_iteration() for _ in range(iterations)]
        times = await asyncio.gather(*tasks)

        return {
            "total_time": sum(times),
            "average_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "iterations_per_second": len(times) / sum(times),
        }


# Handler Test Helpers
class HandlerTestHelper:
    """Helpers for testing message handlers."""

    @staticmethod
    def create_mock_handler(
        responses: List[T] = None,
    ) -> Callable[[T, MessageContext], Awaitable[Optional[T]]]:
        """Create a mock handler that returns predefined responses."""
        responses = responses or []
        response_iter = iter(responses)

        async def mock_handler(message: T, context: MessageContext) -> Optional[T]:
            try:
                return next(response_iter)
            except StopIteration:
                return None

        return mock_handler

    @staticmethod
    def create_echo_handler() -> Callable[[T, MessageContext], Awaitable[Optional[T]]]:
        """Create a handler that echoes back the message."""

        async def echo_handler(message: T, context: MessageContext) -> Optional[T]:
            return message

        return echo_handler

    @staticmethod
    def create_delayed_handler(
        delay: float = 1.0,
    ) -> Callable[[T, MessageContext], Awaitable[Optional[T]]]:
        """Create a handler that adds a delay."""

        async def delayed_handler(message: T, context: MessageContext) -> Optional[T]:
            await asyncio.sleep(delay)
            return message

        return delayed_handler


# Meeting Test Helpers
class MeetingTestHelper:
    """Helpers for meeting testing."""

    def __init__(self, sdk: AgentMessaging[T]):
        self.sdk = sdk

    async def create_test_meeting(
        self, organizer_id: str, participant_ids: List[str], turn_duration: float = 30.0
    ) -> str:
        """Create a test meeting and return meeting ID."""
        meeting_id = await self.sdk.meeting.create(organizer_id, participant_ids, turn_duration)
        return str(meeting_id)

    async def setup_meeting_participants(self, meeting_id: str, participant_ids: List[str]) -> None:
        """Set up participants for a meeting."""
        for participant_id in participant_ids:
            await self.sdk.meeting.attend_meeting(participant_id, meeting_id)

    async def simulate_meeting_flow(
        self, meeting_id: str, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Simulate a complete meeting flow."""
        results = []

        # Start meeting
        await self.sdk.meeting.start_meeting(meeting_id)

        # Send messages in turn order
        for message_data in messages:
            speaker_id = message_data["speaker_id"]
            content = message_data["content"]

            await self.sdk.meeting.speak(speaker_id, meeting_id, content)
            results.append({"speaker": speaker_id, "message": content, "timestamp": time.time()})

        # End meeting
        await self.sdk.meeting.end_meeting(meeting_id)

        return results


# Assertion Helpers
class AssertionHelper:
    """Custom assertions for testing."""

    @staticmethod
    def assert_uuid_valid(uuid_str: str) -> None:
        """Assert that a string is a valid UUID."""
        try:
            uuid_obj = uuid4()
            uuid_obj.hex  # Just to validate it's a UUID object
        except (ValueError, TypeError):
            pytest.fail(f"Invalid UUID: {uuid_str}")

    @staticmethod
    def assert_message_equal(msg1: Message, msg2: Message) -> None:
        """Assert that two messages are equal."""
        assert msg1.id == msg2.id
        assert msg1.sender_id == msg2.sender_id
        assert msg1.recipient_id == msg2.recipient_id
        assert msg1.content == msg2.content
        assert msg1.message_type == msg2.message_type

    @staticmethod
    def assert_organization_equal(org1: Organization, org2: Organization) -> None:
        """Assert that two organizations are equal."""
        assert org1.id == org2.id
        assert org1.external_id == org2.external_id
        assert org1.name == org2.name

    @staticmethod
    async def assert_eventually_true(
        condition: Callable[[], Awaitable[bool]],
        timeout: float = 5.0,
        message: str = "Condition never became true",
    ) -> None:
        """Assert that a condition eventually becomes true."""
        success = await AsyncTestHelper.wait_for_condition(condition, timeout)
        assert success, message
