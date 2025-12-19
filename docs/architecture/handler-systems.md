# Handler Systems Architecture

**Version**: 0.4.0  
**Last Updated**: December 19, 2025  
**Status**: Stable

## Table of Contents

1. [Overview](#overview)
2. [Two Handler Patterns](#two-handler-patterns)
3. [Global Message Handlers](#global-message-handlers)
4. [Instance Event Handlers](#instance-event-handlers)
5. [Type Safety Guide](#type-safety-guide)
6. [Decision Tree](#decision-tree)
7. [Best Practices](#best-practices)
8. [FAQ](#faq)

## Overview

The Agent Messaging Protocol uses **two distinct handler systems** for different purposes:

1. **Global Message Handlers** - Process message content (business logic)
2. **Instance Event Handlers** - React to meeting lifecycle events (integration logic)

This architecture may seem complex at first, but each system serves a specific purpose that makes it the right tool for its job. This document explains when and how to use each system.

## Two Handler Patterns

### Why Two Systems?

| Aspect | Global Message Handlers | Instance Event Handlers |
|--------|------------------------|-------------------------|
| **Purpose** | Process message content | React to state changes |
| **Scope** | Application-wide | Per-SDK-instance |
| **Registration** | Decorator-based | Method-based |
| **Storage** | Global `_handlers` dict | Instance `self._handlers` dict |
| **Lifecycle** | Live until app shutdown | Live with SDK instance |
| **Use Case** | Business logic | Integration/monitoring |

### The Core Distinction

**Message Handlers = "What do I do with this message?"**
- Process the content of messages sent between agents
- Implement business logic (process queries, send notifications, etc.)
- Same logic applies to all SDK instances in your application

**Event Handlers = "What happened in this meeting?"**
- React to lifecycle events (meeting started, turn changed, etc.)
- Implement integration logic (logging, monitoring, webhooks)
- Different logic per SDK instance (dev vs prod, different apps)

## Global Message Handlers

### Overview

Global message handlers process the **content** of messages sent between agents. They implement your application's business logic for handling different message types.

### Available Contexts

```python
from agent_messaging.handlers import HandlerContext

HandlerContext.ONE_WAY          # Fire-and-forget messages
HandlerContext.CONVERSATION     # Request-response messages
HandlerContext.MESSAGE_NOTIFICATION  # New message notifications
```

### Registration

```python
from agent_messaging.handlers import (
    register_one_way_handler,
    register_conversation_handler,
    register_message_notification_handler,
    MessageContext,
)

@register_one_way_handler
async def handle_notification(message: dict, context: MessageContext) -> None:
    """Process one-way notifications."""
    print(f"Notification from {context.sender_id}: {message}")

@register_conversation_handler
async def handle_query(message: dict, context: MessageContext) -> dict:
    """Process conversation queries and return responses."""
    return {"answer": f"Processed: {message.get('question')}"}

@register_message_notification_handler
async def notify_agent(message: dict, context: MessageContext) -> None:
    """Notify agent of new message when they're not actively waiting."""
    send_push_notification(context.receiver_id, "New message!")
```

### When Handlers Are Invoked

**ONE_WAY Handler:**
```python
# Invoked by OneWayMessenger.send()
await sdk.one_way.send("alice", ["bob"], {"text": "Hello"})
# → Calls handler for each recipient
```

**CONVERSATION Handler:**
```python
# Invoked by Conversation.send_and_wait() and send_no_wait()
response = await sdk.conversation.send_and_wait("alice", "bob", {"question": "Hi"})
# → Calls handler for recipient "bob"
```

**MESSAGE_NOTIFICATION Handler:**
```python
# Invoked when message arrives for non-locked agent
await sdk.conversation.send_no_wait("alice", "bob", {"text": "Urgent!"})
# → If Bob is not currently locked/waiting, notification handler is called
```

### Global Handler Characteristics

✅ **Registered once, applies everywhere**
```python
# Register at app startup
@register_one_way_handler
async def handle(message, context):
    pass

# Works for all SDK instances
async with AgentMessaging() as sdk1:
    await sdk1.one_way.send(...)  # Uses handler

async with AgentMessaging() as sdk2:
    await sdk2.one_way.send(...)  # Uses same handler
```

✅ **Only one handler per context**
```python
# Last registration wins
@register_one_way_handler
async def handler1(message, context):
    pass

@register_one_way_handler  # This replaces handler1
async def handler2(message, context):
    pass
```

✅ **Thread-safe and concurrent-safe**
```python
# Multiple SDK instances can invoke same handler concurrently
# Handler must be thread-safe if used in multi-threaded app
```

### Message Context

Handlers receive a `MessageContext` with routing information:

```python
@dataclass
class MessageContext:
    sender_id: str              # External ID of sender
    receiver_id: str            # External ID of receiver
    organization_id: str        # Organization UUID
    handler_context: HandlerContext  # Which handler type
    message_id: Optional[int]   # Database message ID
    session_id: Optional[str]   # Conversation session ID
    meeting_id: Optional[int]   # Meeting ID (if applicable)
    metadata: dict[str, Any]    # Custom metadata
```

### Use Cases

**ONE_WAY Handlers:**
- Send email/SMS notifications
- Update dashboards
- Log events
- Trigger webhooks
- Process fire-and-forget commands

**CONVERSATION Handlers:**
- Answer support queries
- Process API requests
- Handle chatbot interactions
- Execute commands and return results

**MESSAGE_NOTIFICATION Handlers:**
- Send push notifications to mobile apps
- Update UI with "new message" indicators
- Trigger email alerts for urgent messages
- Log message arrival for monitoring

## Instance Event Handlers

### Overview

Instance event handlers react to **meeting lifecycle events**. Each SDK instance can have its own event handlers, allowing different behaviors for different contexts (dev/prod, different apps, etc.).

### Available Events

```python
from agent_messaging.models import MeetingEventType

MeetingEventType.MEETING_STARTED       # Meeting begins
MeetingEventType.MEETING_ENDED         # Meeting ends
MeetingEventType.TURN_CHANGED          # Speaking turn changes
MeetingEventType.PARTICIPANT_JOINED    # Agent joins meeting
MeetingEventType.PARTICIPANT_LEFT      # Agent leaves meeting
MeetingEventType.TIMEOUT_OCCURRED      # Speaker timeout
```

### Registration

```python
from agent_messaging.models import MeetingEventType
from agent_messaging.handlers import MeetingEvent

async with AgentMessaging() as sdk:
    # Register event handler on this SDK instance
    async def on_meeting_started(event: MeetingEvent):
        """Called when a meeting starts."""
        print(f"Meeting {event.meeting_id} started!")
        print(f"Host: {event.data.host_id}")
        print(f"Participants: {event.data.participant_ids}")
    
    sdk._event_handler.register_handler(
        MeetingEventType.MEETING_STARTED,
        on_meeting_started
    )
    
    # Use SDK with event handlers
    meeting_id = await sdk.meeting.create_meeting("alice", ["bob", "charlie"])
    await sdk.meeting.start_meeting("alice", meeting_id)
    # → Triggers on_meeting_started event
```

### Event Data Types

Each event type has a specific data class:

```python
from agent_messaging.models import (
    MeetingStartedEventData,
    MeetingEndedEventData,
    TurnChangedEventData,
    ParticipantJoinedEventData,
    ParticipantLeftEventData,
    TimeoutOccurredEventData,
)

async def on_turn_changed(event: MeetingEvent):
    # Type-safe access to event data
    data: TurnChangedEventData = event.data
    print(f"Turn changed from {data.previous_speaker_id} to {data.current_speaker_id}")
```

### Instance Handler Characteristics

✅ **Per-SDK-instance isolation**
```python
# Each SDK instance has its own event handlers
async with AgentMessaging() as sdk1:
    sdk1._event_handler.register_handler(event_type, handler1)
    # sdk1 uses handler1

async with AgentMessaging() as sdk2:
    sdk2._event_handler.register_handler(event_type, handler2)
    # sdk2 uses handler2 (different from sdk1)
```

✅ **Multiple handlers per event**
```python
# You can register multiple handlers for the same event
sdk._event_handler.register_handler(event_type, handler1)
sdk._event_handler.register_handler(event_type, handler2)
# Both handlers will be called
```

✅ **Unregister handlers**
```python
# Remove specific handler
sdk._event_handler.unregister_handler(event_type, handler)
```

### Use Cases

**Meeting Lifecycle Events:**
- Log meeting start/end times to database
- Send notifications when meetings begin
- Update UI when turn changes
- Track participant join/leave for analytics
- Alert on timeouts for monitoring

**Integration Examples:**
```python
# Log to database
async def log_meeting_start(event: MeetingEvent):
    await db.insert("meeting_logs", {
        "meeting_id": event.meeting_id,
        "event": "started",
        "timestamp": event.timestamp
    })

# Send webhook
async def notify_external_system(event: MeetingEvent):
    await webhook_client.post("https://api.example.com/meeting-events", {
        "meeting_id": str(event.meeting_id),
        "type": event.event_type.value
    })

# Update dashboard
async def update_dashboard(event: MeetingEvent):
    await websocket_manager.broadcast({
        "type": "meeting_update",
        "meeting_id": str(event.meeting_id),
        "event": event.event_type.value
    })
```

## Type Safety Guide

### The Type Safety Challenge

Python's type system has a limitation: **generic types are erased at runtime**.

```python
# At compile time (mypy sees this)
AgentMessaging[Notification, Query, MeetingMsg]

# At runtime (Python sees this)
AgentMessaging  # Generic parameters are gone!
```

This means handlers can't automatically know what message type to expect at runtime.

### Solution: Use Type Hints

While we can't enforce types at runtime, we **can** use type hints for excellent IDE support:

#### ✅ DO THIS:

```python
from typing import TypedDict

class Notification(TypedDict):
    type: str
    text: str
    priority: str

@register_one_way_handler
async def handle_notification(
    message: Notification,  # ← Type hint for IDE
    context: MessageContext
) -> None:
    # IDE now knows message.text, message.priority exist!
    print(f"[{message['priority']}] {message['text']}")
```

#### ❌ DON'T DO THIS:

```python
@register_one_way_handler
async def handle_notification(message, context):  # No type hints
    # IDE doesn't know what 'message' contains
    # No autocomplete, no type checking
    print(message.text)  # Might fail at runtime!
```

### Type Hints with Pydantic

If you use Pydantic models, type hints work even better:

```python
from pydantic import BaseModel

class Query(BaseModel):
    question: str
    context: str

@register_conversation_handler
async def handle_query(
    message: Query,  # ← Pydantic model
    context: MessageContext
) -> Query:
    # Full IDE autocomplete!
    answer = process(message.question)
    return Query(question=message.question, context=answer)
```

### Static Type Checking

Use mypy or pyright for static type checking:

```bash
# Install mypy
pip install mypy

# Check your code
mypy your_app.py
```

Example with type checking:

```python
# your_app.py
from agent_messaging import AgentMessaging
from agent_messaging.handlers import register_one_way_handler, MessageContext

class Notification(TypedDict):
    text: str

@register_one_way_handler
async def handle(message: Notification, context: MessageContext) -> None:
    print(message['text'])  # ✓ OK
    print(message['invalid'])  # ✗ mypy error: Key 'invalid' not in Notification

async def main():
    async with AgentMessaging[Notification, dict, dict]() as sdk:
        await sdk.one_way.send("alice", ["bob"], {"text": "Hi"})  # ✓ OK
        await sdk.one_way.send("alice", ["bob"], {"invalid": "data"})  # ✗ mypy error

# Run: mypy your_app.py
```

### Runtime Type Validation (Optional)

If you want runtime type checking, use Pydantic:

```python
from pydantic import BaseModel, ValidationError

class Notification(BaseModel):
    text: str
    priority: str = "normal"

@register_one_way_handler
async def handle(message: dict, context: MessageContext) -> None:
    try:
        # Validate at runtime
        notif = Notification(**message)
        print(f"Valid: {notif.text}")
    except ValidationError as e:
        print(f"Invalid message: {e}")
```

## Decision Tree

### Which Handler System Should I Use?

```
START: I need to handle something
│
├─ Is it about MESSAGE CONTENT?
│  (Processing queries, notifications, commands)
│  │
│  └─ YES → Use Global Message Handlers
│     ├─ Fire-and-forget? → register_one_way_handler
│     ├─ Need response? → register_conversation_handler
│     └─ Notify when message arrives? → register_message_notification_handler
│
└─ Is it about MEETING LIFECYCLE?
   (Meeting started, turn changed, participant joined)
   │
   └─ YES → Use Instance Event Handlers
      └─ sdk._event_handler.register_handler(event_type, handler)
```

### Examples

**"I want to send an email when a notification arrives"**
→ Global Message Handler (ONE_WAY)

**"I want to answer support questions from agents"**
→ Global Message Handler (CONVERSATION)

**"I want to log when meetings start"**
→ Instance Event Handler (MEETING_STARTED)

**"I want to update UI when speaking turn changes"**
→ Instance Event Handler (TURN_CHANGED)

**"I want to alert agents when messages arrive while they're busy"**
→ Global Message Handler (MESSAGE_NOTIFICATION)

**"I want to track how long agents speak in meetings"**
→ Instance Event Handler (TURN_CHANGED + TIMEOUT_OCCURRED)

## Best Practices

### Global Message Handlers

**1. Use Type Hints**
```python
@register_one_way_handler
async def handle(message: Notification, context: MessageContext) -> None:
    pass  # Good: type hints for IDE support
```

**2. Keep Handlers Stateless**
```python
# ✗ BAD: State in handler
request_count = 0

@register_one_way_handler
async def handle(message, context):
    global request_count
    request_count += 1  # Race conditions!

# ✓ GOOD: Use external state management
@register_one_way_handler
async def handle(message, context):
    await redis.incr("request_count")  # Thread-safe
```

**3. Handle Exceptions Gracefully**
```python
@register_one_way_handler
async def handle(message, context):
    try:
        await process_message(message)
    except Exception as e:
        logger.error(f"Handler error: {e}", extra={"context": context})
        # Don't let exceptions kill the handler system
```

**4. Register at App Startup**
```python
# main.py
from agent_messaging.handlers import register_one_way_handler

# Register handlers BEFORE creating SDK
@register_one_way_handler
async def handle(message, context):
    pass

# Then use SDK
async def main():
    async with AgentMessaging() as sdk:
        await sdk.one_way.send(...)
```

### Instance Event Handlers

**1. Register Early**
```python
async with AgentMessaging() as sdk:
    # Register event handlers IMMEDIATELY after SDK creation
    sdk._event_handler.register_handler(event_type, handler)
    
    # Then use SDK
    await sdk.meeting.create_meeting(...)
```

**2. Clean Up Resources**
```python
async def on_meeting_ended(event: MeetingEvent):
    """Clean up when meeting ends."""
    await close_websockets(event.meeting_id)
    await cleanup_resources(event.meeting_id)
```

**3. Don't Block Event Loop**
```python
# ✗ BAD: Blocking operation
async def on_turn_changed(event):
    time.sleep(5)  # Blocks event loop!

# ✓ GOOD: Async operations
async def on_turn_changed(event):
    await asyncio.sleep(5)  # Non-blocking
```

**4. Use Type-Safe Event Data**
```python
async def on_meeting_started(event: MeetingEvent):
    # Type-cast for IDE support
    data: MeetingStartedEventData = event.data
    print(f"Participants: {data.participant_ids}")
```

## FAQ

### Q: Why not use one unified handler system?

**A**: Because they serve fundamentally different purposes:
- Message handlers process **content** (business logic)
- Event handlers react to **state changes** (integration logic)

Mixing them would create confusion and limit flexibility.

### Q: Can I use both systems together?

**A**: Yes! Most applications will use both:

```python
# Global message handler (business logic)
@register_conversation_handler
async def handle_query(message, context):
    return {"answer": "..."}

# Instance event handler (monitoring)
async with AgentMessaging() as sdk:
    sdk._event_handler.register_handler(
        MeetingEventType.MEETING_STARTED,
        lambda event: log_meeting_start(event)
    )
```

### Q: Why are meeting messages not using message handlers?

**A**: Meeting messages are tightly coupled to turn management and state updates. Processing them through handlers would complicate synchronization. Meeting **events** provide the extensibility hook instead.

### Q: Can I have different handlers for different organizations/agents?

**A**: Global message handlers apply to ALL agents. If you need per-agent logic, implement routing inside your handler:

```python
@register_one_way_handler
async def handle(message, context):
    if context.organization_id == "org_premium":
        await premium_processing(message)
    else:
        await standard_processing(message)
```

### Q: How do I test handlers?

**A**: Test handlers as regular async functions:

```python
import pytest
from agent_messaging.handlers import MessageContext, HandlerContext

@pytest.mark.asyncio
async def test_handler():
    # Create test context
    context = MessageContext(
        sender_id="alice",
        receiver_id="bob",
        organization_id="test_org",
        handler_context=HandlerContext.ONE_WAY,
        metadata={}
    )
    
    # Call handler directly
    result = await my_handler({"text": "test"}, context)
    
    assert result is not None
```

### Q: What happens if a handler raises an exception?

**A**: 
- **Global handlers**: Exception is logged, but doesn't stop message delivery
- **Event handlers**: Exception is logged, but doesn't stop other handlers
- Use try/except in handlers for graceful error handling

### Q: Can I clear/unregister global handlers?

**A**: Yes:

```python
from agent_messaging.handlers import clear_handlers

# Clear all handlers
clear_handlers()

# Handlers are gone - new registrations needed
```

### Q: How do I debug handler invocations?

**A**: Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Will log handler registrations and invocations
```

### Q: Are handlers invoked synchronously or asynchronously?

**A**:
- **ONE_WAY**: Always asynchronous (`asyncio.create_task`)
- **CONVERSATION**: Can be both (tries sync first with timeout, then async)
- **MESSAGE_NOTIFICATION**: Always asynchronous
- **Event handlers**: Concurrent (all handlers run in parallel)

## Related Documentation

- [API Reference](../api-reference.md) - Handler API details
- [Quick Start](../quick-start.md) - Getting started with handlers
- [Message Notifications](../features/message-notifications.md) - Notification handler guide
- [Meeting Guide](../features/meetings.md) - Meeting event handler examples

## Changelog

**v0.4.0** (December 19, 2025)
- Removed unused `HandlerContext.MEETING` and `HandlerContext.SYSTEM`
- Removed `register_meeting_handler()` and `register_system_handler()`
- Clarified two-handler-system architecture
- Added comprehensive type safety guide
- Added decision tree and best practices

**v0.3.2** (Previous)
- Added `MESSAGE_NOTIFICATION` handler context
- Initial documentation of handler system
