#!/usr/bin/env python3
"""
Example 4: Multi-Agent Meeting - Brainstorming Session with Wait-for-Turn

This example demonstrates multi-agent meetings with turn-based coordination.
Agents take turns sharing ideas in a structured brainstorming session.

This example showcases:
- Meeting creation and lifecycle management
- Turn-based messaging coordination with wait_for_turn parameter
- Receiving messages that occurred while waiting for a turn
- Event handlers for meeting lifecycle events
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
from agent_messaging.models import MeetingEventType, MeetingEvent
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IdeaMessage(BaseModel):
    """Brainstorming idea message."""

    speaker: str
    idea: str
    category: str  # "feature", "improvement", "bug_fix", "architecture"


async def setup_event_handlers(sdk: "AgentMessaging[dict, dict, IdeaMessage]"):
    """Set up event handlers for meeting lifecycle events."""

    async def on_meeting_started(event: MeetingEvent):
        """Called when a meeting starts."""
        logger.info(
            f"🎬 EVENT: Meeting {event.meeting_id} started with "
            f"{len(event.data.participant_ids)} participants"
        )

    async def on_turn_changed(event: MeetingEvent):
        """Called when the speaking turn changes."""
        logger.info(f"🔄 EVENT: Turn changed to agent {event.data.current_speaker_id}")

    async def on_participant_joined(event: MeetingEvent):
        """Called when a participant joins the meeting."""
        logger.info(f"👋 EVENT: Participant joined meeting")

    async def on_meeting_ended(event: MeetingEvent):
        """Called when a meeting ends."""
        logger.info(f"🏁 EVENT: Meeting {event.meeting_id} ended")

    # Register event handlers
    sdk._event_handler.register_handler(MeetingEventType.MEETING_STARTED, on_meeting_started)
    sdk._event_handler.register_handler(MeetingEventType.TURN_CHANGED, on_turn_changed)
    sdk._event_handler.register_handler(MeetingEventType.PARTICIPANT_JOINED, on_participant_joined)
    sdk._event_handler.register_handler(MeetingEventType.MEETING_ENDED, on_meeting_ended)


async def participant_agent(
    sdk: "AgentMessaging[dict, dict, IdeaMessage]", agent_name: str, meeting_id, idea_data: dict
):
    """Participant agent that waits for their turn and shares an idea."""
    logger.info(f"{agent_name}: Waiting for my turn to speak...")

    # Wait for turn and speak (with wait_for_turn=True)
    # This will block until it's the agent's turn, then speak and return messages
    message_id, messages = await sdk.meeting.speak(
        agent_external_id=agent_name,
        meeting_id=meeting_id,
        message=IdeaMessage(**idea_data),
        wait_for_turn=True,  # Block until it's my turn
    )

    logger.info(f"{agent_name}: ✅ Spoke (message ID: {message_id})")

    # Log messages that occurred while waiting
    if messages:
        logger.info(f"{agent_name}: 📬 Received {len(messages)} messages while waiting:")
        for msg in messages:
            sender = msg["sender_external_id"]
            content = msg["content"]
            logger.info(
                f"  - {sender}: {content.get('idea', 'N/A')} [{content.get('category', 'N/A')}]"
            )
    else:
        logger.info(f"{agent_name}: (No messages received while waiting)")


async def main():
    """Run the brainstorming meeting example with wait-for-turn functionality."""
    logger.info("🚀 Starting multi-agent meeting brainstorming example with wait-for-turn")

    # Use 3 type parameters: T_OneWay=dict, T_Conversation=dict, T_Meeting=IdeaMessage
    async with AgentMessaging[dict, dict, IdeaMessage]() as sdk:
        # Set up event handlers to monitor meeting lifecycle
        await setup_event_handlers(sdk)

        # Register organization
        await sdk.register_organization("brainstorm_co", "Brainstorming Company")

        # Register agents
        await sdk.register_agent("moderator", "brainstorm_co", "Meeting Moderator")
        await sdk.register_agent("alice", "brainstorm_co", "Alice")
        await sdk.register_agent("bob", "brainstorm_co", "Bob")
        await sdk.register_agent("charlie", "brainstorm_co", "Charlie")

        logger.info("📋 Moderator: Creating meeting...")

        # Create meeting
        meeting_id = await sdk.meeting.create_meeting(
            organizer_external_id="moderator",
            participant_external_ids=["moderator", "alice", "bob", "charlie"],
            turn_duration=60.0,  # 60 seconds per turn
        )

        logger.info(f"✅ Moderator: Created meeting {meeting_id}")

        # All participants attend the meeting (non-blocking)
        logger.info("📝 All participants attending meeting...")
        await sdk.meeting.attend_meeting("moderator", meeting_id)
        await sdk.meeting.attend_meeting("alice", meeting_id)
        await sdk.meeting.attend_meeting("bob", meeting_id)
        await sdk.meeting.attend_meeting("charlie", meeting_id)

        # Start the meeting
        logger.info("🎬 Moderator: Starting meeting...")
        await sdk.meeting.start_meeting(
            host_external_id="moderator",
            meeting_id=meeting_id,
        )

        logger.info("✅ Meeting started! Participants will now speak in turn.")

        # Define ideas for each participant
        moderator_idea = {
            "speaker": "moderator",
            "idea": "Welcome everyone! Let's brainstorm new features for our product.",
            "category": "introduction",
        }

        alice_idea = {
            "speaker": "alice",
            "idea": "We should add a dark mode toggle to improve user experience.",
            "category": "feature",
        }

        bob_idea = {
            "speaker": "bob",
            "idea": "The API response times are too slow. We need to optimize database queries.",
            "category": "improvement",
        }

        charlie_idea = {
            "speaker": "charlie",
            "idea": "We should add comprehensive error logging to help with debugging.",
            "category": "bug_fix",
        }

        # All participants wait for their turn concurrently (with wait_for_turn=True)
        # This demonstrates the new functionality where agents automatically wait
        tasks = [
            asyncio.create_task(participant_agent(sdk, "moderator", meeting_id, moderator_idea)),
            asyncio.create_task(participant_agent(sdk, "alice", meeting_id, alice_idea)),
            asyncio.create_task(participant_agent(sdk, "bob", meeting_id, bob_idea)),
            asyncio.create_task(participant_agent(sdk, "charlie", meeting_id, charlie_idea)),
        ]

        # Wait for all participants to speak
        await asyncio.gather(*tasks)

        logger.info("💬 All participants have shared their ideas")

        # Check meeting status
        status = await sdk.meeting.get_meeting_status(meeting_id)
        logger.info(f"📊 Meeting status: {status['status']}")

        # Get meeting history
        history = await sdk.meeting.get_meeting_history(meeting_id)
        logger.info(f"📜 Meeting history: {len(history)} messages total")

        # Summary of ideas shared
        ideas_by_category = {}
        for msg in history:
            content = msg.get("content", {})
            if "category" in content:
                category = content["category"]
                ideas_by_category[category] = ideas_by_category.get(category, 0) + 1

        logger.info(f"📈 Ideas by category: {ideas_by_category}")

        # End the meeting
        logger.info("🏁 Moderator: Ending meeting")
        await sdk.meeting.end_meeting("moderator", meeting_id)

    logger.info("✅ Brainstorming meeting example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
