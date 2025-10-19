# Agent Messaging Protocol - Quick Start Guide

## Installation

```bash
# Install the package
pip install agent-messaging

# Or with Poetry
poetry add agent-messaging
```

---

## 5-Minute Quick Start

### 1. Setup Environment

Create a `.env` file:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=agent_messaging
```

### 2. Initialize Database

```bash
# Run database initialization (one-time setup)
python -m agent_messaging.database.init_db
```

### 3. Your First Agent Message

```python
import asyncio
from agent_messaging import AgentMessaging
from pydantic import BaseModel


# Define your message type
class ChatMessage(BaseModel):
    text: str
    priority: str = "normal"


async def main():
    # Initialize SDK
    async with AgentMessaging[ChatMessage]() as sdk:
        # Register organization
        await sdk.register_organization("my_org", "My Organization")
        
        # Register agents
        await sdk.register_agent("alice", "my_org", "Alice")
        await sdk.register_agent("bob", "my_org", "Bob")
        
        # Register handler for Bob
        @sdk.register_handler("bob")
        async def bob_handler(message: ChatMessage, context):
            print(f"Bob received: {message.text}")
        
        # Send one-way message
        await sdk.one_way.send(
            "alice",
            "bob",
            ChatMessage(text="Hello Bob!", priority="high")
        )


if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
Bob received: Hello Bob!
```

---

## Core Concepts

### 1. Message Types

Define your own message structure using Pydantic:

```python
class MyMessage(BaseModel):
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = {}
```

### 2. Four Communication Patterns

#### A. One-Way Message (Fire and Forget)

```python
await sdk.one_way.send(
    sender="alice",
    recipient="bob",
    message=MyMessage(content="Notification")
)
```

**Use when:** Sending notifications, alerts, or commands without expecting a response.

#### B. Synchronous Conversation (Request-Response)

```python
# Alice sends and waits for Bob's response
response = await sdk.sync_conversation.send_and_wait(
    sender="alice",
    recipient="bob",
    message=MyMessage(content="What's your status?"),
    timeout=30.0
)

print(f"Bob replied: {response.content}")
```

```python
# Bob's handler
@sdk.register_handler("bob")
async def bob_handler(message: MyMessage, context):
    if context.requires_reply:
        await sdk.sync_conversation.reply(
            sender="bob",
            recipient=context.sender_external_id,
            message=MyMessage(content="Status: OK")
        )
```

**Use when:** Need immediate response, like API calls or question-answer flows.

#### C. Asynchronous Conversation (Non-Blocking)

```python
# Alice sends without waiting
await sdk.async_conversation.send(
    sender="alice",
    recipient="bob",
    message=MyMessage(content="Check this out")
)

# Alice continues with other work...

# Later, Bob checks messages
messages = await sdk.async_conversation.get_unread_messages("bob")
for msg in messages:
    print(msg.content)
```

**Use when:** Sender doesn't need immediate response, like email or chat apps.

#### D. Multi-Agent Meeting (Turn-Based)

```python
# Host creates meeting
meeting_id = await sdk.meeting.create_meeting(
    host="alice",
    agents=["alice", "bob", "charlie"],
    turn_duration=60.0  # 60 seconds per turn
)

# Agents attend in their handlers
@sdk.register_handler("bob")
async def bob_handler(message, context):
    if context.meeting_id:
        # Attend and wait for turn
        turn_signal = await sdk.meeting.attend_meeting(
            agent="bob",
            meeting_id=context.meeting_id
        )
        # Bob's turn! Speak now.

# Host starts meeting
await sdk.meeting.start_meeting(
    host="alice",
    meeting_id=meeting_id,
    initial_message=MyMessage(content="Welcome everyone!"),
    next_speaker="bob"
)

# Bob speaks (in his handler after getting turn)
await sdk.meeting.speak(
    speaker="bob",
    meeting_id=meeting_id,
    message=MyMessage(content="Thanks for having me!"),
    next_speaker="charlie"
)
```

**Use when:** Multiple agents need to coordinate, like meetings or panels.

---

## Common Use Cases

### Use Case 1: Customer Support Bot

```python
class SupportMessage(BaseModel):
    customer_query: str
    ticket_id: Optional[str] = None


@sdk.register_handler("support_agent")
async def support_handler(message: SupportMessage, context):
    # Process customer query
    response = process_query(message.customer_query)
    
    if context.requires_reply:
        await sdk.sync_conversation.reply(
            "support_agent",
            context.sender_external_id,
            SupportMessage(
                customer_query=response,
                ticket_id=message.ticket_id
            )
        )


# Customer sends query
response = await sdk.sync_conversation.send_and_wait(
    "customer_bot",
    "support_agent",
    SupportMessage(customer_query="How do I reset my password?"),
    timeout=60.0
)
```

### Use Case 2: Multi-Agent Brainstorming

```python
class IdeaMessage(BaseModel):
    speaker: str
    idea: str


# Create brainstorming session
meeting_id = await sdk.meeting.create_meeting(
    host="moderator",
    agents=["moderator", "designer", "engineer", "product_manager"],
    turn_duration=120.0  # 2 minutes per person
)

# Register event handler to track ideas
@sdk.register_event_handler(MeetingEvent.AGENT_SPOKE)
async def on_idea_shared(meeting_id, agent_id, data):
    print(f"{agent_id} shared: {data['message']['idea']}")
```

### Use Case 3: Task Pipeline

```python
class TaskMessage(BaseModel):
    task_id: str
    data: dict
    step: str


# Sequential processing
async def run_pipeline(task_data):
    # Step 1: Preprocessor
    result1 = await sdk.sync_conversation.send_and_wait(
        "orchestrator",
        "preprocessor",
        TaskMessage(task_id="123", data=task_data, step="preprocess")
    )
    
    # Step 2: Analyzer (using result from step 1)
    result2 = await sdk.sync_conversation.send_and_wait(
        "orchestrator",
        "analyzer",
        TaskMessage(task_id="123", data=result1.data, step="analyze")
    )
    
    # Step 3: Output generator
    final = await sdk.sync_conversation.send_and_wait(
        "orchestrator",
        "generator",
        TaskMessage(task_id="123", data=result2.data, step="generate")
    )
    
    return final
```

---

## Best Practices

### 1. Always Use Context Managers

```python
# ✅ GOOD: Ensures cleanup
async with AgentMessaging[MyMessage]() as sdk:
    # Your code here
    pass

# ❌ BAD: Manual cleanup (error-prone)
sdk = AgentMessaging[MyMessage]()
await sdk.initialize()
# ... your code ...
await sdk.close()  # Might be missed on error
```

### 2. Define Message Types with Pydantic

```python
# ✅ GOOD: Type-safe, validated
class UserMessage(BaseModel):
    user_id: UUID
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

# ❌ BAD: Unstructured data
message = {"user_id": "123", "content": "Hello"}  # No validation
```

### 3. Handle Timeouts Gracefully

```python
try:
    response = await sdk.sync_conversation.send_and_wait(
        "alice", "bob", message, timeout=30.0
    )
except ConversationTimeoutError:
    print("Bob didn't respond in time")
    # Handle timeout appropriately
```

### 4. Use Appropriate Conversation Type

```python
# Notification? Use one-way
await sdk.one_way.send(sender, recipient, notification)

# Need immediate response? Use sync
response = await sdk.sync_conversation.send_and_wait(sender, recipient, question)

# Can wait? Use async
await sdk.async_conversation.send(sender, recipient, message)

# Multiple agents? Use meeting
meeting_id = await sdk.meeting.create_meeting(host, agents)
```

### 5. Register Handlers Before Sending

```python
# ✅ GOOD: Handler registered first
@sdk.register_handler("bob")
async def bob_handler(message, context):
    print(f"Received: {message}")

await sdk.one_way.send("alice", "bob", message)

# ❌ BAD: Handler missing - will raise error
await sdk.one_way.send("alice", "bob", message)  # No handler!
```

---

## Configuration

### Environment Variables

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=agent_messaging

# Optional: Connection pooling
MAX_POOL_SIZE=10

# Optional: Timeouts (seconds)
DEFAULT_CONVERSATION_TIMEOUT=300
DEFAULT_MEETING_TIMEOUT=600
DEFAULT_TURN_DURATION=60
```

### Programmatic Configuration

```python
from agent_messaging import AgentMessaging, Config

config = Config(
    postgres_host="db.example.com",
    postgres_port=5432,
    max_pool_size=20,
    default_conversation_timeout=120.0
)

async with AgentMessaging[MyMessage](config=config) as sdk:
    # Your code here
    pass
```

---

## Error Handling

### Common Exceptions

```python
from agent_messaging.exceptions import (
    AgentNotFoundError,
    ConversationTimeoutError,
    MeetingNotFoundError,
    HandlerNotRegisteredError,
    NotMeetingHostError
)

try:
    await sdk.one_way.send("alice", "bob", message)
except AgentNotFoundError:
    print("Agent doesn't exist")
except HandlerNotRegisteredError:
    print("Bob has no message handler")

try:
    response = await sdk.sync_conversation.send_and_wait(
        "alice", "bob", message, timeout=30.0
    )
except ConversationTimeoutError:
    print("Bob didn't respond in 30 seconds")

try:
    await sdk.meeting.end_meeting("bob", meeting_id)
except NotMeetingHostError:
    print("Only host can end meeting")
```

---

## Debugging Tips

### Enable Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agent_messaging")
logger.setLevel(logging.DEBUG)
```

### Check Agent Status

```python
# Verify agent exists
try:
    agent = await sdk.get_agent("alice")
    print(f"Agent found: {agent.name}")
except AgentNotFoundError:
    print("Agent not found")
```

### Check Meeting Status

```python
status = await sdk.meeting.get_meeting_status(meeting_id)
print(f"Status: {status.status}")
print(f"Current speaker: {status.current_speaker_external_id}")
print(f"Participants: {status.participants}")
```

### View Meeting History

```python
history = await sdk.meeting.get_meeting_history(meeting_id)
for msg in history:
    print(f"{msg.sender}: {msg.content}")
```

---

## Next Steps

### Learn More

- **Architecture:** See `docs/plan/01-architecture.md` for system design
- **Database Schema:** See `docs/plan/02-database-schema.md` for database details
- **API Reference:** See `docs/plan/03-api-design.md` for complete API
- **Examples:** Check `examples/` directory for full applications

### Explore Examples

```bash
# Simple notification system
python examples/01_notification_system.py

# Two-agent interview
python examples/02_interview.py

# Multi-agent meeting
python examples/03_brainstorming_meeting.py

# Customer support flow
python examples/04_customer_support.py
```

### Get Help

- **GitHub Issues:** Report bugs or request features
- **Documentation:** Full docs at `docs/`
- **Community:** Join our Discord/Slack

---

## Summary

You now know how to:

✅ Install and configure Agent Messaging Protocol  
✅ Define custom message types  
✅ Use all four communication patterns  
✅ Register handlers for agents  
✅ Handle errors and timeouts  
✅ Debug and monitor agent interactions  

**Ready to build?** Check out the examples directory for complete applications!
