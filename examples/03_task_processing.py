#!/usr/bin/env python3
"""
Example 3: Asynchronous Conversation - Task Processing

This example demonstrates asynchronous conversations where agents
send tasks and check for results later, without blocking.
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
from pydantic import BaseModel
from datetime import datetime

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


async def task_submitter(sdk: AgentMessaging):
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

    # Submit all tasks asynchronously
    submitted_tasks = []
    for task in tasks:
        logger.info(f"Task Submitter: Submitting {task.task_id} ({task.task_type})")

        # Send task asynchronously (non-blocking)
        await sdk.conversation.send_no_wait(
            sender_external_id="submitter", recipient_external_id="worker", message=task
        )

        submitted_tasks.append(task.task_id)
        logger.info(f"Task Submitter: {task.task_id} submitted")

    # Wait a bit for processing
    logger.info("Task Submitter: Waiting for processing...")
    await asyncio.sleep(3)

    # Check for results
    logger.info("Task Submitter: Checking for results...")
    results = await sdk.conversation.get_unread_messages("submitter")

    logger.info(f"Task Submitter: Received {len(results)} result messages")

    for result in results:
        logger.info(f"Task Submitter: Task {result.task_id} - Status: {result.status}")
        if result.status == "completed":
            logger.info(f"Task Submitter: Result: {result.result}")
            logger.info(f"Task Submitter: Processing time: {result.processing_time:.2f}s")
        else:
            logger.error(f"Task Submitter: Error: {result.error_message}")

    logger.info("Task Submitter: All tasks processed")


async def task_worker(sdk: AgentMessaging):
    """Agent that processes tasks asynchronously."""
    logger.info("Task Worker: Ready to process tasks")


async def main():
    """Run the task processing example."""
    logger.info("Starting asynchronous task processing example")

    async with AgentMessaging() as sdk:  # Generic type for mixed messages
        # Register organization
        await sdk.register_organization("processing_co", "Task Processing Company")

        # Register agents
        await sdk.register_agent("submitter", "processing_co", "Task Submitter")
        await sdk.register_agent("worker", "processing_co", "Task Worker")

        # Register conversation handler for worker to process tasks
        @sdk.register_conversation_handler("worker")
        async def worker_handler(message, context):
            if isinstance(message, TaskRequest):
                logger.info(f"Task Worker: Received task {message.task_id} ({message.task_type})")

                # Simulate processing time based on task type
                if message.task_type == "data_analysis":
                    processing_time = 1.0
                    result_data = {"sum": sum(message.data["numbers"])}
                elif message.task_type == "text_summary":
                    processing_time = 2.0
                    result_data = {"summary": f"Summary of {len(message.data['text'])} characters"}
                elif message.task_type == "image_processing":
                    processing_time = 1.5
                    result_data = {"processed_url": "https://example.com/processed_image.jpg"}
                else:
                    processing_time = 0.5
                    result_data = {"error": "Unknown task type"}

                # Simulate processing
                await asyncio.sleep(processing_time)

                # Create result
                result = TaskResult(
                    task_id=message.task_id,
                    status="completed",
                    result=result_data,
                    processing_time=processing_time,
                )

                # Send result back asynchronously
                await sdk.conversation.send_no_wait(
                    sender_external_id="worker",
                    recipient_external_id="submitter",
                    message=result,
                )

                logger.info(
                    f"Task Worker: Completed task {message.task_id} in {processing_time:.2f}s"
                )

        # Start both agents concurrently
        await asyncio.gather(task_submitter(sdk), task_worker(sdk))

    logger.info("Task processing example completed")


if __name__ == "__main__":
    asyncio.run(main())
