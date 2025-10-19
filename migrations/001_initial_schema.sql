-- Agent Messaging Protocol Database Schema
-- PostgreSQL 14+ with JSONB support and advisory locks

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. organizations
-- Purpose: Group agents by organization/tenant
-- ============================================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    external_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. agents
-- Purpose: Individual AI agents that communicate
-- ============================================================================

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    external_id VARCHAR(255) NOT NULL UNIQUE,
    organization_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. sessions
-- Purpose: One-to-one conversation sessions (sync/async)
-- ============================================================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_a_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_b_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    session_type VARCHAR(10) NOT NULL CHECK (session_type IN ('sync', 'async')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'waiting', 'ended')),
    locked_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,

-- Ensure consistent agent ordering and prevent duplicate sessions
CONSTRAINT sessions_agent_order CHECK (agent_a_id < agent_b_id),
    UNIQUE (agent_a_id, agent_b_id, session_type)
);

-- ============================================================================
-- 4. meetings
-- Purpose: Multi-agent meeting sessions
-- ============================================================================

CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    host_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'created' CHECK (
        status IN (
            'created',
            'ready',
            'active',
            'ended'
        )
    ),
    current_speaker_id UUID REFERENCES agents (id) ON DELETE SET NULL,
    turn_duration INTERVAL,
    turn_started_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- 5. meeting_participants
-- Purpose: Track agents participating in meetings
-- ============================================================================

CREATE TABLE meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    meeting_id UUID NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'invited' CHECK (
        status IN (
            'invited',
            'attending',
            'waiting',
            'speaking',
            'left'
        )
    ),
    join_order INTEGER NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (meeting_id, agent_id)
);

-- ============================================================================
-- 6. messages
-- Purpose: Store all messages (one-way, conversation, meeting)
-- ============================================================================

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    message_type VARCHAR(50) NOT NULL DEFAULT 'user_defined' CHECK (message_type IN ('user_defined', 'system', 'timeout', 'ending')),
    content JSONB NOT NULL,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,

-- Either recipient_id OR meeting_id must be set, not both
CONSTRAINT messages_recipient_or_meeting CHECK (
        (recipient_id IS NOT NULL AND meeting_id IS NULL) OR
        (recipient_id IS NULL AND meeting_id IS NOT NULL)
    )
);

-- ============================================================================
-- 7. meeting_events
-- Purpose: Audit log for meeting lifecycle events
-- ============================================================================

CREATE TABLE meeting_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    meeting_id UUID NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    agent_id UUID REFERENCES agents (id) ON DELETE CASCADE,
    data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- organizations
CREATE INDEX idx_organizations_external_id ON organizations (external_id);

-- agents
CREATE INDEX idx_agents_external_id ON agents (external_id);

CREATE INDEX idx_agents_organization_id ON agents (organization_id);

-- sessions
CREATE INDEX idx_sessions_agent_a ON sessions (agent_a_id);

CREATE INDEX idx_sessions_agent_b ON sessions (agent_b_id);

CREATE INDEX idx_sessions_status ON sessions (status);

CREATE INDEX idx_sessions_locked_agent ON sessions (locked_agent_id)
WHERE
    locked_agent_id IS NOT NULL;

-- meetings
CREATE INDEX idx_meetings_host ON meetings (host_id);

CREATE INDEX idx_meetings_status ON meetings (status);

CREATE INDEX idx_meetings_current_speaker ON meetings (current_speaker_id)
WHERE
    current_speaker_id IS NOT NULL;

-- meeting_participants
CREATE INDEX idx_meeting_participants_meeting ON meeting_participants (meeting_id);

CREATE INDEX idx_meeting_participants_agent ON meeting_participants (agent_id);

CREATE INDEX idx_meeting_participants_status ON meeting_participants (meeting_id, status);

CREATE INDEX idx_meeting_participants_join_order ON meeting_participants (meeting_id, join_order);

-- messages
CREATE INDEX idx_messages_sender ON messages (sender_id);

CREATE INDEX idx_messages_recipient ON messages (recipient_id)
WHERE
    recipient_id IS NOT NULL;

CREATE INDEX idx_messages_session ON messages (session_id)
WHERE
    session_id IS NOT NULL;

CREATE INDEX idx_messages_meeting ON messages (meeting_id)
WHERE
    meeting_id IS NOT NULL;

CREATE INDEX idx_messages_created_at ON messages (created_at DESC);

CREATE INDEX idx_messages_content_gin ON messages (content) USING GIN;

-- meeting_events
CREATE INDEX idx_meeting_events_meeting ON meeting_events (meeting_id);

CREATE INDEX idx_meeting_events_type ON meeting_events (meeting_id, event_type);

CREATE INDEX idx_meeting_events_created_at ON meeting_events (created_at DESC);

-- ============================================================================
-- Triggers for updated_at Timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Advisory Lock Helper Functions
-- ============================================================================

-- Convert UUID to bigint for advisory locks
CREATE OR REPLACE FUNCTION uuid_to_lock_key(uuid_val UUID)
RETURNS BIGINT AS $$
BEGIN
    -- Take first 8 bytes of UUID, convert to bigint
    -- Ensure positive value (advisory locks use bigint)
    RETURN (('x' || substring(uuid_val::text from 1 for 16))::bit(64)::bigint & 9223372036854775807);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE organizations IS 'Groups agents by organization/tenant';

COMMENT ON TABLE agents IS 'Individual AI agents that communicate';

COMMENT ON TABLE sessions IS 'One-to-one conversation sessions (sync/async)';

COMMENT ON TABLE meetings IS 'Multi-agent meeting sessions';

COMMENT ON TABLE meeting_participants IS 'Tracks agents participating in meetings';

COMMENT ON TABLE messages IS 'Stores all messages (one-way, conversation, meeting)';

COMMENT ON TABLE meeting_events IS 'Audit log for meeting lifecycle events';

COMMENT ON FUNCTION uuid_to_lock_key (UUID) IS 'Convert UUID to bigint for advisory locks';