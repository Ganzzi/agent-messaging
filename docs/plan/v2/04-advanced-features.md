# Phase 4: Advanced Features

**Priority:** 🟢 MEDIUM  
**Duration:** 4-5 days  
**Depends On:** Phase 2 (Query Methods), Phase 3 (Handler Refactor)  
**Risk Level:** LOW (additive features)

---

## Overview

This phase adds advanced features that enhance the SDK's capabilities for production use, including message metadata, advanced filtering, and analytics.

---

## 4.1: Message Metadata System

**Priority:** MEDIUM  
**Effort:** 2 days

### Feature Description

Allow users to attach custom metadata to messages for tracking, categorization, and filtering.

### Use Cases

1. **Request Tracing** - Track request IDs across microservices
2. **Message Tagging** - Categorize messages (urgent, low-priority, etc.)
3. **Custom Properties** - Store application-specific data
4. **Audit Trail** - Track message source, transformations, etc.

### API Design

#### Add Metadata to Messages

```python
# One-way messages
await sdk.one_way.send(
    sender_external_id="alice",
    recipient_external_ids=["bob"],
    message=NotificationMessage(text="Hello"),
    metadata={
        "priority": "high",
        "request_id": "req-12345",
        "source": "web_app",
        "tags": ["urgent", "customer-facing"]
    }
)

# Conversation messages
response = await sdk.conversation.send_and_wait(
    sender_external_id="alice",
    recipient_external_id="bob",
    message=QueryMessage(query="status?"),
    metadata={
        "timeout": 60,
        "retry_count": 0,
        "correlation_id": "corr-67890"
    }
)

# Meeting messages
await sdk.meeting.speak(
    agent_external_id="alice",
    meeting_id=meeting_id,
    message=IdeaMessage(text="My idea..."),
    metadata={
        "speaker_role": "designer",
        "idea_category": "UI/UX"
    }
)
```

#### Query by Metadata

```python
# Get messages with specific metadata
messages = await sdk.one_way.get_received_messages(
    recipient_external_id="bob",
    metadata_filter={
        "priority": "high",
        "tags__contains": "urgent"  # Special operator for array contains
    }
)

# Get conversation messages with metadata
messages = await sdk.conversation.get_messages_in_session(
    session_id=session_id,
    metadata_filter={
        "request_id": "req-12345"
    }
)
```

### Implementation

#### Update Method Signatures

```python
class OneWayMessenger(Generic[T]):
    async def send(
        self,
        sender_external_id: str,
        recipient_external_ids: List[str],
        message: T,
        metadata: Optional[Dict[str, Any]] = None,  # NEW
    ) -> List[str]:
        # ...

class Conversation(Generic[T]):
    async def send_and_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T,
        timeout: float = 30.0,
        metadata: Optional[Dict[str, Any]] = None,  # NEW
    ) -> T:
        # ...
    
    async def send_no_wait(
        self,
        sender_external_id: str,
        recipient_external_id: str,
        message: T,
        metadata: Optional[Dict[str, Any]] = None,  # NEW
    ) -> None:
        # ...

class MeetingManager(Generic[T]):
    async def speak(
        self,
        agent_external_id: str,
        meeting_id: UUID,
        message: T,
        metadata: Optional[Dict[str, Any]] = None,  # NEW
    ) -> UUID:
        # ...
```

#### Repository Updates

```python
class MessageRepository(BaseRepository):
    async def get_messages_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Query messages by metadata."""
        # Build JSONB query
        query = """
            SELECT id, sender_id, recipient_id, session_id, meeting_id,
                   message_type, content, read_at, created_at, metadata
            FROM messages
            WHERE 1=1
        """
        
        params = []
        param_idx = 1
        
        for key, value in metadata_filter.items():
            if "__contains" in key:
                # Array contains operator
                actual_key = key.replace("__contains", "")
                query += f" AND metadata->'{actual_key}' @> ${param_idx}"
                params.append([value])  # Wrap in array for @> operator
            else:
                # Exact match
                query += f" AND metadata->>'{key}' = ${param_idx}"
                params.append(str(value))
            param_idx += 1
        
        query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx+1}"
        params.extend([limit, offset])
        
        results = await self._fetch_all(query, params)
        return [self._message_from_db(result) for result in results]
```

#### Database Index

```sql
-- GIN index for fast JSONB queries
CREATE INDEX idx_messages_metadata_gin
ON messages USING GIN (metadata);
```

---

## 4.2: Advanced Message Filtering

**Priority:** MEDIUM  
**Effort:** 1 day

### Date Range Filtering

```python
# Get messages from last 7 days
from datetime import datetime, timedelta

messages = await sdk.one_way.get_received_messages(
    recipient_external_id="bob",
    date_from=datetime.now() - timedelta(days=7),
    date_to=datetime.now()
)

# Get conversation history for last month
messages = await sdk.conversation.get_conversation_history(
    agent_a_external_id="alice",
    agent_b_external_id="bob",
    date_from=datetime.now() - timedelta(days=30)
)
```

### Message Type Filtering

```python
# Get only system messages
messages = await sdk.conversation.get_messages_in_session(
    session_id=session_id,
    message_types=[MessageType.SYSTEM, MessageType.TIMEOUT]
)

# Get only user messages
messages = await sdk.conversation.get_messages_in_session(
    session_id=session_id,
    message_types=[MessageType.USER_DEFINED]
)
```

### Combined Filtering

```python
# Complex query: unread messages from last 24h with priority=high
messages = await sdk.one_way.get_received_messages(
    recipient_external_id="bob",
    include_read=False,
    date_from=datetime.now() - timedelta(hours=24),
    metadata_filter={"priority": "high"},
    limit=50
)
```

### Implementation

Update all query methods to accept:
- `date_from: Optional[datetime]`
- `date_to: Optional[datetime]`
- `message_types: Optional[List[MessageType]]`
- `metadata_filter: Optional[Dict[str, Any]]`

---

## 4.3: Meeting Analytics

**Priority:** MEDIUM  
**Effort:** 1-2 days

### Analytics Methods

#### 4.3.1: Participation Analysis

```python
async def get_participation_analysis(
    self,
    meeting_id: UUID,
) -> Dict[str, Any]:
    """Analyze participation patterns in a meeting.
    
    Returns:
        {
            "total_participants": int,
            "active_participants": int,  # Actually spoke
            "inactive_participants": int,  # Never spoke
            "participation_rate": float,  # Percentage who spoke
            "by_participant": {
                "alice": {
                    "message_count": int,
                    "word_count": int,
                    "average_turn_duration": float,
                    "speaking_time_percentage": float,
                    "first_message_at": datetime,
                    "last_message_at": datetime
                },
                # ... other participants
            },
            "most_active": str,  # external_id
            "least_active": str,  # external_id (among active)
        }
    """
```

#### 4.3.2: Timeline Analysis

```python
async def get_meeting_timeline(
    self,
    meeting_id: UUID,
) -> Dict[str, Any]:
    """Get meeting timeline with key events.
    
    Returns:
        {
            "meeting_id": UUID,
            "created_at": datetime,
            "started_at": datetime,
            "ended_at": datetime,
            "total_duration": float,  # seconds
            "active_duration": float,  # time spent speaking
            "idle_duration": float,  # time between messages
            "timeline": [
                {
                    "timestamp": datetime,
                    "event_type": str,  # "started", "turn_changed", "message", "ended"
                    "agent": str,  # external_id
                    "details": dict
                },
                # ... chronological events
            ]
        }
    """
```

#### 4.3.3: Turn Statistics

```python
async def get_turn_statistics(
    self,
    meeting_id: UUID,
) -> Dict[str, Any]:
    """Analyze turn-taking patterns.
    
    Returns:
        {
            "total_turns": int,
            "average_turn_duration": float,
            "min_turn_duration": float,
            "max_turn_duration": float,
            "turns_per_participant": Dict[str, int],
            "average_messages_per_turn": float,
            "turn_transitions": [
                {"from": "alice", "to": "bob", "count": 3},
                # ... transition patterns
            ],
            "speaking_order": List[str],  # Order of speakers
        }
    """
```

---

## 4.4: Message Search

**Priority:** LOW-MEDIUM  
**Effort:** 1 day

### Full-Text Search

```python
# Search messages by content
results = await sdk.search_messages(
    agent_external_id="bob",
    search_query="password reset",
    limit=20
)

# Returns:
[
    {
        "message_id": UUID,
        "relevance_score": float,  # 0-1
        "message": Dict,
        "context": str,  # Snippet with search term highlighted
        "matched_fields": List[str]  # Which fields matched
    },
    # ... ranked by relevance
]
```

### Implementation

Requires PostgreSQL full-text search:

```sql
-- Add tsvector column
ALTER TABLE messages
ADD COLUMN content_search tsvector
GENERATED ALWAYS AS (to_tsvector('english', content::text)) STORED;

-- Create GIN index
CREATE INDEX idx_messages_content_search
ON messages USING GIN (content_search);

-- Search query
SELECT id, sender_id, content,
       ts_rank(content_search, to_tsquery('english', $1)) as rank
FROM messages
WHERE content_search @@ to_tsquery('english', $1)
  AND (recipient_id = $2 OR sender_id = $2)
ORDER BY rank DESC
LIMIT $3;
```

---

## 4.5: Performance Optimizations

**Priority:** MEDIUM  
**Effort:** 1 day

### Batch Operations

```python
# Mark multiple messages as read in one query
await sdk.conversation.mark_messages_read_batch(
    message_ids=[uuid1, uuid2, uuid3, ...]
)

# Get multiple sessions in one query
sessions = await sdk.conversation.get_sessions_batch(
    session_ids=[uuid1, uuid2, uuid3]
)
```

### Query Result Caching

```python
# Cache frequently accessed data
class MessageRepository(BaseRepository):
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self._cache = TTLCache(maxsize=1000, ttl=60)  # 60 second TTL
    
    async def get_by_id(self, message_id: UUID) -> Optional[Message]:
        # Check cache first
        if message_id in self._cache:
            return self._cache[message_id]
        
        # Query database
        message = await self._fetch_message(message_id)
        
        # Cache result
        if message:
            self._cache[message_id] = message
        
        return message
```

### Connection Pool Tuning

```python
# Optimize pool settings based on workload
config = Config(
    database=DatabaseConfig(
        # ... connection details ...
        max_pool_size=50,  # Increase for high concurrency
        min_pool_size=10,  # Keep warm connections
        max_idle_time=300,  # Close idle connections after 5 min
        statement_cache_size=100,  # Cache prepared statements
    )
)
```

---

## Implementation Plan

### Day 1: Message Metadata
- [ ] Update method signatures to accept metadata
- [ ] Update repository to store/query metadata
- [ ] Add JSONB indexes
- [ ] Write tests

### Day 2: Advanced Filtering
- [ ] Add date range filtering to all query methods
- [ ] Add message type filtering
- [ ] Add combined filter support
- [ ] Write tests

### Day 3: Meeting Analytics (Part 1)
- [ ] Implement participation analysis
- [ ] Implement timeline analysis
- [ ] Write tests

### Day 4: Meeting Analytics (Part 2) + Search
- [ ] Implement turn statistics
- [ ] Add full-text search capability
- [ ] Write tests

### Day 5: Performance Optimizations
- [ ] Implement batch operations
- [ ] Add caching layer
- [ ] Optimize connection pooling
- [ ] Performance benchmarks

---

## Testing Requirements

### Unit Tests
- ✅ Metadata storage and retrieval
- ✅ JSONB query operators
- ✅ Date range filtering
- ✅ Analytics calculations
- ✅ Search ranking

### Integration Tests
- ✅ End-to-end metadata flow
- ✅ Complex combined filters
- ✅ Analytics accuracy
- ✅ Search relevance

### Performance Tests
- ✅ Metadata query performance (<50ms)
- ✅ Search performance (<100ms for 10k messages)
- ✅ Analytics calculation time (<200ms)
- ✅ Cache hit rate (>80% for hot data)

---

## Acceptance Criteria

- [ ] Message metadata system working
- [ ] Advanced filtering functional
- [ ] Meeting analytics provide useful insights
- [ ] Full-text search working
- [ ] Performance optimizations implemented
- [ ] Test coverage ≥ 80%
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Examples added

---

**Status:** 📝 Ready for Implementation  
**Depends On:** Phase 2, Phase 3 Complete  
**Estimated Completion:** Day 20
