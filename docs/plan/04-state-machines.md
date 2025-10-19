# Agent Messaging Protocol - State Machines & Flow Diagrams

This document provides detailed state machines and sequence diagrams for all conversation types.

---

## 1. Synchronous Conversation State Machine

### Agent States in Sync Conversation

```
┌─────────────┐
│    IDLE     │  (No active conversation)
└──────┬──────┘
       │
       │ send_and_wait() called
       ▼
┌─────────────┐
│   SENDING   │  (Creating/getting session, sending message)
└──────┬──────┘
       │
       ├─► Is recipient waiting? ───► No ────┐
       │                                     │
       │                                     ▼
       │                          ┌─────────────────┐
       │                          │ INVOKE_HANDLER  │
       │                          └────────┬────────┘
       │                                   │
       │                                   │ Handler processes
       │                                   ▼
       │                          ┌─────────────────┐
       │                          │ RECIPIENT_ACTIVE│
       │                          └─────────────────┘
       │
       │ Yes (recipient already waiting)
       ▼
┌─────────────┐
│   WAITING   │◄──────────┐ (Agent locked, waiting for reply)
└──────┬──────┘           │
       │                  │
       │                  │ Still waiting (other agent processing)
       │                  │
       ├─► Timeout? ──────┴─► Continue waiting
       │
       │ Reply received
       ▼
┌─────────────┐
│  UNLOCKED   │  (Received reply, can process response)
└──────┬──────┘
       │
       │ Handle response
       ▼
┌─────────────┐
│    IDLE     │  (Ready for next message)
└─────────────┘
       │
       │ reply() called
       ▼
┌─────────────┐
│  REPLYING   │  (Sending reply)
└──────┬──────┘
       │
       │ Unlock waiting agent
       ▼
┌─────────────┐
│   WAITING   │  (Now this agent waits)
└─────────────┘
```

### Session States

```
        [No Session]
              │
              │ First message sent
              ▼
       ┌─────────────┐
       │   ACTIVE    │  (Session exists, both agents can send)
       └──────┬──────┘
              │
              │ send_and_wait() called
              ▼
       ┌─────────────┐
       │   WAITING   │◄──────┐ (One agent locked, waiting for reply)
       └──────┬──────┘       │
              │               │
              │ reply()       │ Another message while waiting
              ├───────────────┘
              │
              │ end_conversation()
              ▼
       ┌─────────────┐
       │    ENDED    │  (Session closed)
       └─────────────┘
```

---

## 2. Synchronous Conversation - Sequence Diagrams

### Scenario A: First Message (No Existing Session)

```
Agent A          SDK            Session         Agent B
   │              │             Repository      Handler
   │              │                 │              │
   │ send_and_wait()              │              │
   ├─────────────►│                 │              │
   │              │                 │              │
   │              │ get_or_create_session()        │
   │              ├────────────────►│              │
   │              │◄────────────────┤              │
   │              │   [NEW SESSION]                │
   │              │                 │              │
   │              │ save_message()  │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │              │ is_B_waiting?   │              │
   │              ├────────────────►│              │
   │              │◄────────────────┤              │
   │              │      [NO]       │              │
   │              │                 │              │
   │              │ invoke_handler() ──────────────►│
   │              │                 │              │
   │              │                 │    (B processes)
   │              │                 │              │
   │              │ lock_agent(A)   │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │ [BLOCKED]    │                 │              │
   │   wait...    │                 │              │
   │   wait...    │                 │              │
   │              │                 │              │
   │              │                 │    reply()   │
   │              │◄────────────────────────────────┤
   │              │                 │              │
   │              │ save_message()  │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │              │ unlock_agent(A) │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │ [UNBLOCKED]  │                 │              │
   │◄─────────────┤                 │              │
   │   response   │                 │              │
   │              │                 │              │
   │              │ lock_agent(B)   │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │              │                 │   [BLOCKED]  │
```

### Scenario B: Both Agents Talking (Session Exists)

```
Agent A          SDK            Session         Agent B
  (waiting)       │             Repository     (waiting)
   │              │                 │              │
   │              │                 │   send_and_wait()
   │              │                 │◄─────────────┤
   │              │◄────────────────────────────────┤
   │              │                 │              │
   │              │ get_session()   │              │
   │              ├────────────────►│              │
   │              │◄────────────────┤              │
   │              │ [EXISTING SESSION]             │
   │              │                 │              │
   │              │ is_A_waiting?   │              │
   │              ├────────────────►│              │
   │              │◄────────────────┤              │
   │              │     [YES]       │              │
   │              │                 │              │
   │              │ save_message()  │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │              │ unlock_agent(A) │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │ [UNBLOCKED]  │                 │              │
   │◄─────────────┤                 │              │
   │   response   │                 │              │
   │              │                 │              │
   │              │ lock_agent(B)   │              │
   │              ├────────────────►│              │
   │              │                 │              │
   │              │                 │   [BLOCKED]  │
```

---

## 3. Meeting State Machine

### Meeting States

```
         [No Meeting]
              │
              │ create_meeting()
              ▼
       ┌─────────────┐
       │   CREATED   │  (Meeting exists, agents invited)
       └──────┬──────┘
              │
              │ All agents called attend_meeting()
              ▼
       ┌─────────────┐
       │    READY    │  (All agents present, waiting to start)
       └──────┬──────┘
              │
              │ start_meeting() by host
              ▼
       ┌─────────────┐
       │   ACTIVE    │◄─────┐ (Meeting in progress)
       └──────┬──────┘      │
              │              │
              │ speak()      │ Continue speaking
              ├──────────────┘
              │
              │ end_meeting() by host
              ▼
       ┌─────────────┐
       │    ENDED    │  (Meeting closed)
       └─────────────┘
```

### Participant States

```
         [Not Invited]
              │
              │ create_meeting()
              ▼
       ┌─────────────┐
       │   INVITED   │  (Received invitation)
       └──────┬──────┘
              │
              │ attend_meeting()
              ▼
       ┌─────────────┐
       │  ATTENDING  │  (Present, not yet started)
       └──────┬──────┘
              │
              │ start_meeting()
              ▼
       ┌─────────────┐
       │   WAITING   │◄─────┐ (Locked, waiting for turn)
       └──────┬──────┘      │
              │              │
              │ My turn      │ Not my turn
              ▼              │
       ┌─────────────┐       │
       │  SPEAKING   │───────┘ (Unlocked, can speak)
       └──────┬──────┘
              │
              │ speak() called (pass turn to next)
              └──────► [WAITING]
              │
              │ leave_meeting()
              ▼
       ┌─────────────┐
       │    LEFT     │  (No longer in meeting)
       └─────────────┘
```

---

## 4. Meeting Flow - Sequence Diagram

### Complete Meeting Flow

```
Host (Alice)    Agent Bob      Agent Charlie      SDK           Meeting Repo
     │              │               │              │                 │
     │ create_meeting([Alice, Bob, Charlie])       │                 │
     ├─────────────────────────────────────────────►│                 │
     │              │               │              │                 │
     │              │               │              │ create_meeting()│
     │              │               │              ├────────────────►│
     │              │               │              │◄────────────────┤
     │              │               │              │                 │
     │              │               │              │ invoke_handler(Alice)
     │◄─────────────────────────────────────────────┤                 │
     │              │               │              │                 │
     │              │               │              │ invoke_handler(Bob)
     │              │◄──────────────────────────────┤                 │
     │              │               │              │                 │
     │              │               │              │ invoke_handler(Charlie)
     │              │               │◄─────────────┤                 │
     │              │               │              │                 │
     │ attend_meeting()             │              │                 │
     ├─────────────────────────────────────────────►│                 │
     │ [LOCKED]     │               │              │ lock(Alice)     │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │ attend_meeting()             │                 │
     │              ├──────────────────────────────►│                 │
     │              │ [LOCKED]      │              │ lock(Bob)       │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │ attend_meeting()               │
     │              │               ├──────────────►│                 │
     │              │               │ [LOCKED]     │ lock(Charlie)   │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │ start_meeting(next=Bob)        │
     │◄─────────────────────────────────────────────┤                 │
     │              │               │              │                 │
     │              │               │              │ set_speaker(Bob)│
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │              │ unlock(Bob)     │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │ [RE-LOCKED]  │               │              │ lock(Alice)     │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │ [UNLOCKED]    │              │                 │
     │              │ (My turn!)    │              │                 │
     │              │               │              │                 │
     │              │ speak(next=Charlie)          │                 │
     │              ├──────────────────────────────►│                 │
     │              │               │              │                 │
     │              │               │              │ save_message()  │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │              │ set_speaker(Charlie)
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │              │ unlock(Charlie) │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │ [RE-LOCKED]   │              │ lock(Bob)       │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │              │               │ [UNLOCKED]   │                 │
     │              │               │ (My turn!)   │                 │
     │              │               │              │                 │
     │              │               │ speak(next=Alice)              │
     │              │               ├──────────────►│                 │
     │              │               │              │                 │
     │              │               │              │ ... (continues round-robin)
     │              │               │              │                 │
     │              │               │              │                 │
     │ end_meeting()                │              │                 │
     ├─────────────────────────────────────────────►│                 │
     │              │               │              │                 │
     │              │               │              │ unlock_all()    │
     │              │               │              ├────────────────►│
     │              │               │              │                 │
     │ [UNLOCKED]   │               │              │                 │
     │◄─────────────────────────────────────────────┤                 │
     │ (ended msg)  │               │              │                 │
     │              │               │              │                 │
     │              │ [UNLOCKED]    │              │                 │
     │              │◄──────────────────────────────┤                 │
     │              │ (ended msg)   │              │                 │
     │              │               │              │                 │
     │              │               │ [UNLOCKED]   │                 │
     │              │               │◄─────────────┤                 │
     │              │               │ (ended msg)  │                 │
```

---

## 5. Timeout Handling State Machine

### Agent Timeout in Meeting

```
       ┌─────────────┐
       │  SPEAKING   │  (Agent's turn)
       └──────┬──────┘
              │
              │ Turn timer started
              ▼
       ┌─────────────┐
       │   TIMING    │
       └──────┬──────┘
              │
              ├─► speak() before timeout ─────► [Success, move to next]
              │
              ├─► Timeout expires ──────────┐
              │                             │
              ▼                             ▼
       ┌─────────────┐            ┌──────────────────┐
       │ TIMED_OUT   │            │ SYSTEM_ACTION    │
       └──────┬──────┘            └────────┬─────────┘
              │                             │
              │                   ┌─────────▼─────────┐
              │                   │ Save timeout msg  │
              │                   └─────────┬─────────┘
              │                             │
              │                   ┌─────────▼─────────┐
              │                   │ Lock timed-out    │
              │                   │ agent             │
              │                   └─────────┬─────────┘
              │                             │
              │                   ┌─────────▼─────────┐
              │                   │ Move to next      │
              │                   │ speaker           │
              │                   └─────────┬─────────┘
              │                             │
              │                   ┌─────────▼─────────┐
              │                   │ Emit TIMED_OUT    │
              │                   │ event             │
              │                   └───────────────────┘
              │
              │ Agent tries to speak() after timeout
              ▼
       ┌─────────────┐
       │ LATE_SPEAK  │  (Message saved with note, agent stays locked)
       └──────┬──────┘
              │
              │ Continue with current speaker
              ▼
       [Agent remains locked until next turn or meeting ends]
```

---

## 6. Asynchronous Conversation State Machine

### Agent States

```
┌─────────────┐
│    IDLE     │  (No active conversation)
└──────┬──────┘
       │
       │ send() called (non-blocking)
       ▼
┌─────────────┐
│   SENDING   │  (Saving message)
└──────┬──────┘
       │
       │ Message saved
       ▼
┌─────────────┐
│    IDLE     │  (Can continue immediately)
└──────┬──────┘
       │
       │ get_unread_messages() or wait_for_message()
       ▼
┌─────────────┐
│  CHECKING   │  (Querying for messages)
└──────┬──────┘
       │
       ├─► Messages found ──────► Return messages
       │
       ├─► No messages (get) ───► Return empty list
       │
       └─► No messages (wait) ──┐
                                │
                                ▼
                        ┌─────────────┐
                        │   WAITING   │  (Blocking until message or timeout)
                        └──────┬──────┘
                               │
                               ├─► Message arrives ──► Return message
                               │
                               └─► Timeout ──────────► Return None
```

---

## 7. Lock Coordination Pattern

### PostgreSQL Advisory Locks

```python
# Lock ID calculation
lock_id = hash(agent_external_id) & 0x7FFFFFFFFFFFFFFF  # Positive 64-bit int

# Locking an agent
await conn.execute("SELECT pg_advisory_lock($1)", [lock_id])
# Agent is now blocked

# In another process/thread...
# Unlocking the agent
await conn.execute("SELECT pg_advisory_unlock($1)", [lock_id])
# Agent is now unblocked
```

### asyncio Coordination

```python
# Create event for coordination
unlock_events = {}  # agent_id -> asyncio.Event

# Waiting agent
event = asyncio.Event()
unlock_events[agent_id] = event

try:
    await asyncio.wait_for(event.wait(), timeout=timeout)
    return result
except asyncio.TimeoutError:
    return TimeoutError("Agent did not respond")
finally:
    del unlock_events[agent_id]

# Unlocking agent (from another coroutine)
if agent_id in unlock_events:
    unlock_events[agent_id].set()
```

---

## 8. Decision Trees

### When to Use Which Conversation Type?

```
Does sender need immediate response?
    │
    ├─► YES ──► Is response critical?
    │           │
    │           ├─► YES ──► Use SYNC CONVERSATION
    │           │           (send_and_wait)
    │           │
    │           └─► NO ───► Can sender check later?
    │                       │
    │                       ├─► YES ──► Use ASYNC CONVERSATION
    │                       │           (send + wait_for_message)
    │                       │
    │                       └─► NO ───► Use SYNC CONVERSATION
    │
    └─► NO ───► Does recipient need to know?
                │
                ├─► YES, but no response ──► Use ONE-WAY MESSAGE
                │
                └─► Multiple agents involved? ──► Use MEETING
```

### Meeting vs. Multiple Conversations?

```
Number of agents involved?
    │
    ├─► 2 agents ──────► Use CONVERSATION (sync or async)
    │
    └─► 3+ agents ──────► Need turn-taking?
                          │
                          ├─► YES ──────► Use MEETING
                          │
                          └─► NO ───────► Use multiple ASYNC CONVERSATIONS
```

---

## 9. Error Recovery State Machine

### Session Recovery After Failure

```
┌─────────────┐
│   ACTIVE    │  (Normal operation)
└──────┬──────┘
       │
       │ Database connection lost
       ▼
┌─────────────┐
│   ERROR     │
└──────┬──────┘
       │
       │ Retry logic
       ▼
┌─────────────┐
│  RETRYING   │
└──────┬──────┘
       │
       ├─► Success ────────────► [ACTIVE]
       │
       └─► Failure after N retries
                  │
                  ▼
           ┌─────────────┐
           │   FAILED    │  (Raise exception to user)
           └─────────────┘
```

---

## Summary

This document provides:

✓ **Complete state machines** for all conversation types  
✓ **Detailed sequence diagrams** for complex flows  
✓ **Lock coordination patterns**  
✓ **Decision trees** for choosing conversation types  
✓ **Timeout handling** visualization  
✓ **Error recovery** patterns

These diagrams should guide implementation and help with debugging complex interaction scenarios.
