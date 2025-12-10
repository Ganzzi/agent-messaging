-- Phase 4.4: Full-Text Search Support
-- Migration 004
-- Created: 2025-12-10
-- Description: Adds GIN indexes for full-text search on message content

-- ============================================================================
-- Full-Text Search Indexes
-- ============================================================================

-- 1. GIN index for full-text search on message content
-- Uses to_tsvector with English language configuration
-- Speeds up @@ (full-text search) queries significantly
CREATE INDEX IF NOT EXISTS idx_messages_content_fts
ON messages
USING GIN (to_tsvector('english', content::text));

-- 2. Composite GIN index for filtered full-text searches
-- Combines full-text vector with sender_id for efficient filtered searches
-- Example: Search messages from a specific sender
CREATE INDEX IF NOT EXISTS idx_messages_sender_content_fts
ON messages (sender_id)
INCLUDE (created_at)
WHERE content IS NOT NULL;

-- 3. Composite GIN index for session-based searches
-- Enables efficient full-text search within a specific session
CREATE INDEX IF NOT EXISTS idx_messages_session_content_fts
ON messages (session_id)
INCLUDE (created_at)
WHERE session_id IS NOT NULL AND content IS NOT NULL;

-- 4. Composite GIN index for meeting-based searches
-- Enables efficient full-text search within a specific meeting
CREATE INDEX IF NOT EXISTS idx_messages_meeting_content_fts
ON messages (meeting_id)
INCLUDE (created_at)
WHERE meeting_id IS NOT NULL AND content IS NOT NULL;

-- ============================================================================
-- Performance Notes
-- ============================================================================
-- 
-- GIN indexes are ideal for full-text search because:
-- - They index all unique words (lexemes) in the text
-- - Fast lookup for complex queries with multiple terms
-- - Support operators: & (AND), | (OR), ! (NOT), <-> (phrase)
-- 
-- Index usage patterns:
-- - idx_messages_content_fts: General text search across all messages
-- - idx_messages_sender_content_fts: Search within sender's messages
-- - idx_messages_session_content_fts: Search within conversation
-- - idx_messages_meeting_content_fts: Search within meeting
-- 
-- Query example using index:
--   SELECT * FROM messages
--   WHERE to_tsvector('english', content::text) @@ websearch_to_tsquery('english', 'database postgres')
--   ORDER BY ts_rank(to_tsvector('english', content::text), websearch_to_tsquery('english', 'database postgres')) DESC;
-- 
-- websearch_to_tsquery provides user-friendly query syntax:
-- - "database postgres" → database & postgres (AND)
-- - "database OR postgres" → database | postgres (OR)
-- - "database -mysql" → database & !mysql (NOT)
-- - '"full text search"' → 'full' <-> 'text' <-> 'search' (phrase)
