# Agent Messaging Protocol - Database Schema

## Overview

This document defines the complete PostgreSQL database schema for the Agent Messaging Protocol. The schema supports organizations, agents, messages, conversation sessions, and multi-agent meetings.

---

## Schema Diagram

```
organizations
├── id (UUID, PK)
├── external_id (VARCHAR, UNIQUE)
└── name (VARCHAR)

agents
├── id (UUID, PK)
├── external_id (VARCHAR, UNIQUE)
├── organization_id (UUID, FK → organizations.id)
└── name (VARCHAR)

messages
├── id (UUID, PK)
├── sender_id (UUID, FK → agents.id)
├── recipient_id (UUID, FK → agents.id, NULLABLE)
├── session_id (UUID, FK → sessions.id, NULLABLE)
├── meeting_id (UUID, FK → meetings.id, NULLABLE)
├── message_type (VARCHAR)
├── content (JSONB)
├── read_at (TIMESTAMP, NULLABLE)
├── created_at (TIMESTAMP)
└── metadata (JSONB)

sessions
├── id (UUID, PK)
├── agent_a_id (UUID, FK → agents.id)
├── agent_b_id (UUID, FK → agents.id)
├── session_type (VARCHAR: 'sync' | 'async')
├── status (VARCHAR: 'active' | 'waiting' | 'ended')
├── locked_agent_id (UUID, FK → agents.id, NULLABLE)
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
└── ended_at (TIMESTAMP, NULLABLE)

meetings
├── id (UUID, PK)
├── host_id (UUID, FK → agents.id)
├── status (VARCHAR: 'created' | 'ready' | 'active' | 'ended')
├── current_speaker_id (UUID, FK → agents.id, NULLABLE)
├── turn_duration (INTERVAL, NULLABLE)
├── turn_started_at (TIMESTAMP, NULLABLE)
├── created_at (TIMESTAMP)
├── started_at (TIMESTAMP, NULLABLE)
└── ended_at (TIMESTAMP, NULLABLE)

meeting_participants
├── id (UUID, PK)
├── meeting_id (UUID, FK → meetings.id)
├── agent_id (UUID, FK → agents.id)
├── status (VARCHAR: 'invited' | 'attending' | 'waiting' | 'speaking' | 'left')
├── join_order (INTEGER)
├── is_locked (BOOLEAN)
├── joined_at (TIMESTAMP)
└── left_at (TIMESTAMP, NULLABLE)

meeting_events
├── id (UUID, PK)
├── meeting_id (UUID, FK → meetings.id)
├── event_type (VARCHAR)
├── agent_id (UUID, FK → agents.id, NULLABLE)
├── data (JSONB)
└── created_at (TIMESTAMP)
```

---

## Complete SQL Schema

```sql
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- Organizations Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_external_id ON organizations(external_id);

-- ============================================================================
-- Agents Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) UNIQUE NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agents_external_id ON agents(external_id);
CREATE INDEX idx_agents_organization_id ON agents(organization_id);

-- ============================================================================
-- Sessions Table (for one-to-one conversations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_a_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_b_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    session_type VARCHAR(20) NOT NULL CHECK (session_type IN ('sync', 'async')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'waiting', 'ended')),
    locked_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    
    -- Ensure agent_a_id is always less than agent_b_id for consistency
    CONSTRAINT sessions_agent_order CHECK (agent_a_id < agent_b_id),
    
    -- Unique constraint: one active session per agent pair per type
    CONSTRAINT sessions_unique_active_pair UNIQUE (agent_a_id, agent_b_id, session_type)
);

CREATE INDEX idx_sessions_agent_a ON sessions(agent_a_id);
CREATE INDEX idx_sessions_agent_b ON sessions(agent_b_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_locked_agent ON sessions(locked_agent_id) WHERE locked_agent_id IS NOT NULL;

-- ============================================================================
-- Meetings Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'ready', 'active', 'ended')),
    current_speaker_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    turn_duration INTERVAL,  -- Optional time limit per turn
    turn_started_at TIMESTAMP WITH TIME ZONE,  -- When current turn started
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_meetings_host ON meetings(host_id);
CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_meetings_current_speaker ON meetings(current_speaker_id) WHERE current_speaker_id IS NOT NULL;

-- ============================================================================
-- Meeting Participants Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'attending', 'waiting', 'speaking', 'left')),
    join_order INTEGER NOT NULL,  -- Order in which agent joined (for round-robin)
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    
    -- Unique constraint: one participant record per agent per meeting
    CONSTRAINT meeting_participants_unique_agent UNIQUE (meeting_id, agent_id)
);

CREATE INDEX idx_meeting_participants_meeting ON meeting_participants(meeting_id);
CREATE INDEX idx_meeting_participants_agent ON meeting_participants(agent_id);
CREATE INDEX idx_meeting_participants_status ON meeting_participants(meeting_id, status);
CREATE INDEX idx_meeting_participants_join_order ON meeting_participants(meeting_id, join_order);

-- ============================================================================
-- Messages Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES agents(id) ON DELETE CASCADE,  -- NULL for meeting messages
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,  -- NULL for one-way or meeting messages
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,  -- NULL for one-to-one messages
    message_type VARCHAR(50) NOT NULL,  -- e.g., 'user_defined', 'system', 'timeout', 'ending'
    content JSONB NOT NULL,  -- User-defined message content
    read_at TIMESTAMP WITH TIME ZONE,  -- When message was read (for async conversations)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,  -- Additional metadata (e.g., timeout info, system message details)
    
    -- Either recipient_id OR meeting_id must be set, not both
    CONSTRAINT messages_recipient_or_meeting CHECK (
        (recipient_id IS NOT NULL AND meeting_id IS NULL) OR
        (recipient_id IS NULL AND meeting_id IS NOT NULL)
    )
);

CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_messages_recipient ON messages(recipient_id) WHERE recipient_id IS NOT NULL;
CREATE INDEX idx_messages_session ON messages(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_messages_meeting ON messages(meeting_id) WHERE meeting_id IS NOT NULL;
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_unread ON messages(recipient_id, read_at) WHERE read_at IS NULL;

-- ============================================================================
-- Meeting Events Table (for event logging and history)
-- ============================================================================
CREATE TABLE IF NOT EXISTS meeting_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- 'agent_joined', 'agent_spoke', 'agent_left', 'agent_timed_out', 'meeting_started', 'meeting_ended'
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,  -- NULL for meeting-level events
    data JSONB,  -- Event-specific data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_meeting_events_meeting ON meeting_events(meeting_id);
CREATE INDEX idx_meeting_events_type ON meeting_events(meeting_id, event_type);
CREATE INDEX idx_meeting_events_created_at ON meeting_events(meeting_id, created_at);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to ensure agent ordering in sessions
CREATE OR REPLACE FUNCTION ensure_session_agent_order()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.agent_a_id > NEW.agent_b_id THEN
        -- Swap agents to maintain order
        DECLARE
            temp_id UUID;
        BEGIN
            temp_id := NEW.agent_a_id;
            NEW.agent_a_id := NEW.agent_b_id;
            NEW.agent_b_id := temp_id;
        END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sessions_ensure_order BEFORE INSERT OR UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION ensure_session_agent_order();

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View: Active Conversations
CREATE OR REPLACE VIEW active_conversations AS
SELECT 
    s.id AS session_id,
    s.session_type,
    s.status,
    s.locked_agent_id,
    a1.external_id AS agent_a_external_id,
    a1.name AS agent_a_name,
    a2.external_id AS agent_b_external_id,
    a2.name AS agent_b_name,
    s.created_at,
    s.updated_at
FROM sessions s
JOIN agents a1 ON s.agent_a_id = a1.id
JOIN agents a2 ON s.agent_b_id = a2.id
WHERE s.status != 'ended';

-- View: Active Meetings
CREATE OR REPLACE VIEW active_meetings AS
SELECT 
    m.id AS meeting_id,
    m.status,
    h.external_id AS host_external_id,
    h.name AS host_name,
    cs.external_id AS current_speaker_external_id,
    cs.name AS current_speaker_name,
    m.turn_duration,
    m.turn_started_at,
    m.created_at,
    m.started_at,
    COUNT(DISTINCT mp.agent_id) AS participant_count
FROM meetings m
JOIN agents h ON m.host_id = h.id
LEFT JOIN agents cs ON m.current_speaker_id = cs.id
LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id AND mp.status != 'left'
WHERE m.status != 'ended'
GROUP BY m.id, h.external_id, h.name, cs.external_id, cs.name;

-- View: Unread Messages per Agent
CREATE OR REPLACE VIEW agent_unread_messages AS
SELECT 
    a.id AS agent_id,
    a.external_id AS agent_external_id,
    a.name AS agent_name,
    COUNT(m.id) AS unread_count,
    MAX(m.created_at) AS latest_message_at
FROM agents a
LEFT JOIN messages m ON a.id = m.recipient_id AND m.read_at IS NULL
GROUP BY a.id, a.external_id, a.name;
```

---

## Key Design Decisions

### 1. Agent Ordering in Sessions

The `sessions` table enforces that `agent_a_id < agent_b_id` to ensure consistency:
- Prevents duplicate sessions (A-B vs B-A)
- Simplifies queries for finding sessions
- Automatic via trigger

### 2. Message Recipient Flexibility

Messages can have either:
- `recipient_id` (one-to-one messages)
- `meeting_id` (meeting messages)

Constraint ensures exactly one is set.

### 3. Meeting Participant States

Participants progress through states:
- `invited` → `attending` → `waiting` → `speaking` → `left`

The `is_locked` flag coordinates turn-taking.

### 4. JSONB for Message Content

Using JSONB allows:
- User-defined message structures
- No schema changes for new message types
- Efficient querying of message properties
- Flexible metadata storage

### 5. Advisory Locks

Not stored in schema, but used at runtime:
- Agent locks: `pg_advisory_lock(hash(agent_external_id))`
- Session locks: `pg_advisory_lock(hash(session_id))`
- Meeting locks: `pg_advisory_lock(hash(meeting_id))`

---

## Indexes Rationale

### Performance-Critical Indexes

1. **external_id indexes:** Fast agent/org lookup from external systems
2. **Unread messages index:** Quick unread message queries
3. **Session status index:** Find active/waiting sessions
4. **Meeting participant join_order:** Round-robin speaker selection
5. **Message created_at:** Chronological history retrieval

### Partial Indexes

- `locked_agent_id IS NOT NULL` - Only index locked sessions
- `read_at IS NULL` - Only index unread messages
- `current_speaker_id IS NOT NULL` - Only index active speakers

---

## Constraints & Data Integrity

### Foreign Key Cascades

- `ON DELETE CASCADE` for dependent records
- `ON DELETE SET NULL` for optional references
- Ensures referential integrity

### Check Constraints

- Valid enum values for status fields
- Agent ordering in sessions
- Recipient XOR meeting constraint

### Unique Constraints

- External IDs (organization/agent)
- Active session per agent pair
- One participant per agent per meeting

---

## Sample Queries

### Find or Create Session

```sql
-- Find existing session
SELECT id, status, locked_agent_id
FROM sessions
WHERE session_type = 'sync'
  AND ((agent_a_id = $1 AND agent_b_id = $2) OR (agent_a_id = $2 AND agent_b_id = $1))
  AND status != 'ended'
LIMIT 1;

-- Create new session (with automatic ordering)
INSERT INTO sessions (agent_a_id, agent_b_id, session_type)
VALUES ($1, $2, 'sync')
RETURNING id, agent_a_id, agent_b_id;
```

### Get Unread Messages for Agent

```sql
SELECT 
    m.id,
    m.content,
    m.message_type,
    s.external_id AS sender_external_id,
    s.name AS sender_name,
    m.created_at
FROM messages m
JOIN agents s ON m.sender_id = s.id
WHERE m.recipient_id = (SELECT id FROM agents WHERE external_id = $1)
  AND m.read_at IS NULL
ORDER BY m.created_at ASC;
```

### Get Next Speaker in Meeting (Round-Robin)

```sql
-- Get current speaker's join_order
SELECT join_order
FROM meeting_participants
WHERE meeting_id = $1 AND agent_id = $2;

-- Get next speaker (wrapping around)
SELECT agent_id
FROM meeting_participants
WHERE meeting_id = $1
  AND status NOT IN ('left')
  AND join_order > $3  -- current speaker's join_order
ORDER BY join_order ASC
LIMIT 1;

-- If no next speaker, get first speaker (wrap around)
SELECT agent_id
FROM meeting_participants
WHERE meeting_id = $1
  AND status NOT IN ('left')
ORDER BY join_order ASC
LIMIT 1;
```

### Get Meeting History

```sql
SELECT 
    m.id AS message_id,
    m.created_at,
    m.message_type,
    m.content,
    m.metadata,
    s.external_id AS sender_external_id,
    s.name AS sender_name
FROM messages m
JOIN agents s ON m.sender_id = s.id
WHERE m.meeting_id = $1
ORDER BY m.created_at ASC;
```

### Check if Agent is Locked

```sql
-- For conversation
SELECT locked_agent_id = $1 AS is_locked
FROM sessions
WHERE id = $2;

-- For meeting
SELECT is_locked
FROM meeting_participants
WHERE meeting_id = $1 AND agent_id = $2;
```

---

## Migration Strategy

### Version 1.0.0 (Initial Schema)

File: `migrations/001_initial_schema.sql`

Contains all tables, indexes, triggers, and views defined above.

### Future Migrations

Example structure:
- `002_add_message_priority.sql` - Add priority field
- `003_add_agent_metadata.sql` - Add metadata column to agents
- `004_add_message_attachments.sql` - Support file attachments

Each migration:
1. Numbered sequentially
2. Idempotent (can run multiple times safely)
3. Includes rollback script
4. Documented with purpose

---

## Performance Tuning

### Recommended PostgreSQL Settings

```ini
# Connection pooling
max_connections = 100

# Shared buffers (25% of RAM)
shared_buffers = 2GB

# Work memory (for sorting/hashing)
work_mem = 16MB

# Maintenance work memory
maintenance_work_mem = 256MB

# WAL settings
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Query planner
random_page_cost = 1.1  # For SSD storage
effective_cache_size = 6GB
```

### Monitoring Queries

```sql
-- Find slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY idx_tup_read DESC;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Data Retention & Cleanup

### Retention Policies

Consider implementing:
- Archive old messages after 90 days
- Delete ended sessions after 30 days
- Soft delete agents (add `deleted_at` column)

### Cleanup Queries

```sql
-- Archive old messages
INSERT INTO messages_archive
SELECT * FROM messages
WHERE created_at < NOW() - INTERVAL '90 days';

DELETE FROM messages
WHERE created_at < NOW() - INTERVAL '90 days';

-- Clean up ended sessions
DELETE FROM sessions
WHERE status = 'ended'
  AND ended_at < NOW() - INTERVAL '30 days';

-- Clean up ended meetings
DELETE FROM meetings
WHERE status = 'ended'
  AND ended_at < NOW() - INTERVAL '30 days';
```

---

## Testing Data

### Sample Data Script

```sql
-- Insert test organization
INSERT INTO organizations (external_id, name)
VALUES ('org_001', 'Test Organization');

-- Insert test agents
INSERT INTO agents (external_id, organization_id, name)
VALUES 
    ('agent_alice', (SELECT id FROM organizations WHERE external_id = 'org_001'), 'Alice'),
    ('agent_bob', (SELECT id FROM organizations WHERE external_id = 'org_001'), 'Bob'),
    ('agent_charlie', (SELECT id FROM organizations WHERE external_id = 'org_001'), 'Charlie');

-- Create a test session
INSERT INTO sessions (agent_a_id, agent_b_id, session_type)
SELECT a1.id, a2.id, 'sync'
FROM agents a1, agents a2
WHERE a1.external_id = 'agent_alice'
  AND a2.external_id = 'agent_bob';

-- Add test messages
INSERT INTO messages (sender_id, recipient_id, session_id, message_type, content)
SELECT 
    (SELECT id FROM agents WHERE external_id = 'agent_alice'),
    (SELECT id FROM agents WHERE external_id = 'agent_bob'),
    s.id,
    'user_defined',
    '{"text": "Hello Bob!"}'::jsonb
FROM sessions s
WHERE s.agent_a_id = (SELECT id FROM agents WHERE external_id = 'agent_alice');
```

---

## Summary

This schema provides:
- ✓ Flexible message storage (JSONB)
- ✓ Support for all four conversation types
- ✓ Efficient querying with indexes
- ✓ Data integrity with constraints
- ✓ Scalability considerations
- ✓ Performance monitoring capabilities
- ✓ Clear migration path

Next steps:
1. Review and approve schema
2. Create initial migration file
3. Set up test database
4. Begin repository implementation
