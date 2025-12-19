"""Tests for message notification handler feature.

Tests that notification handlers are invoked when messages arrive
for agents that are not currently locked/waiting.
"""

import asyncio
import uuid
from typing import List

import pytest

from agent_messaging import AgentMessaging
from agent_messaging.handlers import register_message_notification_handler
from agent_messaging.handlers.types import MessageContext


# Track notification calls
notification_calls: List[MessageContext] = []


@pytest.fixture(autouse=True)
def reset_notification_calls():
    """Reset notification calls before each test."""
    notification_calls.clear()
    yield
    notification_calls.clear()


def setup_notification_handler():
    """Register the notification handler for tests."""

    @register_message_notification_handler
    async def handle_notification(message: dict, context: MessageContext) -> None:
        """Notification handler that tracks calls."""
        notification_calls.append(context)


@pytest.mark.asyncio
async def test_notification_handler_invoked_when_receiver_not_locked(
    e2e_sdk: AgentMessaging,
):
    """Test that notification handler is invoked when receiver is not locked."""
    # Register handler after clean_handlers fixture has run
    setup_notification_handler()

    # Create unique IDs for this test
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    alice_id = f"alice_{uuid.uuid4().hex[:8]}"
    bob_id = f"bob_{uuid.uuid4().hex[:8]}"

    # Create two agents
    await e2e_sdk.register_organization(org_id, "Test Organization")
    await e2e_sdk.register_agent(alice_id, org_id, "Alice")
    await e2e_sdk.register_agent(
        bob_id, org_id, "Bob"
    )  # Alice sends a message to Bob using send_no_wait
    # Bob is not locked, so notification should be triggered
    await e2e_sdk.conversation.send_no_wait(
        sender_external_id=alice_id,
        recipient_external_id=bob_id,
        message={"text": "Hello Bob!"},
        metadata={"test": "notification"},
    )

    # Give async handler time to execute
    await asyncio.sleep(0.2)

    # Verify notification was called
    assert len(notification_calls) >= 1
    assert notification_calls[0].sender_id == alice_id
    assert notification_calls[0].receiver_id == bob_id
    assert notification_calls[0].metadata["test"] == "notification"


@pytest.mark.asyncio
async def test_notification_handler_not_invoked_when_receiver_locked(
    e2e_sdk: AgentMessaging,
):
    """Test that notification handler is NOT invoked when receiver is locked/waiting."""
    # Register handler after clean_handlers fixture has run
    setup_notification_handler()

    # Create unique IDs for this test
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    alice_id = f"alice_{uuid.uuid4().hex[:8]}"
    bob_id = f"bob_{uuid.uuid4().hex[:8]}"

    # Create two agents
    await e2e_sdk.register_organization(org_id, "Test Organization")
    await e2e_sdk.register_agent(alice_id, org_id, "Alice")
    await e2e_sdk.register_agent(bob_id, org_id, "Bob")

    # Bob sends a message to Alice using send_and_wait (non-blocking)
    # This will lock Bob as the sender
    async def bob_send_and_wait():
        try:
            await e2e_sdk.conversation.send_and_wait(
                sender_external_id=bob_id,
                recipient_external_id=alice_id,
                message={"text": "Hey Alice!"},
                timeout=1.0,
            )
        except Exception:
            pass  # Timeout expected

    # Start Bob's send_and_wait in background
    bob_task = asyncio.create_task(bob_send_and_wait())
    await asyncio.sleep(0.1)  # Let Bob acquire lock

    # Now Alice sends to Bob while Bob is locked (waiting for Alice's response)
    # Notification should NOT be triggered
    notification_calls.clear()

    await e2e_sdk.conversation.send_no_wait(
        sender_external_id=alice_id,
        recipient_external_id=bob_id,
        message={"text": "Hi Bob!"},
    )

    # Give async handler time to execute
    await asyncio.sleep(0.1)

    # Verify notification was NOT called (Bob is locked)
    assert len(notification_calls) == 0

    # Clean up
    await bob_task


@pytest.mark.asyncio
async def test_notification_handler_with_send_and_wait(
    e2e_sdk: AgentMessaging,
):
    """Test notification handler with send_and_wait when receiver not locked."""
    # Register handler after clean_handlers fixture has run
    setup_notification_handler()

    # Create unique IDs for this test
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    alice_id = f"alice_{uuid.uuid4().hex[:8]}"
    bob_id = f"bob_{uuid.uuid4().hex[:8]}"

    # Create two agents
    await e2e_sdk.register_organization(org_id, "Test Organization")
    await e2e_sdk.register_agent(alice_id, org_id, "Alice")
    await e2e_sdk.register_agent(bob_id, org_id, "Bob")

    # Alice sends using send_and_wait to Bob
    # Bob is not locked, so notification should be triggered
    async def alice_send():
        try:
            await e2e_sdk.conversation.send_and_wait(
                sender_external_id=alice_id,
                recipient_external_id=bob_id,
                message={"text": "Question for Bob"},
                timeout=0.5,
            )
        except Exception:
            pass  # Timeout expected

    # Start Alice's send_and_wait
    alice_task = asyncio.create_task(alice_send())
    await asyncio.sleep(0.1)  # Let message be sent

    # Verify notification was called for Bob
    assert len(notification_calls) >= 1
    assert notification_calls[0].sender_id == alice_id
    assert notification_calls[0].receiver_id == bob_id

    # Clean up
    await alice_task


@pytest.mark.asyncio
async def test_notification_handler_receives_correct_context(
    e2e_sdk: AgentMessaging,
):
    """Test that notification handler receives complete MessageContext."""
    # Register handler after clean_handlers fixture has run
    setup_notification_handler()

    # Create unique IDs for this test
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    alice_id = f"alice_{uuid.uuid4().hex[:8]}"
    bob_id = f"bob_{uuid.uuid4().hex[:8]}"

    # Create two agents
    await e2e_sdk.register_organization(org_id, "Test Organization")
    await e2e_sdk.register_agent(alice_id, org_id, "Alice")
    await e2e_sdk.register_agent(bob_id, org_id, "Bob")

    # Send message with metadata
    await e2e_sdk.conversation.send_no_wait(
        sender_external_id=alice_id,
        recipient_external_id=bob_id,
        message={"text": "Test message", "priority": "high"},
        metadata={"category": "urgent", "tags": ["important"]},
    )

    # Give async handler time to execute
    await asyncio.sleep(0.2)

    # Verify context
    assert len(notification_calls) == 1
    context = notification_calls[0]

    assert context.sender_id == alice_id
    assert context.receiver_id == bob_id
    assert context.message_id is not None
    assert context.session_id is not None
    assert context.metadata["category"] == "urgent"
    assert context.metadata["tags"] == ["important"]
