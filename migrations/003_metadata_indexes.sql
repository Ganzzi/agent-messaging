-- Phase 4: Advanced Features - Metadata Indexes
-- Created: December 9, 2025
-- Purpose: Add GIN indexes for efficient metadata queries

-- ============================================================================
-- GIN Index for Metadata JSONB Queries
-- ============================================================================

-- This index enables fast queries on message metadata using JSONB operators
-- Supports queries like:
--   - WHERE metadata @> '{"priority": "high"}'
--   - WHERE metadata ? 'request_id'
--   - WHERE metadata->'tags' @> '["urgent"]'

CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin
ON messages USING GIN (metadata jsonb_path_ops);

COMMENT ON INDEX idx_messages_metadata_gin IS 
'GIN index for fast JSONB metadata queries using @>, ?, and other operators';

-- ============================================================================
-- Composite Index for Common Metadata Queries
-- ============================================================================

-- Index for filtering by read status + metadata existence
CREATE INDEX IF NOT EXISTS idx_messages_recipient_read_metadata
ON messages (recipient_id, read_at, created_at DESC)
WHERE metadata IS NOT NULL AND recipient_id IS NOT NULL;

COMMENT ON INDEX idx_messages_recipient_read_metadata IS
'Composite index for recipient messages with metadata filtering';

-- Index for session messages with metadata
CREATE INDEX IF NOT EXISTS idx_messages_session_metadata
ON messages (session_id, created_at ASC)
WHERE metadata IS NOT NULL AND session_id IS NOT NULL;

COMMENT ON INDEX idx_messages_session_metadata IS
'Composite index for session messages with metadata';

-- Index for meeting messages with metadata
CREATE INDEX IF NOT EXISTS idx_messages_meeting_metadata
ON messages (meeting_id, sender_id, created_at ASC)
WHERE metadata IS NOT NULL AND meeting_id IS NOT NULL;

COMMENT ON INDEX idx_messages_meeting_metadata IS
'Composite index for meeting messages with metadata';

-- ============================================================================
-- Statistics Update
-- ============================================================================

-- Analyze the messages table to update query planner statistics
ANALYZE messages;
