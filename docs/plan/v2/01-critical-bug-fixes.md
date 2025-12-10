# Phase 1: Critical Bug Fixes

**Priority:** 🔴 CRITICAL  
**Duration:** 3-4 days  
**Must Complete Before:** Phase 2 can begin  
**Risk Level:** HIGH (touching core lock mechanisms)

---

## Overview

This phase addresses critical bugs that can cause deadlocks, data corruption, or system failures. These issues must be fixed before any other work proceeds.

---

## Critical Issues

### Issue 1.1: Lock Connection Scope Mismatch ⚠️ DEADLOCK RISK

**File:** `agent_messaging/messaging/conversation.py`  
**Method:** `send_and_wait()`  
**Lines:** 196-197, 286-288  
**Severity:** CRITICAL

#### Current Code (BROKEN)
```python
# Line 196-197: Acquire lock on connection A
async with self._message_repo.db_manager.connection() as connection:
    lock_acquired = await session_lock.acquire(connection)
    if not lock_acquired:
        raise RuntimeError(f"Failed to acquire lock for session {session.id}")

try:
    # ... handler invocation and waiting ...
finally:
    # Line 286-288: Release lock on connection B (DIFFERENT CONNECTION!)
    async with self._message_repo.db_manager.connection() as connection:
        await session_lock.release(connection)
    await self._session_repo.set_locked_agent(session.id, None)
```

#### Problem
PostgreSQL advisory locks are **connection-scoped**. Acquiring on connection A and releasing on connection B does nothing. The lock remains held until connection A closes (connection pool timeout or process exit).

#### Impact
- **Deadlocks** when multiple agents try to use the same session
- **Lock leaks** that never get cleaned up
- **Resource exhaustion** as connection pool fills with locked connections
- **System hangs** requiring database restart

#### Root Cause
The `async with connection` context manager closes the connection when the block exits. The lock acquisition happens in one context, but the try-finally block expects to use a different connection later.

#### Solution

**Option A: Keep Single Connection (Recommended)**
```python
# Acquire connection ONCE and hold it through the entire operation
async with self._message_repo.db_manager.connection() as connection:
    # Acquire lock on this connection
    lock_acquired = await session_lock.acquire(connection)
    if not lock_acquired:
        raise RuntimeError(f"Failed to acquire lock for session {session.id}")
    
    try:
        # Set sender as locked agent
        await self._session_repo.set_locked_agent(session.id, sender.id)
        
        # ... rest of the logic ...
        
    finally:
        # Release lock on SAME connection
        await session_lock.release(connection)
        await self._session_repo.set_locked_agent(session.id, None)
```

**Option B: Use Database-Level Lock Tracking (Alternative)**
```python
# Store lock info in database so any connection can release
await self._session_repo.acquire_session_lock(session.id, sender.id)
try:
    # ... operation ...
finally:
    await self._session_repo.release_session_lock(session.id)
```

#### Recommendation
**Use Option A** - simpler, more reliable, follows PostgreSQL advisory lock best practices.

#### Testing Requirements
- ✅ Test lock acquisition and release on same connection
- ✅ Test lock release in finally block even when exceptions occur
- ✅ Test concurrent send_and_wait calls don't deadlock
- ✅ Test lock is released when handler times out
- ✅ Test lock is released when wait times out
- ✅ Performance test: ensure single connection doesn't bottleneck

#### Implementation Steps
1. Refactor `send_and_wait()` to use single connection scope
2. Update `SessionLock` class to validate connection consistency
3. Add connection validation in lock acquire/release
4. Add comprehensive integration tests
5. Run stress test with concurrent sessions

---

### Issue 1.2: Meeting Lock Not Implemented ⚠️ RACE CONDITION

**File:** `agent_messaging/messaging/meeting.py`  
**Method:** `speak()`  
**Lines:** 420-540  
**Severity:** CRITICAL

#### Current Code (BROKEN)
```python
async def speak(self, agent_external_id: str, meeting_id: UUID, message: T) -> UUID:
    # Line 93: Lock dictionary declared but NEVER USED
    # self._meeting_locks: Dict[UUID, SessionLock] = {}
    
    # No lock acquisition before checking turn!
    if meeting.current_speaker_id != agent.id:
        raise NotYourTurnError(f"It's not {agent_external_id}'s turn")
    
    # Store message (RACE CONDITION - multiple agents can reach here)
    message_id = await self._message_repo.create(...)
    
    # Update current speaker (RACE CONDITION - concurrent updates)
    await self._meeting_repo.set_current_speaker(...)
```

#### Problem
Multiple agents can call `speak()` concurrently. Without locking:
1. Agent A checks `current_speaker_id == A` ✅
2. Agent B checks `current_speaker_id == A` ❌ (but hasn't updated yet)
3. Agent A stores message and updates speaker to B
4. Agent B stores message and updates speaker to C
5. **Result:** Both agents spoke, breaking turn-based rule

#### Impact
- **Turn-based coordination broken** - multiple agents speak at once
- **Meeting state corruption** - wrong current_speaker_id
- **Message ordering issues** - unclear who spoke when
- **Event sequence broken** - turn_changed events fire incorrectly

#### Solution

**Implement per-meeting advisory locks:**

```python
async def speak(
    self,
    agent_external_id: str,
    meeting_id: UUID,
    message: T,
) -> UUID:
    # Validate agent, meeting, etc. (before lock)
    # ...
    
    # Acquire meeting lock
    meeting_lock = SessionLock(meeting_id)  # Uses meeting UUID as lock key
    
    async with self._message_repo.db_manager.connection() as connection:
        lock_acquired = await meeting_lock.acquire(connection)
        if not lock_acquired:
            raise MeetingError(f"Meeting {meeting_id} is locked by another operation")
        
        try:
            # Re-fetch meeting state after lock acquired
            meeting = await self._meeting_repo.get_by_id(meeting_id)
            
            # Validate it's still your turn (state might have changed)
            if meeting.current_speaker_id != agent.id:
                raise NotYourTurnError(f"It's not {agent_external_id}'s turn anymore")
            
            # Store message
            message_id = await self._message_repo.create(...)
            
            # Update current speaker
            await self._meeting_repo.set_current_speaker(...)
            
            # Start timeout for next speaker
            await self._timeout_manager.start_turn_timeout(...)
            
            # Emit event
            await self._event_handler.emit_turn_changed(...)
            
            return message_id
            
        finally:
            # Always release lock
            await meeting_lock.release(connection)
```

#### Additional Changes Needed

**1. Lock pass_turn() method:**
```python
async def pass_turn(self, agent_external_id: str, meeting_id: UUID) -> None:
    meeting_lock = SessionLock(meeting_id)
    async with self._message_repo.db_manager.connection() as connection:
        lock_acquired = await meeting_lock.acquire(connection)
        # ... acquire lock before changing turn ...
```

**2. Lock start_meeting() method:**
```python
async def start_meeting(self, host_external_id: str, meeting_id: UUID) -> None:
    meeting_lock = SessionLock(meeting_id)
    async with self._message_repo.db_manager.connection() as connection:
        lock_acquired = await meeting_lock.acquire(connection)
        # ... acquire lock before starting and setting first speaker ...
```

**3. Lock end_meeting() method:**
```python
async def end_meeting(self, host_external_id: str, meeting_id: UUID) -> None:
    meeting_lock = SessionLock(meeting_id)
    async with self._message_repo.db_manager.connection() as connection:
        lock_acquired = await meeting_lock.acquire(connection)
        # ... acquire lock before ending ...
```

#### Testing Requirements
- ✅ Test concurrent speak() calls are serialized
- ✅ Test turn validation happens after lock acquired
- ✅ Test lock released even when NotYourTurnError occurs
- ✅ Test multiple meetings can proceed concurrently (different locks)
- ✅ Test timeout handling with locks
- ✅ Stress test: 10 agents trying to speak simultaneously

#### Implementation Steps
1. Add meeting lock acquisition to `speak()`
2. Add meeting lock acquisition to `pass_turn()`
3. Add meeting lock acquisition to `start_meeting()`
4. Add meeting lock acquisition to `end_meeting()`
5. Refetch meeting state after lock acquired (important!)
6. Add integration tests for concurrent operations
7. Run stress test with multiple concurrent meetings

---

### Issue 1.3: Handler Response Not Stored ⚠️ DATA LOSS

**File:** `agent_messaging/messaging/conversation.py`  
**Method:** `send_and_wait()`  
**Lines:** 230-250  
**Severity:** HIGH

#### Current Code (INCOMPLETE)
```python
# Line 235: Handler invoked but return value IGNORED
self._handler_registry.invoke_handler_async(
    message,
    context,
)

# Lines 240-249: Check for response messages in database
immediate_responses = await self._message_repo.get_unread_messages_from_sender(
    sender.id, recipient.id
)
if immediate_responses:
    # ... return first response ...
```

#### Problem
Handler's return value is discarded. The code expects the handler to manually call `send_no_wait()` to send a response, but this is:
1. Not documented clearly
2. Not enforced
3. Creates circular dependency (handler needs SDK reference)
4. Doesn't work for synchronous handlers that just return a value

#### Impact
- **Lost responses** - handler returns value but sender never receives it
- **Confusion** - developers expect handler return value to be sent automatically
- **Workaround complexity** - handlers need SDK reference to send responses
- **Inconsistent behavior** - works differently than users expect

#### Solution

**Option A: Auto-send handler response (Recommended)**
```python
# Invoke handler and capture response
response_task = self._handler_registry.invoke_handler_async(message, context)

# Check if handler completed synchronously
try:
    handler_response = await asyncio.wait_for(response_task, timeout=0.1)
    
    if handler_response is not None:
        # Handler returned a response - store it automatically
        response_content = self._serialize_content(handler_response)
        await self._message_repo.create(
            sender_id=recipient.id,
            recipient_id=sender.id,
            session_id=session.id,
            content=response_content,
            message_type=MessageType.USER_DEFINED,
        )
        
        # Return immediately
        return handler_response
        
except asyncio.TimeoutError:
    # Handler still running, will send response later via send_no_wait()
    pass

# Continue with normal wait logic...
```

**Option B: Provide response callback**
```python
# Add to MessageContext
class MessageContext(BaseModel):
    # ... existing fields ...
    response_callback: Optional[Callable] = None

# In send_and_wait:
async def _response_sender(response: T):
    content = self._serialize_content(response)
    await self._message_repo.create(...)
    self._waiting_responses[session.id] = response
    self._waiting_events[session.id].set()

context = MessageContext(
    ...,
    response_callback=_response_sender
)
```

#### Recommendation
**Use Option A** - simpler, more intuitive, works with existing code.

#### Testing Requirements
- ✅ Test handler that returns immediate response
- ✅ Test handler that returns None (sends response later)
- ✅ Test handler that calls send_no_wait() manually
- ✅ Test handler that times out without responding
- ✅ Test serialization of various response types

#### Implementation Steps
1. Capture handler response from invoke_handler_async()
2. Auto-store response if handler completes quickly
3. Fall back to waiting for database response if handler takes longer
4. Update documentation to clarify both modes work
5. Add tests for both immediate and delayed responses

---

### Issue 1.4: Lock Cleanup on Early Exceptions

**File:** `agent_messaging/messaging/conversation.py`  
**Method:** `send_and_wait()`  
**Lines:** 196-204  
**Severity:** MEDIUM-HIGH

#### Current Code (POTENTIAL LEAK)
```python
async with self._message_repo.db_manager.connection() as connection:
    lock_acquired = await session_lock.acquire(connection)
    if not lock_acquired:
        raise RuntimeError(f"Failed to acquire lock for session {session.id}")

try:
    # Set sender as locked agent
    await self._session_repo.set_locked_agent(session.id, sender.id)
    # ^^^ If this raises, we're not in the try block's protection yet!
```

#### Problem
If `set_locked_agent()` raises an exception before the try block executes, the lock is acquired but never released (connection scope already exited).

#### Solution
Move lock acquisition inside try block:

```python
session_lock = SessionLock(session.id)
connection = None

try:
    connection = await self._message_repo.db_manager.connection().__aenter__()
    
    lock_acquired = await session_lock.acquire(connection)
    if not lock_acquired:
        raise SessionLockError(f"Failed to acquire lock for session {session.id}")
    
    await self._session_repo.set_locked_agent(session.id, sender.id)
    
    # ... rest of operation ...
    
finally:
    # Clean up
    if connection:
        await session_lock.release(connection)
        await self._message_repo.db_manager.connection().__aexit__(None, None, None)
    await self._session_repo.set_locked_agent(session.id, None)
```

---

## Implementation Order

1. **Issue 1.1** (Lock scope) - Day 1-2
2. **Issue 1.4** (Lock cleanup) - Day 2 (depends on 1.1)
3. **Issue 1.2** (Meeting locks) - Day 3-4
4. **Issue 1.3** (Handler response) - Day 4 (can parallel with 1.2)

---

## Testing Strategy

### Unit Tests
- Test each lock acquisition/release in isolation
- Test exception handling for each failure point
- Test connection scope validation

### Integration Tests
- Test concurrent session operations (deadlock detection)
- Test concurrent meeting operations (turn serialization)
- Test handler response flow end-to-end

### Stress Tests
- 100 concurrent send_and_wait() calls
- 10 concurrent meetings with 10 agents each
- Lock leak detection (monitor pg_locks table)

### Performance Benchmarks
- Measure lock acquisition latency (baseline: <1ms)
- Measure send_and_wait() throughput (baseline: 1000 ops/sec)
- Measure meeting turn transition time (baseline: <10ms)

---

## Rollback Plan

If critical issues arise during deployment:

1. **Immediate rollback** to v0.1.0
2. **Isolate failing component** (conversation vs meeting)
3. **Deploy hotfix** for that component only
4. **Re-test in staging** before production

---

## Acceptance Criteria

- [ ] All lock acquisitions and releases use same connection
- [ ] Meeting operations are properly serialized with locks
- [ ] Handler responses are captured and sent automatically
- [ ] No lock leaks detected in stress tests (pg_locks query)
- [ ] All existing tests pass
- [ ] New integration tests pass
- [ ] Performance meets or exceeds baselines
- [ ] Code review approved by 2+ engineers
- [ ] Stress tests run for 1 hour without failures

---

**Status:** 📝 Ready for Implementation  
**Assignee:** TBD  
**Estimated Completion:** Day 4
