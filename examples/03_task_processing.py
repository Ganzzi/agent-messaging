#!/usr/bin/env python3
"""
Example 3: Asynchronous Conversation - Task Processing

This example demonstrates asynchronous conversations where agents
send tasks and check for results later, without blocking.

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


class TaskRequest(BaseModel):
    """Task processing request."""

    task_id: str
    task_type: str  # "data_analysis", "image_processing", "text_summary"
    data: dict
    priority: str = "normal"


class TaskResult(BaseModel):
    """Task processing result."""

    task_id: str
    status: str  # "completed", "failed"
    result: dict
    processing_time: float
    error_message: str = ""


# Type for conversation messages
TaskMessage = Union[TaskRequest, TaskResult]


# Global SDK reference for use in handler
_sdk: "AgentMessaging[dict, TaskMessage, dict] | None" = None


# Register global conversation handler
@register_conversation_handler
async def handle_task(message: TaskMessage, context: MessageContext) -> TaskMessage:
    """Global handler for task processing."""
    if context.receiver_id == "worker" and isinstance(message, TaskRequest):
        logger.info(f"Task Worker: Received task {message.task_id} ({message.task_type})")

        # Simulate processing time based on task type
        if message.task_type == "data_analysis":
            processing_time = 0.5
            result_data = {"sum": sum(message.data["numbers"])}
        elif message.task_type == "text_summary":
            processing_time = 1.0
            result_data = {"summary": f"Summary of {len(message.data['text'])} characters"}
        elif message.task_type == "image_processing":
            processing_time = 0.7
            result_data = {"processed_url": "https://example.com/processed_image.jpg"}
        else:
            processing_time = 0.3
            result_data = {"error": "Unknown task type"}

        # Simulate processing
        await asyncio.sleep(processing_time)

        logger.info(f"Task Worker: Completed task {message.task_id} in {processing_time:.2f}s")

        # Return result
        return TaskResult(
            task_id=message.task_id,
            status="completed",
            result=result_data,
            processing_time=processing_time,
        )

    return None  # type: ignore


async def task_submitter(sdk: "AgentMessaging[dict, TaskMessage, dict]"):
    """Agent that submits tasks asynchronously."""
    logger.info("Task Submitter: Starting task submission")

    tasks = [
        TaskRequest(
            task_id="task_001",
            task_type="data_analysis",
            data={"numbers": [1, 2, 3, 4, 5], "operation": "sum"},
            priority="high",
        ),
        TaskRequest(
            task_id="task_002",
            task_type="text_summary",
            data={
                "text": "This is a long article about artificial intelligence and machine learning..."
            },
            priority="normal",
        ),
        TaskRequest(
            task_id="task_003",
            task_type="image_processing",
            data={"image_url": "https://example.com/image.jpg", "operation": "resize"},
            priority="low",
        ),
    ]

    # Submit all tasks and wait for results
    for task in tasks:
        logger.info(f"Task Submitter: Submitting {task.task_id} ({task.task_type})")

        try:
            # Send task and wait for result (synchronous)
            result = await sdk.conversation.send_and_wait(
                sender_external_id="submitter",
                recipient_external_id="worker",
                message=task,
                timeout=10.0,
            )

            if isinstance(result, TaskResult):
                logger.info(f"Task Submitter: Task {result.task_id} - Status: {result.status}")
                logger.info(f"Task Submitter: Result: {result.result}")
                logger.info(f"Task Submitter: Processing time: {result.processing_time:.2f}s")
        except Exception as e:
            logger.error(f"Task Submitter: Failed to process {task.task_id}: {e}")

    logger.info("Task Submitter: All tasks processed")


async def main():
    """Run the task processing example."""
    logger.info("Starting asynchronous task processing example")

    # Use 3 type parameters
    async with AgentMessaging[dict, TaskMessage, dict]() as sdk:
        # Register organization
        await sdk.register_organization("processing_co", "Task Processing Company")

        # Register agents
        await sdk.register_agent("submitter", "processing_co", "Task Submitter")
        await sdk.register_agent("worker", "processing_co", "Task Worker")

        # Run the task submitter
        await task_submitter(sdk)

    logger.info("Task processing example completed")


if __name__ == "__main__":
    asyncio.run(main())
