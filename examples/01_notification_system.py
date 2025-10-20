#!/usr/bin/env python3
"""
Example 1: Simple Notification System

This example demonstrates one-way messaging for notifications.
Agents send notifications to each other without expecting responses.
"""

import asyncio
import logging
from agent_messaging import AgentMessaging
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Notification(BaseModel):
    """Notification message type."""

    title: str
    message: str
    priority: str = "normal"  # "low", "normal", "high", "urgent"


async def main():
    """Run the notification system example."""
    logger.info("Starting notification system example")

    async with AgentMessaging[Notification]() as sdk:
        # Register organization
        await sdk.register_organization("company", "Tech Company")

        # Register agents
        await sdk.register_agent("system_monitor", "company", "System Monitor")
        await sdk.register_agent("admin", "company", "Administrator")
        await sdk.register_agent("developer", "company", "Developer")

        # Register global handler for all agents
        @sdk.register_handler()
        async def global_handler(notification: Notification, context):
            # Route messages based on recipient
            if context.recipient_external_id == "admin":
                logger.info(f"ADMIN ALERT: {notification.title} - {notification.message}")
                if notification.priority == "urgent":
                    logger.warning("URGENT: Immediate attention required!")
            elif context.recipient_external_id == "developer":
                logger.info(f"DEV NOTIFICATION: {notification.title} - {notification.message}")
            else:
                logger.info(
                    f"UNKNOWN RECIPIENT {context.recipient_external_id}: {notification.title} - {notification.message}"
                )

        # Send various notifications
        logger.info("Sending notifications...")

        # System alerts
        await sdk.one_way.send(
            "system_monitor",
            "admin",
            Notification(
                title="Server Down", message="Production server is unresponsive", priority="urgent"
            ),
        )

        await sdk.one_way.send(
            "system_monitor",
            "developer",
            Notification(
                title="Build Failed",
                message="CI/CD pipeline failed on main branch",
                priority="high",
            ),
        )

        # Regular notifications
        await sdk.one_way.send(
            "system_monitor",
            "admin",
            Notification(
                title="Daily Backup", message="Daily backup completed successfully", priority="low"
            ),
        )

        # Wait a moment for handlers to process
        await asyncio.sleep(0.1)

        logger.info("Notification system example completed")


if __name__ == "__main__":
    asyncio.run(main())
