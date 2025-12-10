-- Phase 2: Query Optimization Indexes
-- Improves performance for message queries and session statistics

-- Index for querying sent messages by sender with creation time
CREATE INDEX IF NOT EXISTS idx_messages_sender_created
ON messages(sender_id, created_at DESC);

-- Index for querying received messages by recipient with read status and creation time
CREATE INDEX IF NOT EXISTS idx_messages_recipient_read_created
ON messages(recipient_id, read_at, created_at DESC);

-- Index for session queries by agent with status
CREATE INDEX IF NOT EXISTS idx_sessions_agent_status
ON sessions(agent_a_id, status)
WHERE agent_a_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_agent_b_status
ON sessions(agent_b_id, status)
WHERE agent_b_id IS NOT NULL;

-- Index for meeting message queries with sender
CREATE INDEX IF NOT EXISTS idx_messages_meeting_sender
ON messages(meeting_id, sender_id)
WHERE meeting_id IS NOT NULL;

-- Index for conversation history ordering
CREATE INDEX IF NOT EXISTS idx_messages_session_created
ON messages(session_id, created_at ASC)
WHERE session_id IS NOT NULL;

-- Index for participant history ordering
CREATE INDEX IF NOT EXISTS idx_participants_meeting_join_order
ON meeting_participants(meeting_id, join_order);

-- Index for quick participant status lookups
CREATE INDEX IF NOT EXISTS idx_participants_agent_status
ON meeting_participants(agent_id, status);
