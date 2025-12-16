#!/usr/bin/env python3
"""
Example 4: Multi-Agent Meeting - Brainstorming Session

This example demonstrates multi-agent meetings with turn-based coordination.
Agents take turns sharing ideas in a structured brainstorming session.

Handlers are registered globally and process messages for ALL agents.
"""

import asyncio
import logging
from agent_messaging import (
    AgentMessaging,
    register_meeting_handler,
    MessageContext,
)
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


# Global SDK reference for use in handler
_sdk: "AgentMessaging[dict, dict, IdeaMessage] | None" = None


# Register global meeting handler
@register_meeting_handler
async def handle_meeting(message: IdeaMessage, context: MessageContext) -> IdeaMessage:
    """Global handler for meeting messages."""
    recipient = context.receiver_id
    logger.info(f"{recipient.capitalize()}: Received meeting message: {message}")

    if _sdk is None:
        return None  # type: ignore

    # Attend the meeting if not already attending
    try:
        await _sdk.meeting.attend_meeting(recipient, context.meeting_id)
        logger.info(f"{recipient.capitalize()}: Joined meeting")
    except Exception as e:
        logger.debug(f"{recipient.capitalize()}: Already attending or error: {e}")

    # If it's this agent's turn, share an idea
    status = await _sdk.meeting.get_meeting_status(context.meeting_id)
    if status.get("current_speaker_external_id") == recipient:
        logger.info(f"{recipient.capitalize()}: It's my turn! Sharing idea...")

        # Different ideas for each agent
        if recipient == "alice":
            idea = IdeaMessage(
                speaker="alice",
                idea="We should add a dark mode toggle to improve user experience.",
                category="feature",
            )
        elif recipient == "bob":
            idea = IdeaMessage(
                speaker="bob",
                idea="The API response times are too slow. We need to optimize database queries.",
                category="improvement",
            )
        elif recipient == "charlie":
            idea = IdeaMessage(
                speaker="charlie",
                idea="We should add comprehensive error logging to help with debugging.",
                category="bug_fix",
            )
        else:
            idea = IdeaMessage(
                speaker=recipient,
                idea="Great point, I agree with the previous speaker.",
                category="general",
            )

        return idea

    return None  # type: ignore


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

    # Let the meeting run for a while
    await asyncio.sleep(5)

    # Check meeting status
    status = await sdk.meeting.get_meeting_status(meeting_id)
    logger.info(f"Moderator: Meeting status - {status['status']}")

    # Let the meeting continue
    await asyncio.sleep(5)

    # End the meeting
    logger.info("Moderator: Ending meeting")
    await sdk.meeting.end_meeting("moderator", meeting_id)

    # Get meeting history
    history = await sdk.meeting.get_meeting_history(meeting_id)
    logger.info(f"Moderator: Meeting had {len(history)} messages")


async def main():
    """Run the brainstorming meeting example."""
    global _sdk
    logger.info("Starting multi-agent meeting brainstorming example")

    # Use 3 type parameters: T_OneWay=dict, T_Conversation=dict, T_Meeting=IdeaMessage
    async with AgentMessaging[dict, dict, IdeaMessage]() as sdk:
        _sdk = sdk

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
