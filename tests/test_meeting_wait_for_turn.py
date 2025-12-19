"""Tests for wait_for_turn functionality in meeting system."""

import asyncio
import pytest
from uuid import UUID

from agent_messaging import AgentMessaging
from agent_messaging.exceptions import MeetingNotActiveError


@pytest.mark.asyncio
class TestMeetingWaitForTurn:
    """Test suite for wait_for_turn parameter in attend_meeting and speak methods."""

    async def test_attend_meeting_without_wait(self, sdk: AgentMessaging):
        """Test attend_meeting with wait_for_turn=False (default behavior)."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")
        await sdk.register_agent("charlie", "org_001", "Charlie")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob", "charlie"],
            turn_duration=60.0,
        )

        # Attend without waiting (default)
        result = await sdk.meeting.attend_meeting("alice", meeting_id)

        # Should return boolean
        assert isinstance(result, bool)
        assert result is True

    async def test_attend_meeting_with_wait_before_start(self, sdk: AgentMessaging):
        """Test attend_meeting with wait_for_turn=True before meeting starts."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")
        await sdk.register_agent("charlie", "org_001", "Charlie")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob", "charlie"],
            turn_duration=60.0,
        )

        # Attend all agents first (non-blocking)
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)

        # Start meeting (alice will be first speaker)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Bob attends with wait_for_turn=True
        # This should wait until it's Bob's turn
        async def bob_waits():
            success, messages = await sdk.meeting.attend_meeting(
                "bob", meeting_id, wait_for_turn=True
            )
            return success, messages

        # Alice speaks first, passing turn to Bob
        async def alice_speaks():
            await asyncio.sleep(0.5)  # Small delay
            await sdk.meeting.speak("alice", meeting_id, {"text": "Hello from Alice!"})

        # Run both concurrently
        bob_task = asyncio.create_task(bob_waits())
        alice_task = asyncio.create_task(alice_speaks())

        await alice_task  # Wait for Alice to speak
        success, messages = await bob_task  # Wait for Bob's turn

        # Verify results
        assert success is True
        assert isinstance(messages, list)
        # Should have at least Alice's message
        assert len(messages) >= 1
        alice_msg = next((m for m in messages if m["sender_external_id"] == "alice"), None)
        assert alice_msg is not None
        assert alice_msg["content"]["text"] == "Hello from Alice!"

    async def test_speak_without_wait(self, sdk: AgentMessaging):
        """Test speak with wait_for_turn=False (default, raises error if not turn)."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Alice can speak (her turn)
        msg_id = await sdk.meeting.speak("alice", meeting_id, {"text": "Alice speaking"})
        assert isinstance(msg_id, UUID)

    async def test_speak_with_wait(self, sdk: AgentMessaging):
        """Test speak with wait_for_turn=True (waits for turn, then speaks)."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Bob waits for his turn to speak
        async def bob_waits_and_speaks():
            msg_id, messages = await sdk.meeting.speak(
                "bob", meeting_id, {"text": "Bob speaking"}, wait_for_turn=True
            )
            return msg_id, messages

        # Alice speaks first
        async def alice_speaks():
            await asyncio.sleep(0.5)  # Small delay
            await sdk.meeting.speak("alice", meeting_id, {"text": "Alice speaking first"})

        # Run both concurrently
        bob_task = asyncio.create_task(bob_waits_and_speaks())
        alice_task = asyncio.create_task(alice_speaks())

        await alice_task  # Wait for Alice to speak
        msg_id, messages = await bob_task  # Wait for Bob to speak

        # Verify results
        assert isinstance(msg_id, UUID)
        assert isinstance(messages, list)
        # Should have Alice's message
        assert len(messages) >= 1
        alice_msg = next((m for m in messages if m["sender_external_id"] == "alice"), None)
        assert alice_msg is not None
        assert alice_msg["content"]["text"] == "Alice speaking first"

    async def test_wait_for_turn_with_multiple_messages(self, sdk: AgentMessaging):
        """Test that wait_for_turn returns all messages that occurred while waiting."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")
        await sdk.register_agent("charlie", "org_001", "Charlie")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob", "charlie"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Charlie waits for his turn
        async def charlie_waits():
            success, messages = await sdk.meeting.attend_meeting(
                "charlie", meeting_id, wait_for_turn=True
            )
            return success, messages

        # Alice and Bob speak
        async def alice_and_bob_speak():
            await asyncio.sleep(0.5)
            # Alice speaks (turn 1)
            await sdk.meeting.speak("alice", meeting_id, {"text": "Message from Alice"})
            await asyncio.sleep(0.5)
            # Bob speaks (turn 2)
            await sdk.meeting.speak("bob", meeting_id, {"text": "Message from Bob"})
            # Charlie's turn is next

        # Run concurrently
        charlie_task = asyncio.create_task(charlie_waits())
        speakers_task = asyncio.create_task(alice_and_bob_speak())

        await speakers_task
        success, messages = await charlie_task

        # Verify Charlie received both messages
        assert success is True
        assert len(messages) >= 2

        alice_msg = next((m for m in messages if m["sender_external_id"] == "alice"), None)
        bob_msg = next((m for m in messages if m["sender_external_id"] == "bob"), None)

        assert alice_msg is not None
        assert bob_msg is not None
        assert alice_msg["content"]["text"] == "Message from Alice"
        assert bob_msg["content"]["text"] == "Message from Bob"

    async def test_wait_for_turn_meeting_ends(self, sdk: AgentMessaging):
        """Test wait_for_turn behavior when meeting ends while waiting."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Bob waits for his turn
        async def bob_waits():
            success, messages = await sdk.meeting.attend_meeting(
                "bob", meeting_id, wait_for_turn=True
            )
            return success, messages

        # Alice ends meeting instead of passing turn
        async def alice_ends_meeting():
            await asyncio.sleep(0.5)
            await sdk.meeting.speak("alice", meeting_id, {"text": "Goodbye!"})
            await asyncio.sleep(0.5)
            await sdk.meeting.end_meeting("alice", meeting_id)

        # Run concurrently
        bob_task = asyncio.create_task(bob_waits())
        alice_task = asyncio.create_task(alice_ends_meeting())

        await alice_task
        success, messages = await bob_task

        # Bob should get messages even though meeting ended
        assert success is True
        assert isinstance(messages, list)

    async def test_speak_wait_for_turn_meeting_ends(self, sdk: AgentMessaging):
        """Test speak with wait_for_turn when meeting ends before agent's turn."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Bob waits to speak
        async def bob_waits_to_speak():
            try:
                msg_id, messages = await sdk.meeting.speak(
                    "bob", meeting_id, {"text": "Bob speaking"}, wait_for_turn=True
                )
                return msg_id, messages
            except MeetingNotActiveError:
                return None, []

        # Alice ends meeting
        async def alice_ends_meeting():
            await asyncio.sleep(0.5)
            await sdk.meeting.end_meeting("alice", meeting_id)

        # Run concurrently
        bob_task = asyncio.create_task(bob_waits_to_speak())
        alice_task = asyncio.create_task(alice_ends_meeting())

        await alice_task
        result, messages = await bob_task

        # Bob should get MeetingNotActiveError
        assert result is None

    async def test_concurrent_wait_for_turn(self, sdk: AgentMessaging):
        """Test multiple agents waiting for their turns concurrently."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")
        await sdk.register_agent("charlie", "org_001", "Charlie")
        await sdk.register_agent("dave", "org_001", "Dave")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob", "charlie", "dave"],
            turn_duration=60.0,
        )

        # All attend
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)
        await sdk.meeting.attend_meeting("dave", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # All agents wait for their turn and speak
        async def agent_waits_and_speaks(agent_name: str):
            msg_id, messages = await sdk.meeting.speak(
                agent_name, meeting_id, {"text": f"Message from {agent_name}"}, wait_for_turn=True
            )
            return agent_name, msg_id, len(messages)

        # Create tasks for all agents
        tasks = [
            asyncio.create_task(agent_waits_and_speaks("alice")),
            asyncio.create_task(agent_waits_and_speaks("bob")),
            asyncio.create_task(agent_waits_and_speaks("charlie")),
            asyncio.create_task(agent_waits_and_speaks("dave")),
        ]

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # Verify all spoke successfully
        assert len(results) == 4
        for agent_name, msg_id, message_count in results:
            assert isinstance(msg_id, UUID)
            assert message_count >= 0  # May have received messages while waiting

    async def test_wait_for_turn_message_ordering(self, sdk: AgentMessaging):
        """Test that messages returned by wait_for_turn are properly ordered."""
        # Register org and agents
        await sdk.register_organization("org_001", "Test Org")
        await sdk.register_agent("alice", "org_001", "Alice")
        await sdk.register_agent("bob", "org_001", "Bob")
        await sdk.register_agent("charlie", "org_001", "Charlie")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="alice",
            participant_external_ids=["alice", "bob", "charlie"],
            turn_duration=60.0,
        )

        # Attend and start
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)
        await sdk.meeting.start_meeting("alice", meeting_id)

        # Charlie waits
        async def charlie_waits():
            msg_id, messages = await sdk.meeting.speak(
                "charlie", meeting_id, {"text": "Charlie speaking"}, wait_for_turn=True
            )
            return msg_id, messages

        # Alice and Bob speak in order
        async def alice_and_bob_speak():
            await asyncio.sleep(0.5)
            await sdk.meeting.speak("alice", meeting_id, {"text": "First message", "order": 1})
            await asyncio.sleep(0.5)
            await sdk.meeting.speak("bob", meeting_id, {"text": "Second message", "order": 2})

        # Run concurrently
        charlie_task = asyncio.create_task(charlie_waits())
        speakers_task = asyncio.create_task(alice_and_bob_speak())

        await speakers_task
        msg_id, messages = await charlie_task

        # Verify messages are in order
        assert len(messages) >= 2

        # Find Alice and Bob's messages
        alice_msg = next((m for m in messages if m["sender_external_id"] == "alice"), None)
        bob_msg = next((m for m in messages if m["sender_external_id"] == "bob"), None)

        assert alice_msg is not None
        assert bob_msg is not None

        # Check ordering by comparing indices in the list
        alice_idx = messages.index(alice_msg)
        bob_idx = messages.index(bob_msg)
        assert alice_idx < bob_idx, "Messages should be in chronological order"
