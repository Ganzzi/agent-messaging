#!/usr/bin/env python3
"""
Example 4: Multi-Agent Meeting - Brainstorming Session

This example demonstrates multi-agent meetings with turn-based coordination.
Agents take turns sharing ideas in a structured brainstorming session.
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
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


async def moderator_agent(sdk: AgentMessaging):
    """Moderator agent that manages the meeting."""
    logger.info("Moderator: Starting brainstorming meeting")

    # Create meeting
    meeting_id = await sdk.meeting.create_meeting(
        organizer_external_id="moderator",
        participant_external_ids=["alice", "bob", "charlie"],
        turn_duration=30.0,  # 30 seconds per turn
    )

    logger.info(f"Moderator: Created meeting {meeting_id}")

    # Register event handler to track meeting progress
    @sdk.register_event_handler("meeting_started")
    async def on_meeting_started(event):
        logger.info(f"Moderator: Meeting {event.meeting_id} has started!")

    @sdk.register_event_handler("turn_changed")
    async def on_turn_changed(event):
        if event.current_speaker_external_id:
            logger.info(f"Moderator: Turn changed to {event.current_speaker_external_id}")
        else:
            logger.info("Moderator: Meeting ended")

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

    # Let the meeting run for a while
    await asyncio.sleep(10)

    # Check meeting status
    status = await sdk.meeting.get_meeting_status(meeting_id)
    logger.info(f"Moderator: Meeting status - {status['status']}")
    logger.info(f"Moderator: Participants: {len(status['participants'])}")

    # Let the meeting continue
    await asyncio.sleep(20)

    # End the meeting
    logger.info("Moderator: Ending meeting")
    await sdk.meeting.end_meeting("moderator", meeting_id)

    # Get meeting history
    history = await sdk.meeting.get_meeting_history(meeting_id)
    logger.info(f"Moderator: Meeting had {len(history)} messages")

    # Summarize ideas
    ideas = [msg for msg in history if isinstance(msg.content, dict) and "idea" in msg.content]
    categories = {}
    for idea in ideas:
        cat = idea.content.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    summary = MeetingSummary(
        total_ideas=len(ideas),
        categories=categories,
        key_insights=["Great collaboration!", "Several innovative ideas generated"],
    )

    logger.info(
        f"Moderator: Meeting summary - {summary.total_ideas} ideas across {len(categories)} categories"
    )


async def alice_agent(sdk: AgentMessaging):
    """Alice agent participant."""
    logger.info("Alice: Joining brainstorming meeting")


async def bob_agent(sdk: AgentMessaging):
    """Bob agent participant."""
    logger.info("Bob: Joining brainstorming meeting")


async def charlie_agent(sdk: AgentMessaging):
    """Charlie agent participant."""
    logger.info("Charlie: Joining brainstorming meeting")


async def main():
    """Run the brainstorming meeting example."""
    logger.info("Starting multi-agent meeting brainstorming example")

    async with AgentMessaging() as sdk:  # Generic type for mixed messages
        # Register organization
        await sdk.register_organization("brainstorm_co", "Brainstorming Company")

        # Register agents
        await sdk.register_agent("moderator", "brainstorm_co", "Meeting Moderator")
        await sdk.register_agent("alice", "brainstorm_co", "Alice")
        await sdk.register_agent("bob", "brainstorm_co", "Bob")
        await sdk.register_agent("charlie", "brainstorm_co", "Charlie")

        # Register meeting handlers for participants
        async def participant_handler(message, context):
            recipient = context.recipient_external_id
            logger.info(f"{recipient.capitalize()}: Received meeting message: {message}")

            # Attend the meeting if not already attending
            try:
                await sdk.meeting.attend_meeting(recipient, context.meeting_id)
                logger.info(f"{recipient.capitalize()}: Joined meeting")
            except Exception as e:
                logger.debug(f"{recipient.capitalize()}: Already attending or error: {e}")

            # If it's this agent's turn, share an idea
            status = await sdk.meeting.get_meeting_status(context.meeting_id)
            if status.get("current_speaker_external_id") == recipient:
                logger.info(f"{recipient.capitalize()}: It's my turn! Sharing idea...")

                # Different ideas for each agent
                if recipient == "alice":
                    idea = IdeaMessage(
                        speaker="alice",
                        idea="We should add a dark mode toggle to improve user experience.",
                        category="feature",
                    )
                    next_speaker = "bob"
                elif recipient == "bob":
                    idea = IdeaMessage(
                        speaker="bob",
                        idea="The API response times are too slow. We need to optimize database queries.",
                        category="improvement",
                    )
                    next_speaker = "charlie"
                elif recipient == "charlie":
                    idea = IdeaMessage(
                        speaker="charlie",
                        idea="We should add comprehensive error logging to help with debugging.",
                        category="bug_fix",
                    )
                    next_speaker = "alice"  # Back to Alice for another round

                await sdk.meeting.speak(
                    speaker_external_id=recipient,
                    meeting_id=context.meeting_id,
                    message=idea,
                    next_speaker=next_speaker,
                )

                logger.info(
                    f"{recipient.capitalize()}: Idea shared, passing turn to {next_speaker}"
                )

        # Register handlers for each participant
        sdk.register_meeting_handler("alice")(participant_handler)
        sdk.register_meeting_handler("bob")(participant_handler)
        sdk.register_meeting_handler("charlie")(participant_handler)

        # Start all agents concurrently
        await asyncio.gather(
            moderator_agent(sdk), alice_agent(sdk), bob_agent(sdk), charlie_agent(sdk)
        )

    logger.info("Brainstorming meeting example completed")


if __name__ == "__main__":
    asyncio.run(main())
