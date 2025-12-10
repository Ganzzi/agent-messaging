# Phase 2: Essential Query Methods

**Priority:** 🟡 HIGH  
**Duration:** 4-5 days  
**Depends On:** Phase 1 (Critical Bug Fixes)  
**Risk Level:** LOW (additive changes only)

---

## Overview

This phase adds essential query methods that users need to effectively manage messages, sessions, and meetings. All changes are additive (no breaking changes).

---

## 2.1: One-Way Message Query Methods

**File:** `agent_messaging/messaging/one_way.py`  
**Priority:** HIGH  
**Effort:** 2 days

### Missing Functionality

Currently, `OneWayMessenger` only has `send()`. Users cannot:
- Retrieve messages they sent
- Retrieve messages they received
- Filter by read status
- Get message counts

### New Methods to Implement

#### 2.1.1: Get Messages by Sender

```python
async def get_sent_messages(
    self,
    sender_external_id: str,
    include_read: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get one-way messages sent by an agent.
    
    Args:
        sender_external_id: External ID of sender agent
        include_read: Include messages marked as read (default: True)
        limit: Maximum number of messages to return (default: 100)
        offset: Offset for pagination (default: 0)
    
    Returns:
        List of message dictionaries with:
        - message_id: UUID
        - recipient_id: str (external_id)
        - recipient_name: str
        - content: Dict (deserialized)
        - is_read: bool
        - created_at: datetime
    
    Raises:
        ValueError: If parameters are invalid
        AgentNotFoundError: If sender not found
    """
```

#### 2.1.2: Get Messages by Recipient

```python
async def get_received_messages(
    self,
    recipient_external_id: str,
    include_read: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get one-way messages received by an agent.
    
    Args:
        recipient_external_id: External ID of recipient agent
        include_read: Include messages marked as read (default: True)
        limit: Maximum number of messages to return (default: 100)
        offset: Offset for pagination (default: 0)
    
    Returns:
        List of message dictionaries with:
        - message_id: UUID
        - sender_id: str (external_id)
        - sender_name: str
        - content: Dict (deserialized)
        - is_read: bool
        - created_at: datetime
    
    Raises:
        ValueError: If parameters are invalid
        AgentNotFoundError: If recipient not found
    """
```

#### 2.1.3: Mark Messages as Read

```python
async def mark_messages_read(
    self,
    message_ids: List[UUID],
) -> int:
    """Mark one-way messages as read.
    
    Args:
        message_ids: List of message UUIDs to mark as read
    
    Returns:
        Number of messages actually marked as read
    
    Raises:
        ValueError: If message_ids is empty or invalid
    """
```

#### 2.1.4: Get Message Count

```python
async def get_message_count(
    self,
    agent_external_id: str,
    as_sender: bool = True,
    include_read: bool = True,
) -> int:
    """Get count of one-way messages for an agent.
    
    Args:
        agent_external_id: External ID of agent
        as_sender: Count sent messages (True) or received messages (False)
        include_read: Include read messages in count
    
    Returns:
        Message count
    
    Raises:
        ValueError: If parameters are invalid
        AgentNotFoundError: If agent not found
    """
```

### Repository Changes Required

**File:** `agent_messaging/database/repositories/message.py`

Add new repository methods:

```python
async def get_messages_by_sender(
    self,
    sender_id: UUID,
    include_read: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> List[Message]:
    """Get messages sent by an agent."""
    query = """
        SELECT id, sender_id, recipient_id, session_id, meeting_id,
               message_type, content, read_at, created_at, metadata
        FROM messages
        WHERE sender_id = $1
          AND session_id IS NULL
          AND meeting_id IS NULL
    """
    if not include_read:
        query += " AND read_at IS NULL"
    
    query += " ORDER BY created_at DESC LIMIT $2 OFFSET $3"
    
    # Implementation...
```

Similar methods for:
- `get_messages_by_recipient()`
- `get_message_count()`
- `mark_messages_read_batch(message_ids: List[UUID])`

---

## 2.2: Conversation Query Methods

**File:** `agent_messaging/messaging/conversation.py`  
**Priority:** HIGH  
**Effort:** 2 days

### New Methods to Implement

#### 2.2.1: Get Conversation History

```python
async def get_conversation_history(
    self,
    agent_a_external_id: str,
    agent_b_external_id: str,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get conversation history between two agents.
    
    Returns messages from their session in chronological order.
    
    Args:
        agent_a_external_id: First agent external ID
        agent_b_external_id: Second agent external ID
        limit: Maximum number of messages (default: 100)
        offset: Offset for pagination (default: 0)
    
    Returns:
        List of message dictionaries with:
        - message_id: UUID
        - sender_id: str (external_id)
        - sender_name: str
        - recipient_id: str (external_id)
        - recipient_name: str
        - content: Dict (deserialized)
        - is_read: bool
        - created_at: datetime
    
    Raises:
        ValueError: If parameters invalid
        AgentNotFoundError: If agents not found
    """
```

#### 2.2.2: Get Session Statistics

```python
async def get_session_statistics(
    self,
    agent_external_id: str,
) -> Dict[str, Any]:
    """Get statistics about an agent's conversation sessions.
    
    Args:
        agent_external_id: Agent external ID
    
    Returns:
        Statistics dictionary with:
        - total_sessions: int
        - active_sessions: int
        - ended_sessions: int
        - total_messages_sent: int
        - total_messages_received: int
        - unread_message_count: int
        - most_active_partners: List[Dict] (top 5)
    
    Raises:
        ValueError: If parameters invalid
        AgentNotFoundError: If agent not found
    """
```

#### 2.2.3: Mark Message Read/Unread

```python
async def mark_message_read(
    self,
    message_id: UUID,
    read: bool = True,
) -> None:
    """Mark a specific message as read or unread.
    
    Args:
        message_id: Message UUID
        read: True to mark as read, False to mark as unread
    
    Raises:
        ValueError: If message_id invalid
        MessageNotFoundError: If message doesn't exist
    """
```

#### 2.2.4: Get Session Info

```python
async def get_session_info(
    self,
    session_id: UUID,
) -> Dict[str, Any]:
    """Get detailed information about a session.
    
    Args:
        session_id: Session UUID
    
    Returns:
        Session info dictionary with:
        - session_id: UUID
        - agent_a_id: str (external_id)
        - agent_a_name: str
        - agent_b_id: str (external_id)
        - agent_b_name: str
        - status: str (active/waiting/ended)
        - locked_by: Optional[str] (external_id)
        - message_count: int
        - unread_count: int
        - created_at: datetime
        - updated_at: datetime
        - ended_at: Optional[datetime]
    
    Raises:
        ValueError: If session_id invalid
        SessionNotFoundError: If session doesn't exist
    """
```

### Repository Changes Required

**File:** `agent_messaging/database/repositories/session.py`

Add:
```python
async def get_session_statistics(self, agent_id: UUID) -> Dict[str, Any]:
    """Get statistics for an agent's sessions."""

async def get_session_message_count(self, session_id: UUID) -> int:
    """Count messages in a session."""

async def get_most_active_partners(self, agent_id: UUID, limit: int = 5) -> List[Dict]:
    """Get agents this agent messages most frequently."""
```

**File:** `agent_messaging/database/repositories/message.py`

Add:
```python
async def mark_as_unread(self, message_id: UUID) -> None:
    """Mark message as unread."""

async def get_message_by_id(self, message_id: UUID) -> Optional[Message]:
    """Get single message by ID (already exists but check implementation)."""
```

---

## 2.3: Meeting Query Methods

**File:** `agent_messaging/messaging/meeting.py`  
**Priority:** MEDIUM  
**Effort:** 1-2 days

### New Methods to Implement

#### 2.3.1: Get Meeting Details

```python
async def get_meeting_details(
    self,
    meeting_id: UUID,
) -> Dict[str, Any]:
    """Get detailed information about a meeting.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        Meeting details dictionary with:
        - meeting_id: UUID
        - host_id: str (external_id)
        - host_name: str
        - status: str (created/ready/active/ended)
        - current_speaker: Optional[Dict] (id, name)
        - turn_duration: Optional[float]
        - turn_started_at: Optional[datetime]
        - participants: List[Dict] (id, name, status)
        - message_count: int
        - created_at: datetime
        - started_at: Optional[datetime]
        - ended_at: Optional[datetime]
    
    Raises:
        ValueError: If meeting_id invalid
        MeetingNotFoundError: If meeting doesn't exist
    """
```

#### 2.3.2: Get Participant History

```python
async def get_participant_history(
    self,
    agent_external_id: str,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get meetings an agent has participated in.
    
    Args:
        agent_external_id: Agent external ID
        limit: Maximum number of meetings (default: 10)
        offset: Offset for pagination (default: 0)
    
    Returns:
        List of meeting summary dictionaries
    
    Raises:
        ValueError: If parameters invalid
        AgentNotFoundError: If agent not found
    """
```

#### 2.3.3: Get Meeting Statistics

```python
async def get_meeting_statistics(
    self,
    meeting_id: UUID,
) -> Dict[str, Any]:
    """Get statistics for a meeting.
    
    Args:
        meeting_id: Meeting UUID
    
    Returns:
        Statistics dictionary with:
        - total_messages: int
        - messages_by_participant: Dict[str, int] (external_id -> count)
        - total_turns: int
        - average_turn_duration: float
        - meeting_duration: float (seconds)
        - participation_rate: Dict[str, float] (external_id -> percentage)
    
    Raises:
        ValueError: If meeting_id invalid
        MeetingNotFoundError: If meeting doesn't exist
    """
```

### Repository Changes Required

**File:** `agent_messaging/database/repositories/meeting.py`

Add:
```python
async def get_meeting_message_count(self, meeting_id: UUID) -> int:
    """Count messages in a meeting."""

async def get_meetings_for_agent(
    self,
    agent_id: UUID,
    limit: int = 10,
    offset: int = 0,
) -> List[Meeting]:
    """Get meetings an agent participated in."""

async def get_meeting_statistics(self, meeting_id: UUID) -> Dict[str, Any]:
    """Get statistics for a meeting."""
```

---

## Implementation Plan

### Day 1: One-Way Messages (Part 1)
- [ ] Implement `get_sent_messages()`
- [ ] Implement `get_received_messages()`
- [ ] Add repository methods
- [ ] Write unit tests

### Day 2: One-Way Messages (Part 2)
- [ ] Implement `mark_messages_read()`
- [ ] Implement `get_message_count()`
- [ ] Write integration tests
- [ ] Update documentation

### Day 3: Conversation Queries (Part 1)
- [ ] Implement `get_conversation_history()`
- [ ] Implement `get_session_info()`
- [ ] Add repository methods
- [ ] Write unit tests

### Day 4: Conversation Queries (Part 2)
- [ ] Implement `get_session_statistics()`
- [ ] Implement `mark_message_read()`
- [ ] Write integration tests
- [ ] Update documentation

### Day 5: Meeting Queries
- [ ] Implement all meeting query methods
- [ ] Add repository methods
- [ ] Write tests
- [ ] Update documentation

---

## Testing Requirements

### Unit Tests (Per Method)
- ✅ Valid inputs return correct data
- ✅ Invalid inputs raise appropriate exceptions
- ✅ Agent not found raises AgentNotFoundError
- ✅ Pagination works correctly
- ✅ Filtering (read status) works correctly

### Integration Tests
- ✅ Get messages after sending several
- ✅ Pagination through large result sets
- ✅ Mark read updates database correctly
- ✅ Statistics match actual message counts
- ✅ Concurrent queries don't interfere

### Performance Tests
- ✅ Query 1000 messages completes in <100ms
- ✅ Statistics calculation completes in <200ms
- ✅ Pagination doesn't degrade with offset
- ✅ Proper indexes used (check EXPLAIN ANALYZE)

---

## Database Optimization

### New Indexes Required

```sql
-- For one-way message queries
CREATE INDEX idx_messages_sender_created
ON messages(sender_id, created_at DESC)
WHERE session_id IS NULL AND meeting_id IS NULL;

CREATE INDEX idx_messages_recipient_read_created
ON messages(recipient_id, read_at, created_at DESC)
WHERE session_id IS NULL AND meeting_id IS NULL;

-- For session statistics
CREATE INDEX idx_sessions_agent_status
ON sessions(agent_a_id, status)
UNION
CREATE INDEX idx_sessions_agent_b_status
ON sessions(agent_b_id, status);

-- For meeting statistics
CREATE INDEX idx_messages_meeting_sender
ON messages(meeting_id, sender_id)
WHERE meeting_id IS NOT NULL;
```

---

## Documentation Updates

### API Reference
- Add new methods to `api-reference.md`
- Include examples for each method
- Document pagination behavior
- Document filtering options

### Quick Start Guide
- Add section on querying messages
- Add section on session management
- Add examples for common queries

### Examples
- Create `05_message_queries.py`
- Create `06_session_management.py`
- Create `07_meeting_analytics.py`

---

## Acceptance Criteria

- [ ] All 13 new methods implemented and tested
- [ ] Test coverage ≥ 85% for new code
- [ ] All integration tests pass
- [ ] Performance benchmarks met
- [ ] Database indexes created
- [ ] Documentation updated
- [ ] Examples added
- [ ] Code review approved

---

**Status:** 📝 Ready for Implementation  
**Depends On:** Phase 1 Complete  
**Estimated Completion:** Day 9-10
