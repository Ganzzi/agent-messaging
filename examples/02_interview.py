#!/usr/bin/env python3
"""
Example 2: Synchronous Conversation - Interview

This example demonstrates synchronous conversations (request-response)
using an interview scenario where questions require immediate answers.

Handlers are registered globally and process messages for ALL agents.
"""

import asyncio
import logging
from typing import Union
from agent_messaging import (
    AgentMessaging,
    register_conversation_handler,
    MessageContext,
)
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterviewQuestion(BaseModel):
    """Interview question message."""

    question: str
    topic: str
    difficulty: str = "medium"


class InterviewAnswer(BaseModel):
    """Interview answer message."""

    answer: str
    confidence: int  # 1-10 scale
    notes: str = ""


# Type for conversation messages (union of question and answer)
ConversationMessage = Union[InterviewQuestion, InterviewAnswer]


# Register global conversation handler - processes ALL conversation messages
@register_conversation_handler
async def handle_conversation(
    message: ConversationMessage, context: MessageContext
) -> ConversationMessage:
    """Global handler for all conversation messages."""
    # Route based on receiver and message type
    if context.receiver_id == "candidate" and isinstance(message, InterviewQuestion):
        logger.info(f"Candidate: Received question: {message.question}")

        # Simulate thinking time
        await asyncio.sleep(0.5)

        # Generate answer based on question
        if "Python async" in message.question:
            return InterviewAnswer(
                answer="I've used asyncio extensively for building concurrent applications. Key concepts include event loops, coroutines, and proper exception handling.",
                confidence=8,
                notes="Have built several async web services and data processing pipelines.",
            )
        elif "microservices" in message.question:
            return InterviewAnswer(
                answer="I would focus on domain-driven design, clear service boundaries, event-driven communication, and comprehensive monitoring.",
                confidence=7,
                notes="Experience with Kubernetes orchestration and service mesh patterns.",
            )
        elif "test-driven" in message.question:
            return InterviewAnswer(
                answer="TDD helps ensure code quality and maintainability. I write tests first, then implement minimal code to pass them.",
                confidence=9,
                notes="Strong advocate for automated testing and CI/CD integration.",
            )
        else:
            return InterviewAnswer(
                answer="I need more time to formulate a proper answer.", confidence=5
            )

    # For interviewer receiving answers, just return None (no further response)
    return None  # type: ignore


async def interviewer_agent(sdk: AgentMessaging[dict, ConversationMessage, dict]):
    """Interviewer agent that asks questions."""
    questions = [
        InterviewQuestion(
            question="What is your experience with Python async programming?",
            topic="Python",
            difficulty="medium",
        ),
        InterviewQuestion(
            question="How would you design a scalable microservices architecture?",
            topic="System Design",
            difficulty="hard",
        ),
        InterviewQuestion(
            question="What are your thoughts on test-driven development?",
            topic="Development Practices",
            difficulty="easy",
        ),
    ]

    logger.info("Interviewer: Starting interview")

    for i, question in enumerate(questions, 1):
        logger.info(f"Interviewer: Asking question {i}: {question.question}")

        try:
            # Send question and wait for response
            answer = await sdk.conversation.send_and_wait(
                sender_external_id="interviewer",
                recipient_external_id="candidate",
                message=question,
                timeout=60.0,  # 60 second timeout
            )

            if isinstance(answer, InterviewAnswer):
                logger.info(f"Interviewer: Received answer - Confidence: {answer.confidence}/10")
                logger.info(f"Interviewer: Answer: {answer.answer}")

                if answer.notes:
                    logger.info(f"Interviewer: Notes: {answer.notes}")

        except Exception as e:
            logger.error(f"Interviewer: Failed to get answer for question {i}: {e}")

        # Brief pause between questions
        await asyncio.sleep(0.5)

    logger.info("Interviewer: Interview completed")


async def main():
    """Run the interview example."""
    logger.info("Starting synchronous conversation interview example")

    # Use 3 type parameters: T_OneWay=dict, T_Conversation=ConversationMessage, T_Meeting=dict
    async with AgentMessaging[dict, ConversationMessage, dict]() as sdk:
        # Register organization
        await sdk.register_organization("interview_co", "Interview Company")

        # Register agents
        await sdk.register_agent("interviewer", "interview_co", "Technical Interviewer")
        await sdk.register_agent("candidate", "interview_co", "Job Candidate")

        # Run the interview
        await interviewer_agent(sdk)

    logger.info("Interview example completed")


if __name__ == "__main__":
    asyncio.run(main())
