#!/usr/bin/env python3
"""
Example 2: Synchronous Conversation - Interview

This example demonstrates synchronous conversations (request-response)
using an interview scenario where questions require immediate answers.
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
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


async def interviewer_agent(sdk: AgentMessaging):
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

            logger.info(f"Interviewer: Received answer - Confidence: {answer.confidence}/10")
            logger.info(f"Interviewer: Answer: {answer.answer}")

            if answer.notes:
                logger.info(f"Interviewer: Notes: {answer.notes}")

        except Exception as e:
            logger.error(f"Interviewer: Failed to get answer for question {i}: {e}")

        # Brief pause between questions
        await asyncio.sleep(1)

    logger.info("Interviewer: Interview completed")


async def candidate_agent(sdk: AgentMessaging):
    """Candidate agent that answers questions."""
    logger.info("Candidate: Ready for interview")


async def main():
    """Run the interview example."""
    logger.info("Starting synchronous conversation interview example")

    async with AgentMessaging() as sdk:  # Generic type for mixed messages
        # Register organization
        await sdk.register_organization("interview_co", "Interview Company")

        # Register agents
        await sdk.register_agent("interviewer", "interview_co", "Technical Interviewer")
        await sdk.register_agent("candidate", "interview_co", "Job Candidate")

        # Register global handler for all agents
        @sdk.register_handler()
        async def global_handler(message, context):
            # Route based on recipient and message type
            if context.recipient_external_id == "candidate":
                if isinstance(message, InterviewQuestion):
                    logger.info(f"Candidate: Received question: {message.question}")

                    # Simulate thinking time
                    await asyncio.sleep(2)

                    # Generate answer based on question
                    if "Python async" in message.question:
                        answer = InterviewAnswer(
                            answer="I've used asyncio extensively for building concurrent applications. Key concepts include event loops, coroutines, and proper exception handling.",
                            confidence=8,
                            notes="Have built several async web services and data processing pipelines.",
                        )
                    elif "microservices" in message.question:
                        answer = InterviewAnswer(
                            answer="I would focus on domain-driven design, clear service boundaries, event-driven communication, and comprehensive monitoring.",
                            confidence=7,
                            notes="Experience with Kubernetes orchestration and service mesh patterns.",
                        )
                    elif "test-driven" in message.question:
                        answer = InterviewAnswer(
                            answer="TDD helps ensure code quality and maintainability. I write tests first, then implement minimal code to pass them.",
                            confidence=9,
                            notes="Strong advocate for automated testing and CI/CD integration.",
                        )
                    else:
                        answer = InterviewAnswer(
                            answer="I need more time to formulate a proper answer.", confidence=5
                        )

                    # Send answer back to interviewer
                    await sdk.conversation.send_no_wait(
                        sender_external_id="candidate",
                        recipient_external_id="interviewer",
                        message=answer,
                    )

                    logger.info("Candidate: Answer sent")
            elif context.recipient_external_id == "interviewer":
                # Interviewer doesn't need a handler in this example
                pass

        # Start both agents concurrently
        await asyncio.gather(interviewer_agent(sdk), candidate_agent(sdk))

    logger.info("Interview example completed")


if __name__ == "__main__":
    asyncio.run(main())
