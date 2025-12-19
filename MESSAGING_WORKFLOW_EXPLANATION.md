# Agent Messaging Protocol - Messaging Workflow Explanation

## Overview

The Agent Messaging Protocol supports **three primary messaging patterns**, each with distinct behavior:

1. **One-Way Messages** - Fire-and-forget notifications (1-to-N)
2. **Synchronous Conversations** - Request-response with blocking waits (1-to-1)
3. **Asynchronous Conversations** - Non-blocking messaging with queues (1-to-1)

---

## Detailed Workflow: Sending a Message

### Pattern 1: One-Way Messages (`send()`)

**Use Case:** Notifications, broadcasts, alerts (no response expected)

```python
message_ids = await sdk.one_way.send(
    sender_external_id="alice",
    recipient_external_ids=["bob", "charlie"],  # Multiple recipients
    message={"text": "Hello everyone!"}
)
```

**Execution Flow:**

```
1. VALIDATION
   ├─ Validate sender exists
   ├─ Validate all recipients exist
   └─ Check handler is registered (required)

2. MESSAGE STORAGE (per recipient)
   ├─ Serialize message to JSONB
   ├─ Store in messages table with:
   │  ├─ sender_id = alice.id
   │  ├─ recipient_id = bob.id/charlie.id
   │  ├─ message_type = USER_DEFINED
   │  ├─ no session_id (one-way pattern)
   │  └─ metadata (optional)
   └─ Return message_id

3. HANDLER INVOCATION (concurrent, fire-and-forget)
   ├─ Create MessageContext for each recipient
   ├─ Call asyncio.create_task() for each recipient's handler
   │  └─ Handler runs in background without blocking sender
   └─ Return immediately to sender

4. SENDER RETURNS
   └─ Returns list of message IDs → [id1, id2]
```

**Key Characteristics:**
- ✅ **Non-blocking** - Sender continues immediately
- ✅ **No session** - Messages are independent
- ✅ **Concurrent handler invocation** - All handlers run simultaneously
- ✅ **Fire-and-forget** - No waiting for responses
- ✅ **One-to-many** - Can send to multiple recipients

**Important:** Handler is invoked **asynchronously** in background via `asyncio.create_task()`

---

### Pattern 2: Synchronous Conversations (`send_and_wait()`)

**Use Case:** Request-response patterns, support chatbots, queries (response required)

```python
response = await sdk.conversation.send_and_wait(
    sender_external_id="alice",
    recipient_external_id="bob",
    message={"question": "What's the status?"},
    timeout=30.0,
    metadata={"request_id": "req-123"}
)
```

**Execution Flow:**

```
1. VALIDATION & SETUP
   ├─ Validate agents exist (sender & recipient)
   ├─ Check conversation handler is registered (required)
   └─ Validate timeout (0 < timeout ≤ 300 seconds)

2. SESSION MANAGEMENT
   ├─ Get active session between sender & recipient
   │  └─ If none exists → Create new session
   └─ Verify session status = ACTIVE
   
3. LOCK ACQUISITION (CRITICAL)
   ├─ Create SessionLock instance
   ├─ Acquire PostgreSQL advisory lock on same connection
   │  └─ This prevents concurrent accesses to this session
   ├─ Mark sender as locked_agent_id in session
   └─ Create waiting event (asyncio.Event) for sender

4. MESSAGE STORAGE
   ├─ Serialize message to JSONB
   ├─ Store request message:
   │  ├─ sender_id = alice.id
   │  ├─ recipient_id = bob.id
   │  ├─ session_id = <session_id>
   │  ├─ message_type = USER_DEFINED
   │  └─ metadata = {...}
   └─ Create MessageContext with all details

5. HANDLER INVOCATION (TRY IMMEDIATE RESPONSE)
   ├─ Try to invoke handler with 100ms timeout
   ├─ If handler returns response immediately:
   │  ├─ Serialize response
   │  ├─ Store response message in database
   │  ├─ Mark as read
   │  ├─ Release lock
   │  └─ Return response (DONE - quick path)
   │
   ├─ If handler times out (doesn't respond in 100ms):
   │  ├─ Invoke handler asynchronously (asyncio.create_task)
   │  └─ Fall through to wait phase
   │
   └─ If handler error:
       ├─ Log error
       ├─ Still invoke async (retry chance)
       └─ Fall through to wait phase

6. CHECK FOR IMMEDIATE RESPONSE
   ├─ Query database for response messages from recipient
   ├─ If found:
   │  ├─ Mark as read
   │  ├─ Release lock
   │  └─ Return response (DONE - handler was fast)
   └─ If not found → Continue to waiting

7. WAIT FOR RESPONSE (with timeout)
   ├─ Block on asyncio.Event until:
   │  ├─ Response arrives (handler calls set()), OR
   │  ├─ Timeout expires
   │  └─ Recipient sends response message
   │
   ├─ When event signals:
   │  ├─ Check _waiting_responses dict (backward compat)
   │  ├─ If found → Return it (DONE)
   │  ├─ Otherwise → Query database for response messages
   │  ├─ If found → Mark read & return (DONE)
   │  └─ If not found → Raise RuntimeError
   │
   └─ On timeout:
       ├─ Clean up waiting structures
       ├─ Release lock
       └─ Raise TimeoutError

8. FINALLY BLOCK (Cleanup)
   ├─ Release PostgreSQL advisory lock (same connection)
   ├─ Clear locked_agent_id from session
   ├─ Clean up waiting event
   └─ Ensure no lock leaks
```

**Key Characteristics:**
- 🔒 **Session-based** - One session per agent pair
- 🔒 **Locking** - PostgreSQL advisory locks prevent concurrent access
- ⏱️ **Blocking** - Sender waits for response (with timeout)
- ✅ **Dual response mechanism**:
  1. Immediate handler response (100ms fast-path)
  2. Wait for response message (normal path)
- 🎯 **One-to-one** - Only between two agents
- ⚠️ **Serialized** - Only one sender can wait at a time per session

**CRITICAL DETAIL:** The lock is acquired and released on the **SAME database connection** to prevent PostgreSQL advisory lock leaks.

---

### Pattern 3: Asynchronous Conversations (`send_no_wait()`)

**Use Case:** Non-blocking messaging, queue-based systems, background tasks

```python
await sdk.conversation.send_no_wait(
    sender_external_id="alice",
    recipient_external_id="bob",
    message={"notification": "Task completed"},
    metadata={"task_id": "task-456"}
)
# Sender continues immediately - no waiting
```

**Execution Flow:**

```
1. VALIDATION
   ├─ Validate agents exist
   └─ Validate IDs are non-empty

2. SESSION MANAGEMENT
   ├─ Get active session between sender & recipient
   │  └─ If none exists → Create new session
   └─ No session locking (this is non-blocking)

3. MESSAGE STORAGE
   ├─ Serialize message to JSONB
   ├─ Store message:
   │  ├─ sender_id = alice.id
   │  ├─ recipient_id = bob.id
   │  ├─ session_id = <session_id>
   │  ├─ message_type = USER_DEFINED
   │  └─ metadata = {...}
   └─ Create MessageContext

4. HANDLER INVOCATION (async, fire-and-forget)
   └─ asyncio.create_task(invoke_handler_async(...))
      └─ Handler runs in background

5. WAKE WAITING AGENT (if any)
   ├─ Check if recipient is waiting in get_or_wait_for_response()
   ├─ If waiting event exists for this session:
   │  └─ Set the event to wake receiver
   └─ Receiver's get_or_wait_for_response() will return

6. RETURN IMMEDIATELY
   └─ Return None immediately to sender
```

**Key Characteristics:**
- ⚡ **Non-blocking** - Returns immediately (returns `None`)
- 📨 **Queue-based** - Messages accumulate if receiver not ready
- 🔓 **No locking** - Multiple senders can queue messages
- 📬 **Wake receiver** - If receiver is waiting, signal the event
- 🎯 **One-to-one** - Between two specific agents

---

## Session Behavior: Existing vs New

### What happens with existing sessions?

When you send a message and a session already exists between the two agents:

#### For `send_no_wait()`:
```python
# Session already exists from previous conversation
# Still works - reuses existing session
await sdk.conversation.send_no_wait("alice", "bob", message)

✓ Query finds active session
✓ Message stored in existing session
✓ Receiver can retrieve via get_unread_messages() or get_or_wait_for_response()
```

**Implications:**
- Messages accumulate in the same session
- Session persists until explicitly ended or times out
- Conversation history is maintained in one session

#### For `send_and_wait()`:
```python
# Session already exists
response = await sdk.conversation.send_and_wait("alice", "bob", message)

# IMPORTANT: This might fail if session is already locked!
```

**⚠️ Critical Issue - Lock Contention:**

```
Scenario 1: Sequential requests (OK)
    alice.send_and_wait("bob", msg1)  # Acquires lock
    # → bob responds
    # → alice releases lock
    
    alice.send_and_wait("bob", msg2)  # Acquires lock (new request)
    ✓ Works fine

Scenario 2: Concurrent requests (FAILS - SessionLockError)
    Task 1: alice.send_and_wait("bob", msg1)  # Gets lock
    Task 2: alice.send_and_wait("bob", msg2)  # Tries to get lock
    
    ✗ SessionLockError: Session already locked by alice
    
    Why? Alice is already waiting for msg1, can't wait for msg2
```

---

## Handler Processing and Message Reception

### Three ways receiver gets messages:

**1. Direct Handler Invocation (immediate, synchronous)**
```python
@register_conversation_handler
async def handle_message(message, context):
    # Called immediately when message arrives
    return {"response": "Got it!"}  # Send response back
```

**2. Get Unread Messages (pull model)**
```python
messages = await sdk.conversation.get_unread_messages("bob")
# Messages marked as read after retrieval
for msg in messages:
    print(msg)
```

**3. Wait for Response (blocking, pull model)**
```python
# Non-blocking message pending - receiver polling
response = await sdk.conversation.get_or_wait_for_response(
    "alice", "bob", timeout=30.0
)
# Waits for next message from alice, or timeout
```

---

## Key Design Question: Receiver Not Locked, Doing Other Tasks

> **Q:** When a message is sent but the receiver is NOT being locked (it's doing other tasks, not waiting), should we allow the client to register a processor call?

### Current Behavior:

**YES, this is already supported via handlers:**

```python
# At startup, register handler globally
@register_conversation_handler
async def my_handler(message, context):
    print(f"Processing: {message}")
    # Do background work here
    return {"processed": True}

# Later, when messages arrive
await sdk.conversation.send_no_wait("alice", "bob", message)
# → Handler is invoked automatically in background
# → No waiting, no locking
# → Handler can do async work
```

**For `send_and_wait()` - handler also invoked:**

```python
# Handler registered
response = await sdk.conversation.send_and_wait(
    "alice", "bob", 
    message,
    timeout=30.0
)

# What happens:
# 1. Message sent
# 2. Handler invoked with 100ms timeout
# 3. If handler responds immediately → Return it
# 4. If handler times out → Wait for manual response
# 5. If handler errors → Log it, wait for manual response
```

### Architecture:

```
┌─────────────┐
│   Handler   │ <- Registered globally at startup
│  (one per   │   @register_conversation_handler
│  message    │   @register_one_way_handler
│   type)     │   @register_meeting_handler
└──────┬──────┘
       │
       ├─ ONE-WAY: asyncio.create_task() (fire-and-forget)
       │
       └─ CONVERSATION:
          ├─ send_and_wait(): Try immediate response (100ms)
          ├─ send_no_wait(): asyncio.create_task() (fire-and-forget)
          └─ Always async if timeout
```

---

## Recommended Usage Patterns

### Pattern 1: Fire-and-Forget Notifications
```python
# Sender: Fire and forget
await sdk.one_way.send(
    "service_a", 
    ["service_b", "service_c"],
    {"alert": "Memory low"}
)

# Receivers: Handler processes automatically in background
@register_one_way_handler
async def handle_alert(message, context):
    await log_alert(message)
    await send_to_monitoring()
```

### Pattern 2: Request-Response with Guaranteed Processing
```python
# Sender: Wait for response
response = await sdk.conversation.send_and_wait(
    "client",
    "worker",
    {"task": "compute"},
    timeout=60.0
)

# Receiver: Handler processes and returns response immediately
@register_conversation_handler
async def handle_task(message, context):
    result = await compute(message["task"])
    return {"result": result}
```

### Pattern 3: Async Message Queue
```python
# Sender: Queue and continue
await sdk.conversation.send_no_wait(
    "producer",
    "consumer",
    {"data": "batch_1"}
)

# Receiver: Poll for messages at own pace
messages = await sdk.conversation.get_unread_messages("consumer")
for msg in messages:
    await process(msg)
```

### Pattern 4: Queue with Auto-Processing Handler
```python
# Sender: Queue message
await sdk.conversation.send_no_wait("producer", "consumer", message)

# Receiver: Handler auto-processes in background (no need to poll)
@register_conversation_handler
async def auto_process(message, context):
    # Automatically invoked when message arrives
    await database.insert(message)
    await send_downstream(message)
```

---

## Session Lock Safety

### The Lock Problem

PostgreSQL advisory locks are **connection-scoped**. If acquired on one connection but released on another, the lock leaks:

```python
# ❌ WRONG - Lock leak!
async with db.connection() as conn1:
    await lock.acquire(conn1)
    # ... do work ...

async with db.connection() as conn2:  # Different connection!
    await lock.release(conn2)  # Lock NOT released! Still held by conn1

# The lock persists until conn1 is closed or timeout occurs
```

### The Fix (Implemented)

```python
# ✓ CORRECT - Same connection for acquire and release
async with db.connection() as connection:
    lock_acquired = await session_lock.acquire(connection)
    try:
        # ... do work ...
    finally:
        await session_lock.release(connection)  # Same connection - safe!
```

This is explicitly documented in the code:
```python
# CRITICAL FIX: Use single connection scope for lock acquire/release
# PostgreSQL advisory locks are connection-scoped, so we must acquire and
# release on the SAME connection to avoid lock leaks
```

---

## Summary: To Answer Your Question

### "What if there's an existing session, should we allow processor calls?"

**Answer: YES, already supported.**

**How it works:**

| Scenario | Method | Handler Invoked? | Receiver Locked? | Can Do Other Tasks? |
|----------|--------|------------------|------------------|-------------------|
| Notify, no response | `send_no_wait()` | ✅ Yes (async) | ❌ No | ✅ Yes |
| Notify, no response | `one_way.send()` | ✅ Yes (async) | ❌ No | ✅ Yes |
| Request-response | `send_and_wait()` | ✅ Yes (100ms) | ✅ Yes (temp) | ⚠️ No (waiting) |
| Request-response | `send_no_wait()` | ✅ Yes (async) | ❌ No | ✅ Yes |

**Key Design Points:**

1. **Handlers are global** - Registered once at startup, work for all agents
2. **Non-blocking patterns** - `send_no_wait()` and `one_way.send()` use `asyncio.create_task()`
3. **Handler auto-invocation** - Receiver doesn't need to manually poll if handler registered
4. **Async processing** - Handlers run in background, receiver can do other tasks
5. **Existing sessions** - Reused automatically, messages accumulate
6. **Session locks** - Prevent concurrent `send_and_wait()` on same session
7. **Critical fix** - Lock acquire/release on same connection to prevent leaks

---

## Code References

- **`conversation.py`**: `send_and_wait()` (line 99), `send_no_wait()` (line 360)
- **`one_way.py`**: `send()` (line 65)
- **`handlers/registry.py`**: Handler registration and invocation
- **`database/manager.py`**: Connection pooling and lock management
- **`utils/locks.py`**: SessionLock implementation
