#!/usr/bin/env python3
"""
Example 1: Simple Notification System

This example demonstrates one-way messaging for notifications.
Agents send notifications to each other without expecting responses.

Handlers are registered globally and process messages for ALL agents.
"""

import asyncio
import logging
from agent_messaging import (
    AgentMessaging,
    register_one_way_handler,
    MessageContext,
)
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Notification(BaseModel):
    """Notification message type."""

    title: str
    message: str
    priority: str = "normal"  # "low", "normal", "high", "urgent"


# Register global handler - processes ALL one-way messages for ALL agents
@register_one_way_handler
async def handle_notification(notification: Notification, context: MessageContext) -> None:
    """Global handler for all notification messages."""
    logger.info(
        f"[{context.receiver_id}] Received from {context.sender_id}: "
        f"{notification.title} - {notification.message}"
    )
    if notification.priority == "urgent":
        logger.warning(f"[{context.receiver_id}] URGENT: Immediate attention required!")


async def main():
    """Run the notification system example."""
    logger.info("Starting notification system example")

    # Use 3 type parameters: T_OneWay, T_Conversation, T_Meeting
    # Here we only use one-way messaging, so other types can be 'dict'
    async with AgentMessaging[Notification, dict, dict]() as sdk:
        # Register organization
        await sdk.register_organization("company", "Tech Company")

        # Register agents
        await sdk.register_agent("system_monitor", "company", "System Monitor")
        await sdk.register_agent("admin", "company", "Administrator")
        await sdk.register_agent("developer", "company", "Developer")

        # Send various notifications
        logger.info("Sending notifications...")

        # System alerts
        await sdk.one_way.send(
            "system_monitor",
            ["admin"],
            Notification(
                title="Server Down", message="Production server is unresponsive", priority="urgent"
            ),
        )

        await sdk.one_way.send(
            "system_monitor",
            ["developer"],
            Notification(
                title="Build Failed",
                message="CI/CD pipeline failed on main branch",
                priority="high",
            ),
        )

        # Regular notifications
        await sdk.one_way.send(
            "system_monitor",
            ["admin"],
            Notification(
                title="Daily Backup", message="Daily backup completed successfully", priority="low"
            ),
        )

        # Wait a moment for handlers to process
        await asyncio.sleep(0.1)

        logger.info("Notification system example completed")


if __name__ == "__main__":
    asyncio.run(main())
