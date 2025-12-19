#!/usr/bin/env python3
"""
Example 4: Multi-Agent Meeting - Brainstorming Session

This example demonstrates multi-agent meetings with turn-based coordination.
Agents take turns sharing ideas in a structured brainstorming session.

This example showcases:
- Meeting creation and lifecycle management
- Turn-based messaging coordination
- Event handlers for meeting lifecycle events
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
from agent_messaging.models import MeetingEventType, MeetingEvent
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IdeaMessage(BaseModel):
    """Brainstorming idea message."""

    speaker: str
    idea: str
    category: str  # "feature", "improvement", "bug_fix", "architecture"


class MeetingSummary(BaseModel):
    """Meeting summary message."""

    total_ideas: int
    categories: dict[str, int]
    key_insights: list[str]


async def setup_event_handlers(sdk: "AgentMessaging[dict, dict, IdeaMessage]"):
    """Set up event handlers for meeting lifecycle events."""

    async def on_meeting_started(event: MeetingEvent):
        """Called when a meeting starts."""
        logger.info(
            f"EVENT: Meeting {event.meeting_id} started with "
            f"{len(event.data.participant_ids)} participants"
        )

    async def on_turn_changed(event: MeetingEvent):
        """Called when the speaking turn changes."""
        logger.info(
            f"EVENT: Turn changed to {event.data.current_speaker_id} "
            f"(previous: {event.data.previous_speaker_id})"
        )

    async def on_participant_joined(event: MeetingEvent):
        """Called when a participant joins the meeting."""
        logger.info(f"EVENT: Participant {event.data.agent_external_id} joined meeting")

    async def on_meeting_ended(event: MeetingEvent):
        """Called when a meeting ends."""
        logger.info(f"EVENT: Meeting {event.meeting_id} ended")

    # Register event handlers
    sdk._event_handler.register_handler(MeetingEventType.MEETING_STARTED, on_meeting_started)
    sdk._event_handler.register_handler(MeetingEventType.TURN_CHANGED, on_turn_changed)
    sdk._event_handler.register_handler(MeetingEventType.PARTICIPANT_JOINED, on_participant_joined)
    sdk._event_handler.register_handler(MeetingEventType.MEETING_ENDED, on_meeting_ended)


async def moderator_agent(sdk: "AgentMessaging[dict, dict, IdeaMessage]"):
    """Moderator agent that manages the meeting."""
    logger.info("Moderator: Starting brainstorming meeting")

    # Create meeting
    meeting_id = await sdk.meeting.create_meeting(
        organizer_external_id="moderator",
        participant_external_ids=["alice", "bob", "charlie"],
        turn_duration=30.0,  # 30 seconds per turn
    )

    logger.info(f"Moderator: Created meeting {meeting_id}")

    # Start the meeting
    await sdk.meeting.start_meeting(
        organizer_external_id="moderator",
        meeting_id=meeting_id,
        initial_message=IdeaMessage(
            speaker="moderator",
            idea="Welcome to our brainstorming session! Let's discuss new features for our product.",
            category="introduction",
        ),
        next_speaker="alice",
    )

    logger.info("Moderator: Meeting started, participants can now speak")

    # Let the meeting run for a while to allow events to fire
    await asyncio.sleep(2)

    # Simulate Alice speaking
    logger.info("Alice: Sharing my idea...")
    await sdk.meeting.send_message(
        sender_external_id="alice",
        meeting_id=meeting_id,
        message=IdeaMessage(
            speaker="alice",
            idea="We should add a dark mode toggle to improve user experience.",
            category="feature",
        ),
        next_speaker="bob",
    )

    await asyncio.sleep(1)

    # Simulate Bob speaking
    logger.info("Bob: Sharing my idea...")
    await sdk.meeting.send_message(
        sender_external_id="bob",
        meeting_id=meeting_id,
        message=IdeaMessage(
            speaker="bob",
            idea="The API response times are too slow. We need to optimize database queries.",
            category="improvement",
        ),
        next_speaker="charlie",
    )

    await asyncio.sleep(1)

    # Simulate Charlie speaking
    logger.info("Charlie: Sharing my idea...")
    await sdk.meeting.send_message(
        sender_external_id="charlie",
        meeting_id=meeting_id,
        message=IdeaMessage(
            speaker="charlie",
            idea="We should add comprehensive error logging to help with debugging.",
            category="bug_fix",
        ),
        next_speaker=None,  # No next speaker
    )

    await asyncio.sleep(1)

    # Check meeting status
    status = await sdk.meeting.get_meeting_status(meeting_id)
    logger.info(f"Moderator: Meeting status - {status['status']}")

    # End the meeting
    logger.info("Moderator: Ending meeting")
    await sdk.meeting.end_meeting("moderator", meeting_id)

    # Get meeting history
    history = await sdk.meeting.get_meeting_history(meeting_id)
    logger.info(f"Moderator: Meeting had {len(history)} messages")

    # Summary of ideas shared
    ideas_by_category = {}
    for msg in history:
        if "category" in msg["message"]:
            category = msg["message"]["category"]
            ideas_by_category[category] = ideas_by_category.get(category, 0) + 1

    logger.info(f"Moderator: Ideas by category: {ideas_by_category}")


async def main():
    """Run the brainstorming meeting example."""
    logger.info("Starting multi-agent meeting brainstorming example")

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

        # Run the moderator
        await moderator_agent(sdk)

    logger.info("Brainstorming meeting example completed")


if __name__ == "__main__":
    asyncio.run(main())
