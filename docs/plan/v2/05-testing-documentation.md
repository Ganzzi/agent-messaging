# Phase 5: Testing & Documentation

**Priority:** 🔴 CRITICAL  
**Duration:** 4-5 days  
**Depends On:** All previous phases  
**Risk Level:** LOW

---

## Overview

This phase ensures all new features are thoroughly tested, documented, and ready for production use. Includes comprehensive test suite, performance benchmarks, migration guide, and updated documentation.

---

## 5.1: Comprehensive Testing

**Priority:** CRITICAL  
**Effort:** 3 days

### Test Coverage Goals

- **Overall Coverage:** ≥ 85%
- **Critical Paths:** 100% (lock mechanisms, handler routing)
- **Edge Cases:** All identified scenarios tested
- **Performance:** Benchmarks for all operations

### Testing Strategy

#### 5.1.1: Unit Tests (Day 1)

**Lock Mechanisms**
```python
# test_locks.py
async def test_lock_acquire_release_same_connection():
    """Test lock acquired and released on same connection."""
    
async def test_lock_not_released_on_different_connection():
    """Verify bug: lock on conn A not released on conn B."""
    
async def test_lock_cleanup_on_exception():
    """Test lock released even when exception occurs."""
    
async def test_concurrent_lock_acquisition():
    """Test multiple agents trying to lock same session."""
    
async def test_meeting_lock_serializes_speakers():
    """Test meeting lock prevents simultaneous speaking."""
```

**Handler Routing**
```python
# test_handler_routing.py
async def test_one_way_handler_selection():
    """Test one-way messages route to one-way handler."""
    
async def test_conversation_handler_selection():
    """Test conversation messages route to conversation handler."""
    
async def test_meeting_handler_selection():
    """Test meeting messages route to meeting handler."""
    
async def test_system_handler_selection():
    """Test system messages route to system handler."""
    
async def test_type_based_handler_selection():
    """Test handler selected by message type."""
    
async def test_fallback_to_default_handler():
    """Test fallback when no specific handler found."""
    
async def test_backward_compatibility():
    """Test old register() API still works."""
```

**Query Methods**
```python
# test_query_methods.py
async def test_get_sent_messages():
    """Test retrieving sent one-way messages."""
    
async def test_get_received_messages_with_filter():
    """Test filtering received messages by read status."""
    
async def test_conversation_history():
    """Test getting conversation history."""
    
async def test_session_statistics():
    """Test session statistics calculation."""
    
async def test_meeting_analytics():
    """Test meeting participation analysis."""
    
async def test_pagination():
    """Test pagination works correctly."""
    
async def test_metadata_filtering():
    """Test filtering by metadata."""
```

#### 5.1.2: Integration Tests (Day 2)

**End-to-End Scenarios**
```python
# test_integration.py
async def test_full_sync_conversation_flow():
    """Test complete sync conversation with lock."""
    # 1. Alice sends to Bob
    # 2. Bob's handler receives
    # 3. Bob returns response
    # 4. Alice receives response
    # 5. Verify lock released

async def test_concurrent_conversations():
    """Test multiple concurrent conversations don't deadlock."""
    # Start 10 conversations simultaneously
    # Verify all complete without deadlock

async def test_meeting_turn_coordination():
    """Test turn-based speaking in meeting."""
    # 1. Start meeting
    # 2. Agent A speaks
    # 3. Agent B tries to speak (should fail - not their turn)
    # 4. Turn passes to B
    # 5. Agent B speaks successfully

async def test_handler_error_recovery():
    """Test system recovers when handler fails."""
    # 1. Send message
    # 2. Handler raises exception
    # 3. Verify lock released
    # 4. Verify error logged
    # 5. Verify sender notified

async def test_timeout_handling():
    """Test timeout in sync conversation."""
    # 1. Alice sends to Bob
    # 2. Bob's handler takes too long
    # 3. Verify timeout occurs
    # 4. Verify lock released
    # 5. Verify Alice gets TimeoutError
```

**Migration Tests**
```python
# test_migration.py
async def test_old_handler_api_with_deprecation():
    """Test old register() API works with warning."""
    with warnings.catch_warnings(record=True) as w:
        @sdk.register_handler()
        async def old_handler(msg, ctx):
            return None
        
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)

async def test_mixed_old_new_handlers():
    """Test old and new handlers coexist."""
    @sdk.register_handler()  # Old API
    async def old_handler(msg, ctx):
        return None
    
    @sdk.register_conversation_handler()  # New API
    async def new_handler(msg, ctx):
        return None
    
    # Both should work
```

#### 5.1.3: Stress Tests (Day 3)

**Load Testing**
```python
# test_stress.py
async def test_1000_concurrent_conversations():
    """Test system handles 1000 concurrent conversations."""
    tasks = []
    for i in range(1000):
        task = sdk.conversation.send_and_wait(...)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    assert all(r is not None for r in results)

async def test_lock_leak_detection():
    """Test no locks leak over 1 hour."""
    start_locks = await count_advisory_locks()
    
    # Run operations for 1 hour
    for _ in range(3600):
        await sdk.conversation.send_and_wait(...)
        await asyncio.sleep(1)
    
    end_locks = await count_advisory_locks()
    assert end_locks == start_locks

async def test_connection_pool_exhaustion():
    """Test system handles connection pool exhaustion."""
    # Attempt to exceed max pool size
    # Verify graceful degradation
```

**Performance Benchmarks**
```python
# test_benchmarks.py
async def test_send_and_wait_latency():
    """Benchmark: send_and_wait should complete in <50ms."""
    times = []
    for _ in range(100):
        start = time.time()
        await sdk.conversation.send_and_wait(...)
        end = time.time()
        times.append(end - start)
    
    avg_time = sum(times) / len(times)
    assert avg_time < 0.05  # 50ms

async def test_query_throughput():
    """Benchmark: should handle 1000 queries/sec."""
    start = time.time()
    for _ in range(1000):
        await sdk.one_way.get_received_messages(...)
    end = time.time()
    
    qps = 1000 / (end - start)
    assert qps >= 1000

async def test_meeting_turn_latency():
    """Benchmark: turn transition should complete in <10ms."""
    # Measure time from speak() to next speaker ready
```

---

## 5.2: Documentation Updates

**Priority:** CRITICAL  
**Effort:** 2 days

### 5.2.1: API Reference Update

**File:** `docs/api-reference.md`

Add sections for:
- New query methods (all signatures)
- Handler type system (OneWayHandler, ConversationHandler, etc.)
- MessageContext enhancements
- Metadata system
- Advanced filtering options
- Meeting analytics methods

### 5.2.2: Migration Guide

**File:** `docs/plan/v2/MIGRATION_GUIDE.md`

```markdown
# Migration Guide: v0.1.0 → v2.0.0

## Overview
This guide helps you migrate from v0.1.0 to v2.0.0.

## Breaking Changes
None (fully backward compatible with deprecations)

## Deprecated Features
1. `sdk.register_handler()` - Use `register_conversation_handler()` instead

## New Features
1. Context-specific handlers
2. Message query methods
3. Message metadata
4. Advanced filtering
5. Meeting analytics

## Step-by-Step Migration

### Step 1: Update Package
```bash
pip install agent-messaging==2.0.0
```

### Step 2: Update Handler Registration
**Before:**
```python
@sdk.register_handler()
async def my_handler(message, context):
    if context.session_id:
        # Conversation
        return {"response": "OK"}
    else:
        # One-way
        pass
```

**After:**
```python
@sdk.register_conversation_handler()
async def handle_conversation(message, context):
    return {"response": "OK"}

@sdk.register_one_way_handler()
async def handle_notification(message, context):
    print(f"Notification: {message}")
```

### Step 3: Use New Query Methods
```python
# Get conversation history
messages = await sdk.conversation.get_conversation_history(
    "alice", "bob", limit=100
)

# Get meeting analytics
stats = await sdk.meeting.get_meeting_statistics(meeting_id)
```

### Step 4: Add Metadata (Optional)
```python
await sdk.one_way.send(
    sender_external_id="alice",
    recipient_external_ids=["bob"],
    message={"text": "Hello"},
    metadata={"priority": "high"}  # NEW
)
```

## Troubleshooting

### Deprecation Warnings
If you see: `DeprecationWarning: register() is deprecated`
- Action: Update to `register_conversation_handler()` or `register_one_way_handler()`

### Lock-Related Errors
If you experience deadlocks or lock timeouts:
- Cause: Fixed in v2.0.0 (lock connection scope bug)
- Action: Update to v2.0.0 immediately

## Testing Your Migration

Run this checklist:
- [ ] All existing tests pass
- [ ] No unexpected deprecation warnings
- [ ] New features work as expected
- [ ] Performance is same or better
```

### 5.2.3: Breaking Changes Document

**File:** `docs/plan/v2/BREAKING_CHANGES.md`

```markdown
# Breaking Changes

## v2.0.0 (Target Release)

### No Breaking Changes
v2.0.0 is fully backward compatible with v0.1.0.

### Deprecated (Will be removed in v3.0.0)
1. `AgentMessaging.register_handler()`
   - **Replacement:** `register_conversation_handler()` or `register_one_way_handler()`
   - **Reason:** Better type safety and context awareness
   - **Migration Path:** See MIGRATION_GUIDE.md

### New Features (Additive Only)
All new features are additive and optional.
```

### 5.2.4: Quick Start Guide Update

**File:** `docs/quick-start.md`

Add sections for:
- Using new handler types
- Querying messages and sessions
- Using metadata
- Meeting analytics examples

### 5.2.5: Examples

Create new example files:

**`examples/05_message_queries.py`**
```python
"""Example: Querying messages and sessions."""

async def main():
    async with AgentMessaging[dict]() as sdk:
        # Get sent messages
        sent = await sdk.one_way.get_sent_messages(
            sender_external_id="alice",
            include_read=False
        )
        
        # Get conversation history
        history = await sdk.conversation.get_conversation_history(
            agent_a_external_id="alice",
            agent_b_external_id="bob",
            limit=50
        )
        
        # Get session statistics
        stats = await sdk.conversation.get_session_statistics(
            agent_external_id="alice"
        )
```

**`examples/06_handler_types.py`**
```python
"""Example: Using different handler types."""

async def main():
    async with AgentMessaging[dict]() as sdk:
        # Register handlers by context
        @sdk.register_one_way_handler()
        async def handle_notification(msg, ctx):
            print(f"Notification: {msg}")
        
        @sdk.register_conversation_handler()
        async def handle_request(msg, ctx):
            return {"status": "ok"}
        
        @sdk.register_meeting_handler()
        async def handle_meeting(msg, ctx):
            print(f"Meeting message: {msg}")
```

**`examples/07_metadata.py`**
```python
"""Example: Using message metadata."""

async def main():
    async with AgentMessaging[dict]() as sdk:
        # Send with metadata
        await sdk.one_way.send(
            sender_external_id="alice",
            recipient_external_ids=["bob"],
            message={"text": "Important!"},
            metadata={
                "priority": "high",
                "request_id": "req-12345"
            }
        )
        
        # Query by metadata
        urgent = await sdk.one_way.get_received_messages(
            recipient_external_id="bob",
            metadata_filter={"priority": "high"}
        )
```

**`examples/08_meeting_analytics.py`**
```python
"""Example: Meeting analytics."""

async def main():
    async with AgentMessaging[dict]() as sdk:
        # Create and run meeting
        meeting_id = await sdk.meeting.create_meeting(...)
        # ... meeting happens ...
        
        # Get analytics
        participation = await sdk.meeting.get_participation_analysis(meeting_id)
        timeline = await sdk.meeting.get_meeting_timeline(meeting_id)
        turns = await sdk.meeting.get_turn_statistics(meeting_id)
        
        print(f"Most active: {participation['most_active']}")
        print(f"Total turns: {turns['total_turns']}")
```

---

## 5.3: Performance Documentation

**Priority:** HIGH  
**Effort:** 1 day

### Performance Guide

**File:** `docs/technical/performance-guide.md`

```markdown
# Performance Tuning Guide

## Overview
This guide helps you optimize Agent Messaging Protocol for your workload.

## Benchmarks

### Operation Latency (Median)
- `send_and_wait()`: 45ms
- `send_no_wait()`: 5ms
- `one_way.send()`: 3ms
- `meeting.speak()`: 8ms
- Query operations: 10-50ms

### Throughput
- Concurrent conversations: 1000+ ops/sec
- One-way messages: 5000+ msgs/sec
- Database queries: 2000+ queries/sec

## Optimization Strategies

### 1. Connection Pool Sizing
```python
config = Config(
    database=DatabaseConfig(
        max_pool_size=50,  # Increase for high concurrency
        min_pool_size=10,  # Maintain warm connections
    )
)
```

### 2. Batch Operations
```python
# Instead of:
for msg_id in message_ids:
    await mark_as_read(msg_id)

# Use:
await mark_messages_read_batch(message_ids)
```

### 3. Pagination
```python
# Always use pagination for large result sets
messages = await get_messages(limit=100, offset=0)
```

### 4. Indexing
Ensure these indexes exist:
- Messages: (sender_id, created_at), (recipient_id, read_at)
- Sessions: (agent_a_id, status), (agent_b_id, status)
- Metadata: GIN index on JSONB columns

## Monitoring

### Key Metrics to Track
1. Lock acquisition time
2. Handler execution time
3. Database query latency
4. Connection pool utilization
5. Message queue depth

### Alerting Thresholds
- Lock wait time > 5 seconds
- Handler timeout rate > 1%
- Connection pool saturation > 90%
- Query latency > 100ms (p95)
```

---

## Implementation Plan

### Day 1: Unit Tests
- [ ] Write tests for lock mechanisms
- [ ] Write tests for handler routing
- [ ] Write tests for query methods
- [ ] Run tests, fix issues

### Day 2: Integration Tests
- [ ] Write end-to-end scenario tests
- [ ] Write migration tests
- [ ] Run tests, fix issues

### Day 3: Stress Tests & Benchmarks
- [ ] Write load tests
- [ ] Write performance benchmarks
- [ ] Run stress tests
- [ ] Document results

### Day 4: Documentation (Part 1)
- [ ] Update API reference
- [ ] Write migration guide
- [ ] Document breaking changes
- [ ] Update quick start guide

### Day 5: Documentation (Part 2) & Examples
- [ ] Create new examples
- [ ] Write performance guide
- [ ] Final review and polish
- [ ] Generate API docs

---

## Acceptance Criteria

- [ ] Test coverage ≥ 85%
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Stress tests run for 1 hour without failures
- [ ] Performance benchmarks met or exceeded
- [ ] API reference updated
- [ ] Migration guide complete
- [ ] Breaking changes documented
- [ ] 5+ working examples created
- [ ] Performance guide written
- [ ] Code review completed
- [ ] Final QA pass completed

---

**Status:** 📝 Ready for Implementation  
**Depends On:** All Previous Phases Complete  
**Estimated Completion:** Day 25
