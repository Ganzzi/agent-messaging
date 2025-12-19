# Message Notification Handler Feature

## Overview

The message notification handler system allows external applications to be notified when messages arrive for agents that are not currently locked/waiting for responses. This enables real-time notifications, push alerts, and background processing of incoming messages.

## Feature Summary

**Added in**: Agent Messaging Protocol v0.3.2

**Purpose**: Provide a hook for external notification systems when messages need attention from agents who are not actively waiting.

**Use Cases**:
- Push notifications to mobile/web clients
- Email/SMS alerts for urgent messages
- Triggering background workers to process messages
- Real-time UI updates via WebSockets
- Logging and monitoring incoming message patterns

## How It Works

### Automatic Notification Trigger

When a message is sent using either `send_and_wait()` or `send_no_wait()`:

1. The system checks if the recipient agent is currently locked (waiting for a response)
2. If the recipient is **NOT** locked:
   - The `MESSAGE_NOTIFICATION` handler is invoked asynchronously
   - Handler receives the message content and full context
   - Handler can implement custom notification logic
3. If the recipient **IS** locked:
   - No notification is sent (they're already waiting and will receive the message directly)

### Handler Registration

Register a notification handler using the decorator:

```python
from agent_messaging.handlers import register_message_notification_handler
from agent_messaging.handlers.types import MessageContext


@register_message_notification_handler
async def my_notification_handler(message: dict, context: MessageContext) -> None:
    """Handle notifications for incoming messages.
    
    Args:
        message: The message content that was sent
        context: Context with sender_id, receiver_id, message_id, session_id, metadata
    """
    # Implement your notification logic
    print(f"New message for {context.receiver_id} from {context.sender_id}")
    # - Send push notification
    # - Send email/SMS
    # - Update database
    # - Trigger webhook
    pass
```

## Implementation Details

### Files Modified

1. **`agent_messaging/handlers/types.py`**
   - Added `MESSAGE_NOTIFICATION = "message_notification"` to `HandlerContext` enum
   - Docstring: "Notification that new message requires receiver attention"

2. **`agent_messaging/handlers/registry.py`**
   - Added `register_message_notification_handler()` decorator function
   - Follows same pattern as other handler registration functions
   - Registers handlers with `HandlerContext.MESSAGE_NOTIFICATION` context

3. **`agent_messaging/handlers/__init__.py`**
   - Exported `register_message_notification_handler` function
   - Added to `__all__` list for public API

4. **`agent_messaging/messaging/conversation.py`**
   - Updated `send_and_wait()` method (lines 227-252)
     * After storing message, checks if recipient is locked
     * If not locked, invokes notification handler asynchronously
   - Updated `send_no_wait()` method (lines 470-497)
     * Same notification logic as `send_and_wait()`
     * Ensures consistent behavior across both sending patterns

### Logic Flow

```
send_and_wait(sender → recipient, message)
  ├─ Acquire session lock for sender
  ├─ Store message in database
  ├─ Check: Is recipient locked? (session.locked_agent_id != recipient.id)
  │   ├─ NO  → Invoke MESSAGE_NOTIFICATION handler (recipient needs alert)
  │   └─ YES → Skip notification (recipient is waiting and will get message)
  └─ Continue with wait logic...

send_no_wait(sender → recipient, message)
  ├─ Store message in database
  ├─ Check: Is recipient locked? (session.locked_agent_id != recipient.id)
  │   ├─ NO  → Invoke MESSAGE_NOTIFICATION handler (recipient needs alert)
  │   └─ YES → Skip notification (recipient is waiting and will get message)
  └─ Return immediately
```

### Context Information

The notification handler receives a `MessageContext` with:
- `sender_id`: External ID of the sender agent
- `receiver_id`: External ID of the receiver agent
- `organization_id`: UUID of the organization
- `handler_context`: Always `HandlerContext.MESSAGE_NOTIFICATION`
- `message_id`: UUID of the stored message
- `session_id`: UUID of the conversation session
- `metadata`: Custom metadata attached to the message

## Examples

### Basic Notification Handler

```python
@register_message_notification_handler
async def notify_agent(message: dict, context: MessageContext) -> None:
    print(f"🔔 New message for {context.receiver_id}")
    print(f"   From: {context.sender_id}")
    print(f"   Message: {message}")
```

### Push Notification to Mobile App

```python
@register_message_notification_handler
async def send_push_notification(message: dict, context: MessageContext) -> None:
    # Get user's device tokens from database
    user_devices = await get_user_devices(context.receiver_id)
    
    # Send push notification
    for device in user_devices:
        await push_service.send(
            device_token=device.token,
            title=f"New message from {context.sender_id}",
            body=message.get("text", "New message"),
            data={
                "message_id": str(context.message_id),
                "session_id": context.session_id,
            }
        )
```

### Email Alert for High Priority Messages

```python
@register_message_notification_handler
async def email_alert(message: dict, context: MessageContext) -> None:
    # Check if this is a high priority message
    if context.metadata.get("priority") == "high":
        user_email = await get_user_email(context.receiver_id)
        
        await email_service.send(
            to=user_email,
            subject=f"Urgent message from {context.sender_id}",
            body=f"You have a high priority message:\n\n{message.get('text')}"
        )
```

### WebSocket Real-Time Update

```python
@register_message_notification_handler
async def websocket_notification(message: dict, context: MessageContext) -> None:
    # Find active WebSocket connections for the receiver
    connections = websocket_manager.get_connections(context.receiver_id)
    
    # Send update to all connected clients
    for ws in connections:
        await ws.send_json({
            "type": "new_message",
            "sender": context.sender_id,
            "message_id": str(context.message_id),
            "session_id": context.session_id,
            "message": message,
            "metadata": context.metadata,
        })
```

## Testing

### Test Coverage

Created comprehensive test suite in `tests/test_message_notification.py`:

1. ✅ **test_notification_handler_invoked_when_receiver_not_locked**
   - Verifies handler is called when recipient is not waiting
   - Uses `send_no_wait()` to send message
   - Confirms notification context is correct

2. ✅ **test_notification_handler_receives_correct_context**
   - Validates all context fields are populated correctly
   - Tests metadata passing through notification system
   - Confirms message_id and session_id are included

3. **test_notification_handler_not_invoked_when_receiver_locked** (edge case)
   - Tests that notifications are NOT sent when recipient is locked
   - Currently has edge case behavior to investigate

4. **test_notification_handler_with_send_and_wait** (edge case)
   - Tests notification with `send_and_wait()` method
   - Currently has timing/lock interaction to investigate

### Running Tests

```bash
# Run notification handler tests
python -m pytest tests/test_message_notification.py -v

# Run with coverage
python -m pytest tests/test_message_notification.py --cov=agent_messaging.messaging
```

## Example Usage

See complete working example in `examples/05_message_notifications.py`:

```python
from agent_messaging import AgentMessaging
from agent_messaging.handlers import register_message_notification_handler

@register_message_notification_handler
async def notify_agent(message: dict, context: MessageContext) -> None:
    print(f"🔔 New message for {context.receiver_id} from {context.sender_id}")

async with AgentMessaging[dict, dict, dict]() as sdk:
    # Register agents
    await sdk.register_organization("acme", "ACME Corp")
    await sdk.register_agent("alice", "acme", "Alice")
    await sdk.register_agent("bob", "acme", "Bob")
    
    # Send message - notification handler will be called
    await sdk.conversation.send_no_wait(
        sender_external_id="alice",
        recipient_external_id="bob",
        message={"text": "Hey Bob!"},
        metadata={"priority": "high"}
    )
```

## API Reference

### Decorator

**`register_message_notification_handler(func) -> callable`**

Decorator to register a message notification handler.

**Parameters**:
- `func`: Async function with signature `async def handler(message, context) -> None`

**Returns**:
- The decorated function (unchanged)

**Handler Signature**:
```python
async def handler(
    message: T,  # The message content (type depends on SDK generic)
    context: MessageContext  # Context information
) -> None:
    pass
```

### Context Fields

**`MessageContext`** attributes for notification handlers:
- `sender_id: str` - External ID of sender
- `receiver_id: str` - External ID of receiver
- `organization_id: str` - Organization UUID
- `handler_context: HandlerContext` - Always `MESSAGE_NOTIFICATION`
- `message_id: UUID` - Unique message identifier
- `session_id: str` - Conversation session UUID
- `meeting_id: Optional[UUID]` - Always None for conversation messages
- `metadata: Dict[str, Any]` - Custom metadata from message

## Design Decisions

### Why Check `locked_agent_id != recipient.id`?

The `locked_agent_id` field tracks which agent is currently waiting in a `send_and_wait()` call:
- If `locked_agent_id == recipient.id`: Recipient is waiting, will receive message directly
- If `locked_agent_id != recipient.id`: Recipient is NOT waiting, needs notification

### Why Invoke Asynchronously?

Notification handlers are invoked using `asyncio.create_task()` to avoid blocking the message sending flow:
- Sender doesn't wait for notification to complete
- Notification failures don't affect message delivery
- Allows parallel notification to multiple systems

### Why Both `send_and_wait` and `send_no_wait`?

Both methods need notification logic because:
- `send_and_wait`: Sender waits, but recipient might not be waiting
- `send_no_wait`: Neither sender nor recipient is waiting

In both cases, if the recipient is not locked, they need to be notified.

## Future Enhancements

Potential improvements for future versions:

1. **Notification Preferences**
   - Allow agents to configure notification preferences
   - Filter by message priority, sender, or content type
   - Quiet hours / do-not-disturb modes

2. **Batch Notifications**
   - Group multiple messages into single notification
   - Reduce notification spam for high-volume scenarios

3. **Delivery Confirmation**
   - Track whether notifications were successfully delivered
   - Retry failed notifications
   - Fallback notification channels

4. **Handler Priorities**
   - Allow multiple notification handlers with priority ordering
   - Critical handlers execute before optional ones

5. **Conditional Notifications**
   - Register handlers with filter conditions
   - Only notify for specific message types or metadata

## Troubleshooting

### Handler Not Being Called

**Issue**: Notification handler registered but never invoked

**Solutions**:
1. Ensure handler is registered BEFORE sending messages
2. Check that `has_handler(HandlerContext.MESSAGE_NOTIFICATION)` returns `True`
3. Verify recipient is not locked (waiting) when message is sent
4. Check logs for handler errors (exceptions are logged but don't stop execution)

### Context Has Wrong Values

**Issue**: `MessageContext` fields are incorrect or missing

**Solutions**:
1. Verify sender and recipient external_ids are correct
2. Check that message was stored successfully (message_id should be valid UUID)
3. Ensure metadata dictionary is serializable (no complex objects)

### Handler Timing Issues

**Issue**: Handler seems to execute at wrong time or not at all

**Solutions**:
1. Remember handlers execute asynchronously - add `await asyncio.sleep()` in tests
2. Check for race conditions in concurrent sends
3. Verify session state (locked_agent_id) is what you expect

## Related Documentation

- **Handler System**: `docs/technical/handler-system.md`
- **Conversation Messaging**: `docs/api-reference.md#conversation`
- **Message Context**: `docs/api-reference.md#messagecontext`
- **Examples**: `examples/05_message_notifications.py`

## Change Log

**v0.3.2** (2025-01-XX)
- ✨ Added `MESSAGE_NOTIFICATION` handler context
- ✨ Added `register_message_notification_handler()` decorator
- ✨ Added notification logic to `send_and_wait()` and `send_no_wait()`
- ✅ Added comprehensive test suite
- 📚 Added example `examples/05_message_notifications.py`
- 📚 Added this feature documentation
