"""Example: Using Message Notification Handlers

This example demonstrates how to use message notification handlers
to be alerted when messages arrive for agents that are not currently locked/waiting.

Use Case:
--------
When Agent A sends a message to Agent B, but Agent B is not actively waiting
for messages (not in a send_and_wait call), Agent B needs to be notified so
they can check for and respond to the new message.

This is useful for:
- Push notifications to mobile/web clients
- Email/SMS alerts for urgent messages
- Triggering background workers to process messages
- Real-time UI updates
"""

import asyncio

from agent_messaging import AgentMessaging
from agent_messaging.handlers import register_message_notification_handler
from agent_messaging.handlers.types import MessageContext


# Register a notification handler
@register_message_notification_handler
async def notify_agent(message: dict, context: MessageContext) -> None:
    """Handle notification when a message arrives for a non-locked agent.

    This handler is called whenever a message is sent to an agent who is
    not currently waiting for responses (not locked).

    Args:
        message: The message content that was sent
        context: Context information including sender, receiver, message_id, etc.
    """
    print(f"\n🔔 NOTIFICATION: New message for {context.receiver_id}")
    print(f"   From: {context.receiver_id}")
    print(f"   Message ID: {context.message_id}")
    print(f"   Session ID: {context.session_id}")
    print(f"   Message content: {message}")
    print(f"   Metadata: {context.metadata}")

    # TODO: Implement your notification logic here:
    # - Send push notification to mobile app
    # - Send email/SMS alert
    # - Update database notification table
    # - Trigger webhook to external system
    # - Update UI via WebSocket
    pass


async def main():
    """Demonstrate message notification feature."""

    async with AgentMessaging[dict, dict, dict]() as sdk:
        # Register organization and agents
        await sdk.register_organization("acme_corp", "ACME Corporation")
        await sdk.register_agent("alice", "acme_corp", "Alice")
        await sdk.register_agent("bob", "acme_corp", "Bob")

        print("=" * 60)
        print("Scenario 1: Send message when receiver is NOT locked")
        print("=" * 60)

        # Alice sends a message to Bob using send_no_wait
        # Bob is not currently waiting (not locked), so notification will be triggered
        await sdk.conversation.send_no_wait(
            sender_external_id="alice",
            recipient_external_id="bob",
            message={"text": "Hey Bob, can you review the report?"},
            metadata={"priority": "high", "category": "work"},
        )

        # Give handler time to execute
        await asyncio.sleep(0.2)

        print("\n✅ Notification handler was called!")
        print("   Bob can now be alerted about the new message\n")

        print("=" * 60)
        print("Scenario 2: Send message when receiver IS locked")
        print("=" * 60)

        # Now Bob starts waiting for messages (becomes locked)
        async def bob_waits_for_response():
            try:
                print("\n📞 Bob is now waiting for messages (locked)...")
                response = await sdk.conversation.send_and_wait(
                    sender_external_id="bob",
                    recipient_external_id="alice",
                    message={"text": "Sure, I'll check it out"},
                    timeout=2.0,
                )
                print(f"   Bob received response: {response}")
            except Exception as e:
                print(f"   Bob's wait timed out (expected): {type(e).__name__}")

        # Start Bob's wait in background
        bob_task = asyncio.create_task(bob_waits_for_response())
        await asyncio.sleep(0.1)  # Let Bob acquire lock

        # Alice sends another message to Bob
        # Bob is now locked (waiting), so NO notification will be triggered
        # (Bob will receive the message directly through send_and_wait)
        await sdk.conversation.send_no_wait(
            sender_external_id="alice",
            recipient_external_id="bob",
            message={"text": "Actually, it's urgent!"},
        )

        await asyncio.sleep(0.2)
        print("\n⚠️  No notification was sent (Bob is locked/waiting)")
        print("   Bob will receive the message through his send_and_wait call\n")

        # Wait for Bob's task to complete
        await bob_task


if __name__ == "__main__":
    asyncio.run(main())
