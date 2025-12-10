-- Phase 4.5: Performance Optimizations
-- Migration 005
-- Created: 2025-12-10
-- Description: Additional performance indexes for common query patterns

-- ============================================================================
-- Compound Indexes for Common Query Patterns
-- ============================================================================

-- 1. Messages by sender with type and date filtering
-- Supports: get_sent_messages with message_type and date filters
CREATE INDEX IF NOT EXISTS idx_messages_sender_type_created
ON messages (sender_id, message_type, created_at DESC)
WHERE sender_id IS NOT NULL;

COMMENT ON INDEX idx_messages_sender_type_created IS
'Optimizes filtered sent message queries with type and date';

-- 2. Messages by recipient with read status, type, and date
-- Supports: get_received_messages with all filters
CREATE INDEX IF NOT EXISTS idx_messages_recipient_type_read_created
ON messages (recipient_id, message_type, read_at, created_at DESC)
WHERE recipient_id IS NOT NULL;

COMMENT ON INDEX idx_messages_recipient_type_read_created IS
'Optimizes filtered received message queries';

-- 3. Session messages with type filtering
-- Supports: get_messages_for_session with message_type filter
CREATE INDEX IF NOT EXISTS idx_messages_session_type_created
ON messages (session_id, message_type, created_at ASC)
WHERE session_id IS NOT NULL;

COMMENT ON INDEX idx_messages_session_type_created IS
'Optimizes session message queries with type filtering';

-- 4. Meeting messages with type filtering
-- Supports: get_messages_for_meeting with message_type filter
CREATE INDEX IF NOT EXISTS idx_messages_meeting_type_created
ON messages (meeting_id, message_type, created_at ASC)
WHERE meeting_id IS NOT NULL;

COMMENT ON INDEX idx_messages_meeting_type_created IS
'Optimizes meeting message queries with type filtering';

-- ============================================================================
-- Partial Indexes for Active Entities
-- ============================================================================

-- 5. Active sessions only (in_progress status)
-- Much smaller index, faster queries for active sessions
CREATE INDEX IF NOT EXISTS idx_sessions_active
ON sessions (agent_a_id, agent_b_id, created_at DESC)
WHERE status = 'in_progress';

COMMENT ON INDEX idx_sessions_active IS
'Optimizes queries for active (in_progress) sessions only';

-- 6. Active meetings only (in_progress status)
-- Faster lookups for ongoing meetings
CREATE INDEX IF NOT EXISTS idx_meetings_active
ON meetings (host_id, created_at DESC)
WHERE status = 'in_progress';

COMMENT ON INDEX idx_meetings_active IS
'Optimizes queries for active (in_progress) meetings only';

-- 7. Attending meeting participants
-- Faster queries for who is currently in a meeting
CREATE INDEX IF NOT EXISTS idx_participants_attending
ON meeting_participants (meeting_id, agent_id, join_order)
WHERE status = 'attending';

COMMENT ON INDEX idx_participants_attending IS
'Optimizes queries for currently attending participants';

-- 8. Unread messages only
-- Much smaller index for finding unread messages
CREATE INDEX IF NOT EXISTS idx_messages_unread
ON messages (recipient_id, created_at DESC)
WHERE read_at IS NULL AND recipient_id IS NOT NULL;

COMMENT ON INDEX idx_messages_unread IS
'Optimizes queries for unread messages';

-- ============================================================================
-- Covering Indexes for Read-Heavy Queries
-- ============================================================================

-- 9. Covering index for meeting details
-- Includes frequently accessed columns to avoid table lookups
CREATE INDEX IF NOT EXISTS idx_meetings_covering
ON meetings (id, host_id, status, current_speaker_id, turn_duration, created_at, started_at, ended_at);

COMMENT ON INDEX idx_meetings_covering IS
'Covering index for meeting detail queries - includes all commonly accessed columns';

-- 10. Covering index for message statistics
-- Optimizes COUNT queries and message type aggregations
CREATE INDEX IF NOT EXISTS idx_messages_stats_covering
ON messages (sender_id, message_type, created_at)
INCLUDE (session_id, meeting_id)
WHERE sender_id IS NOT NULL;

COMMENT ON INDEX idx_messages_stats_covering IS
'Covering index for message statistics and aggregation queries';

-- 11. Covering index for session statistics
-- Supports queries counting active/completed sessions per agent
CREATE INDEX IF NOT EXISTS idx_sessions_stats_covering
ON sessions (agent_a_id, status, created_at)
INCLUDE (ended_at)
WHERE agent_a_id IS NOT NULL;

COMMENT ON INDEX idx_sessions_stats_covering IS
'Covering index for session statistics queries';

-- ============================================================================
-- Indexes for Event Queries
-- ============================================================================

-- 12. Meeting events by meeting and type
-- Optimizes event timeline queries
CREATE INDEX IF NOT EXISTS idx_meeting_events_meeting_type
ON meeting_events (meeting_id, event_type, created_at ASC);

COMMENT ON INDEX idx_meeting_events_meeting_type IS
'Optimizes meeting event queries by type';

-- 13. Meeting events by agent
-- Supports queries for agent-specific events
CREATE INDEX IF NOT EXISTS idx_meeting_events_agent
ON meeting_events (agent_id, created_at DESC)
WHERE agent_id IS NOT NULL;

COMMENT ON INDEX idx_meeting_events_agent IS
'Optimizes queries for agent-specific meeting events';

-- ============================================================================
-- Organization and Agent Indexes
-- ============================================================================

-- 14. Agents by organization with active status
-- Supports listing active agents in an organization
CREATE INDEX IF NOT EXISTS idx_agents_org_active
ON agents (org_id, external_id)
WHERE org_id IS NOT NULL;

COMMENT ON INDEX idx_agents_org_active IS
'Optimizes queries for agents within an organization';

-- 15. External ID lookups (already unique, but ensure B-tree optimization)
-- Ensure fast external_id lookups for both orgs and agents
CREATE INDEX IF NOT EXISTS idx_organizations_external_id_btree
ON organizations (external_id)
WHERE external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agents_external_id_btree
ON agents (external_id)
WHERE external_id IS NOT NULL;

-- ============================================================================
-- Update Statistics
-- ============================================================================

-- Analyze all tables to update query planner statistics
ANALYZE messages;
ANALYZE sessions;
ANALYZE meetings;
ANALYZE meeting_participants;
ANALYZE meeting_events;
ANALYZE agents;
ANALYZE organizations;

-- ============================================================================
-- Performance Notes
-- ============================================================================
--
-- Index Strategy Summary:
-- 1. Compound indexes: Multiple columns for complex WHERE clauses
-- 2. Partial indexes: Smaller indexes for specific conditions (WHERE clauses)
-- 3. Covering indexes: Include extra columns to avoid table lookups
-- 4. B-tree indexes: Default for equality/range queries
-- 5. GIN indexes: For JSONB and full-text search (see migrations 003, 004)
--
-- These indexes target:
-- - High-frequency query patterns (message filtering, session queries)
-- - Active entity queries (in_progress meetings/sessions)
-- - Statistical aggregations (COUNT, GROUP BY queries)
-- - Event timelines (meeting events ordered by time)
-- - Multi-column filters (sender + type + date)
--
-- Maintenance:
-- - PostgreSQL auto-vacuums to prevent index bloat
-- - ANALYZE updates statistics for query planner
-- - Monitor index usage with pg_stat_user_indexes
-- - Consider DROP INDEX for unused indexes to reduce write overhead
