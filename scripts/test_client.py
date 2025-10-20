#!/usr/bin/env python3
"""Manual test client for Agent Messaging Protocol.

This script demonstrates all features of the AgentMessaging SDK with a real database:
- One-way messaging (broadcast)
- Synchronous conversations (send_and_wait)
- Asynchronous conversations (send_no_wait)
- Multi-agent meetings
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_messaging import AgentMessaging
from agent_messaging.handlers.events import MeetingEventType


# Define message types
class ChatMessage(BaseModel):
    """Simple chat message."""

    text: str
    sender: str


class TaskMessage(BaseModel):
    """Task processing message."""

    task_id: str
    action: str
    data: dict


class IdeaMessage(BaseModel):
    """Brainstorming idea message."""

    speaker: str
    idea: str
    priority: int = 1


# Global response storage for testing
responses = {}


async def test_one_way_messaging(sdk: AgentMessaging):
    """Test one-way messaging (broadcast)."""
    print("\n" + "=" * 60)
    print("TEST 1: One-Way Messaging (Broadcast)")
    print("=" * 60)

    # Send to single recipient
    print("\n📤 Sending message to single recipient (Bob)...")
    await sdk.one_way.send(
        sender_external_id="alice",
        recipient_external_ids=["bob"],
        message=ChatMessage(text="Hello Bob!", sender="alice"),
    )
    await asyncio.sleep(0.5)  # Give handler time to process

    # Broadcast to multiple recipients
    print("\n📤 Broadcasting message to multiple recipients...")
    await sdk.one_way.send(
        sender_external_id="alice",
        recipient_external_ids=["bob", "charlie", "dave"],
        message=ChatMessage(text="Team announcement!", sender="alice"),
    )
    await asyncio.sleep(0.5)  # Give handlers time to process

    print("\n✅ One-way messaging test complete")


async def test_sync_conversation(sdk: AgentMessaging):
    """Test synchronous conversations (send_and_wait)."""
    print("\n" + "=" * 60)
    print("TEST 2: Synchronous Conversations (Request-Response)")
    print("=" * 60)

    print("\n📤 Alice sends request to Bob and waits for response...")
    response = await sdk.conversation.send_and_wait(
        sender_external_id="alice",
        recipient_external_id="bob",
        message=ChatMessage(text="What's your status?", sender="alice"),
        timeout=10.0,
    )

    print(f"✅ Received response: {response.text}")
    print("\n✅ Synchronous conversation test complete")


async def test_async_conversation(sdk: AgentMessaging):
    """Test asynchronous conversations (send_no_wait)."""
    print("\n" + "=" * 60)
    print("TEST 3: Asynchronous Conversations (Non-Blocking)")
    print("=" * 60)

    print("\n📤 Alice sends message to Charlie without waiting...")
    await sdk.conversation.send_no_wait(
        sender_external_id="alice",
        recipient_external_id="charlie",
        message=ChatMessage(text="Check this out when you can", sender="alice"),
    )

    print("\n⏳ Alice continues with other work...")
    await asyncio.sleep(1.0)  # Simulate other work

    print("\n📥 Charlie checks for unread messages...")
    messages = await sdk.conversation.get_unread_messages("charlie")
    print(f"   Found {len(messages)} unread message(s)")
    for msg in messages:
        print(f"   - {msg['text']}")

    print("\n✅ Asynchronous conversation test complete")


async def test_meeting(sdk: AgentMessaging):
    """Test multi-agent meetings."""
    print("\n" + "=" * 60)
    print("TEST 4: Multi-Agent Meeting (Turn-Based)")
    print("=" * 60)

    # Create meeting
    print("\n👥 Alice creates a brainstorming meeting...")
    meeting_id = await sdk.meeting.create_meeting(
        organizer_external_id="alice",
        participant_external_ids=["bob", "charlie"],
        turn_duration=60.0,  # 60 seconds per turn
    )
    print(f"   Meeting ID: {meeting_id}")

    # Participants attend
    print("\n📝 Participants attend meeting...")
    await sdk.meeting.attend_meeting("bob", meeting_id)
    print("   ✅ Bob attended")
    await sdk.meeting.attend_meeting("charlie", meeting_id)
    print("   ✅ Charlie attended")

    # Start meeting
    print("\n🎤 Alice starts the meeting...")
    await sdk.meeting.start_meeting(
        organizer_external_id="alice",
        meeting_id=meeting_id,
        initial_message=IdeaMessage(
            speaker="alice", idea="Let's discuss the new feature!", priority=3
        ),
        next_speaker="bob",
    )
    await asyncio.sleep(0.5)

    # Bob speaks
    print("\n🎤 Bob speaks...")
    await sdk.meeting.speak(
        speaker_external_id="bob",
        meeting_id=meeting_id,
        message=IdeaMessage(
            speaker="bob", idea="I think we should focus on user experience", priority=2
        ),
        next_speaker="charlie",
    )
    await asyncio.sleep(0.5)

    # Charlie speaks
    print("\n🎤 Charlie speaks...")
    await sdk.meeting.speak(
        speaker_external_id="charlie",
        meeting_id=meeting_id,
        message=IdeaMessage(
            speaker="charlie", idea="Performance optimization is also important", priority=2
        ),
        next_speaker="alice",
    )
    await asyncio.sleep(0.5)

    # End meeting
    print("\n🛑 Alice ends the meeting...")
    await sdk.meeting.end_meeting("alice", meeting_id)
    await asyncio.sleep(0.5)

    print("\n✅ Meeting test complete")


async def main():
    """Main test execution."""
    print("\n🧪 Agent Messaging Protocol - Manual Client Test")
    print("=" * 60)
    print("\nThis script tests all features of the AgentMessaging SDK:")
    print("  1. One-way messaging (broadcast)")
    print("  2. Synchronous conversations")
    print("  3. Asynchronous conversations")
    print("  4. Multi-agent meetings")

    try:
        # Initialize SDK
        print("\n🔧 Initializing SDK...")
        async with AgentMessaging[ChatMessage]() as sdk:

            # Register organization
            print("\n📋 Setting up organization and agents...")
            await sdk.register_organization("test_org", "Test Organization")

            # Register agents
            await sdk.register_agent("alice", "test_org", "Alice")
            await sdk.register_agent("bob", "test_org", "Bob")
            await sdk.register_agent("charlie", "test_org", "Charlie")
            await sdk.register_agent("dave", "test_org", "Dave")
            print("   ✅ Organization and agents registered")

            # Register shared message handler
            @sdk.register_handler()
            async def message_handler(message, context):
                """Shared handler for all agents."""
                recipient = context.recipient_external_id

                # Log received message
                if hasattr(message, "text"):
                    print(f"   📨 {recipient} received: {message.text}")
                elif hasattr(message, "idea"):
                    print(f"   💡 {recipient} heard: {message.idea}")

                # Return response for sync conversations
                if context.sender_external_id == "alice" and recipient == "bob":
                    if hasattr(message, "text") and "status" in message.text.lower():
                        return ChatMessage(
                            text="Status: All systems operational!", sender=recipient
                        )

                return None

            # Register event handler for meetings
            @sdk.register_event_handler(MeetingEventType.MEETING_STARTED)
            async def on_meeting_started(event):
                print(f"   🎉 Meeting started event received")

            @sdk.register_event_handler(MeetingEventType.TURN_CHANGED)
            async def on_turn_changed(event):
                print(f"   🔄 Turn changed event received")

            @sdk.register_event_handler(MeetingEventType.MEETING_ENDED)
            async def on_meeting_ended(event):
                print(f"   👋 Meeting ended event received")

            print("   ✅ Handlers registered")

            # Run tests
            await test_one_way_messaging(sdk)
            await test_sync_conversation(sdk)
            await test_async_conversation(sdk)
            await test_meeting(sdk)

            print("\n" + "=" * 60)
            print("✨ All tests completed successfully!")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
