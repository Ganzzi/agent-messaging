# Agent Messaging Protocol - Implementation Plan

## Project Overview

**Package Name:** `agent_messaging` (or `agent_comms`, `agent_protocol`)

**Purpose:** A Python SDK that enables AI agents to communicate with each other using human-like messaging patterns, supporting synchronous and asynchronous conversations, and multi-agent meetings.

**Core Technologies:**
- Python 3.11+
- PostgreSQL with psqlpy (async driver)
- asyncio for concurrency
- Pydantic for data validation
- Generic types for extensibility

---

## Implementation Phases

### Phase 1: Foundation & Core Infrastructure ✓
**Estimated Time:** 3-4 days

#### 1.1 Project Setup
- [x] Create project structure
- [ ] Set up pyproject.toml with Poetry
- [ ] Configure dependencies (psqlpy, pydantic, asyncio)
- [ ] Set up development environment (.env template)
- [ ] Create README.md with project overview
- [ ] Set up .gitignore

#### 1.2 Configuration System
- [ ] Create configuration module using Pydantic
- [ ] Database connection settings
- [ ] Timeout configurations
- [ ] Meeting settings (turn duration, etc.)
- [ ] Environment variable loading

#### 1.3 Database Layer
- [ ] Design complete database schema (see schema.md)
- [ ] Create PostgreSQL manager class (psqlpy)
- [ ] Implement connection pool management
- [ ] Create database initialization script
- [ ] Create migration system (simple SQL files)

#### 1.4 Base Models
- [ ] Organization model
- [ ] Agent model
- [ ] Generic Message model (TypeVar support)
- [ ] Session models (conversation, meeting)
- [ ] Enums (MessageType, SessionStatus, AgentStatus, etc.)

#### 1.5 Repository Pattern
- [ ] Base repository class
- [ ] Organization repository (CRUD)
- [ ] Agent repository (CRUD)
- [ ] Message repository (CRUD + queries)
- [ ] Session repository (conversation & meeting)

---

### Phase 2: One-Way Messaging ✓
**Estimated Time:** 2 days

#### 2.1 Handler System
- [ ] Create handler registry interface
- [ ] Implement handler registration decorator
- [ ] Create handler invocation manager
- [ ] Add error handling for handlers
- [ ] Add logging for handler execution

#### 2.2 One-Way Message Implementation
- [ ] Create OneWayMessenger class
- [ ] Implement send_message() method
- [ ] Message validation
- [ ] Handler invocation on recipient
- [ ] Message persistence
- [ ] Unit tests for one-way messaging

---

### Phase 3: Talk and Wait (Synchronous Conversation) ✓
**Estimated Time:** 4-5 days

#### 3.1 Session Management
- [ ] Design conversation session table
- [ ] Implement session creation/retrieval
- [ ] Session locking mechanism (PostgreSQL advisory locks)
- [ ] Session state management (active, waiting, ended)

#### 3.2 Blocking Communication
- [ ] Create SyncConversation class
- [ ] Implement send_and_wait() method
- [ ] Implement reply() method for locked agent
- [ ] Sender locking logic
- [ ] Recipient unlocking on reply
- [ ] Timeout handling with asyncio
- [ ] Return value handling

#### 3.3 Session Control
- [ ] Implement end_conversation() method
- [ ] Unlock both agents on end
- [ ] Return ending message
- [ ] Session cleanup

#### 3.4 Testing
- [ ] Unit tests for session lifecycle
- [ ] Integration tests for send/reply flow
- [ ] Timeout tests
- [ ] Concurrent conversation tests

---

### Phase 4: Talk Without Waiting (Async Conversation) ✓
**Estimated Time:** 3-4 days

#### 4.1 Non-Blocking Messaging
- [ ] Create AsyncConversation class
- [ ] Implement send_message() (non-blocking)
- [ ] Message queue management
- [ ] Unread message tracking

#### 4.2 Message Retrieval
- [ ] Implement get_unread_messages() method
- [ ] Implement get_messages_from_agent() method
- [ ] Implement wait_for_message() with timeout
- [ ] Mark messages as read

#### 4.3 System Recovery
- [ ] Implement resume_agent_handler() method
- [ ] Detect stopped agents
- [ ] Wait for pending messages
- [ ] Trigger handler for recovery

#### 4.4 Testing
- [ ] Unit tests for async messaging
- [ ] Message retrieval tests
- [ ] Wait timeout tests
- [ ] Recovery mechanism tests

---

### Phase 5: Multi-Agent Meetings ✓
**Estimated Time:** 6-7 days

#### 5.1 Meeting Session Management
- [ ] Design meeting session table
- [ ] Design meeting participants table
- [ ] Design meeting messages table
- [ ] Implement meeting creation
- [ ] Implement participant management

#### 5.2 Meeting Attendance
- [ ] Create Meeting class
- [ ] Implement attend_meeting() method
- [ ] Agent locking on attendance
- [ ] Track attendance status
- [ ] Validate all agents attended

#### 5.3 Meeting Flow Control
- [ ] Implement start_meeting() (host only)
- [ ] Initial message from host
- [ ] Optional next speaker selection
- [ ] Host locking after start
- [ ] First speaker unlocking

#### 5.4 Turn-Based Speaking
- [ ] Implement speak() method
- [ ] Turn time tracking
- [ ] Current speaker locking after speak
- [ ] Next speaker unlocking
- [ ] Round-robin speaker selection
- [ ] Return value to unlocked speaker

#### 5.5 Speaking Timeout
- [ ] Implement turn timeout mechanism
- [ ] Auto-advance to next speaker
- [ ] Timeout message generation
- [ ] Handle timed-out agent messages
- [ ] Exception for host during start

#### 5.6 Meeting Management
- [ ] Implement end_meeting() (host only)
- [ ] Unlock all agents
- [ ] Return ending messages
- [ ] Close meeting session

#### 5.7 Leave Meeting
- [ ] Implement leave_meeting() method
- [ ] Validate not host
- [ ] Wait for current turn to finish
- [ ] Adjust turn order
- [ ] Remove from participants

#### 5.8 Meeting Queries
- [ ] Implement get_meeting_status() method
- [ ] Return current speaker
- [ ] Return participant list
- [ ] Return meeting state

#### 5.9 Meeting History
- [ ] Implement get_meeting_history() method
- [ ] Return ordered messages
- [ ] Include timestamps and speakers
- [ ] Include system messages (timeouts, joins, leaves)

#### 5.10 Event System
- [ ] Design event handler interface
- [ ] Implement event registration
- [ ] Events: agent_spoke, agent_joined, agent_left
- [ ] Events: agent_timed_out, meeting_ended
- [ ] Event handler invocation
- [ ] Error handling for event handlers

#### 5.11 Testing
- [ ] Unit tests for meeting lifecycle
- [ ] Integration tests for full meeting flow
- [ ] Timeout handling tests
- [ ] Leave meeting tests
- [ ] Event handler tests
- [ ] Concurrent meeting tests

---

### Phase 6: Core API & SDK Interface ✓
**Estimated Time:** 3 days

#### 6.1 Main SDK Class
- [ ] Create AgentMessaging class (main entry point)
- [ ] Initialize database manager
- [ ] Register organizations and agents
- [ ] Access to all messaging types
- [ ] Context manager support (async with)

#### 6.2 Organization & Agent Management
- [ ] Implement register_organization() method
- [ ] Implement register_agent() method
- [ ] Implement get_organization() method
- [ ] Implement get_agent() method
- [ ] Sync external_id with internal UUID

#### 6.3 Handler Registration
- [ ] Implement register_handler() decorator
- [ ] Implement register_meeting_event_handler() decorator
- [ ] Handler storage and retrieval
- [ ] Type hints for handlers

#### 6.4 API Documentation
- [ ] Create comprehensive API reference
- [ ] Method signatures and parameters
- [ ] Return types and exceptions
- [ ] Usage examples for each method

---

### Phase 7: Error Handling & Resilience ✓
**Estimated Time:** 2-3 days

#### 7.1 Exception Hierarchy
- [ ] Create base exception class
- [ ] AgentNotFound exception
- [ ] SessionNotFound exception
- [ ] MeetingNotFound exception
- [ ] HandlerNotRegistered exception
- [ ] TimeoutException exception
- [ ] InvalidOperation exception

#### 7.2 Validation
- [ ] Input validation for all methods
- [ ] Agent existence checks
- [ ] Session state validation
- [ ] Meeting state validation
- [ ] Permission validation (host-only operations)

#### 7.3 Graceful Degradation
- [ ] Connection pool exhaustion handling
- [ ] Database connection failures
- [ ] Handler execution failures
- [ ] Timeout recovery strategies

---

### Phase 8: Testing & Quality Assurance ✓
**Estimated Time:** 4-5 days

#### 8.1 Unit Tests
- [ ] Repository layer tests
- [ ] Model validation tests
- [ ] Handler system tests
- [ ] Each messaging type tests
- [ ] Code coverage > 80%

#### 8.2 Integration Tests
- [ ] End-to-end conversation flows
- [ ] Multi-agent meeting scenarios
- [ ] Concurrent operations tests
- [ ] Database transaction tests

#### 8.3 Performance Tests
- [ ] Connection pool stress tests
- [ ] Concurrent messaging benchmarks
- [ ] Large meeting tests (50+ agents)
- [ ] Message throughput tests

#### 8.4 Test Infrastructure
- [ ] Docker Compose for PostgreSQL test database
- [ ] pytest configuration
- [ ] Test fixtures and factories
- [ ] Continuous integration setup

---

### Phase 9: Documentation & Examples ✓
**Estimated Time:** 3-4 days

#### 9.1 User Documentation
- [ ] Installation guide
- [ ] Quick start tutorial
- [ ] Configuration guide
- [ ] Core concepts explanation
- [ ] Troubleshooting guide

#### 9.2 Example Applications
- [ ] Simple one-way notification example
- [ ] Two-agent interview example
- [ ] Customer support chat example
- [ ] Multi-agent brainstorming meeting
- [ ] Complex workflow orchestration

#### 9.3 Developer Documentation
- [ ] Architecture overview
- [ ] Database schema documentation
- [ ] Contributing guidelines
- [ ] Code style guide
- [ ] Release process

#### 9.4 API Reference
- [ ] Auto-generated from docstrings
- [ ] Complete method documentation
- [ ] Type hints documentation
- [ ] Exception documentation

---

### Phase 10: Packaging & Distribution ✓
**Estimated Time:** 2 days

#### 10.1 Package Configuration
- [ ] Finalize pyproject.toml
- [ ] Set version number (0.1.0)
- [ ] Add package metadata
- [ ] Configure build system
- [ ] Add license file

#### 10.2 Distribution
- [ ] Build source distribution
- [ ] Build wheel distribution
- [ ] Test installation from package
- [ ] Publish to PyPI (test first)
- [ ] Publish to PyPI (production)

#### 10.3 Release Notes
- [ ] Changelog documentation
- [ ] Version 0.1.0 release notes
- [ ] Migration guide (if applicable)
- [ ] Known issues documentation

---

## Project Timeline

**Total Estimated Time:** 32-39 days (~6-8 weeks)

```
Week 1-2:   Foundation, Database, One-Way Messaging
Week 3:     Synchronous Conversations
Week 4:     Asynchronous Conversations
Week 5-6:   Multi-Agent Meetings
Week 7:     Core API, Error Handling, Testing
Week 8:     Documentation, Examples, Packaging
```

---

## Success Criteria

### Functional Requirements
- ✓ All four messaging types fully implemented
- ✓ Handler registration and invocation working
- ✓ Meeting event system functional
- ✓ Timeout mechanisms working correctly
- ✓ Session management robust

### Non-Functional Requirements
- ✓ Test coverage > 80%
- ✓ All public APIs documented
- ✓ Performance: 1000+ messages/second
- ✓ Support for 100+ concurrent meetings
- ✓ Zero connection leaks

### Documentation Requirements
- ✓ Complete API reference
- ✓ At least 5 working examples
- ✓ Architecture documentation
- ✓ User guide and tutorials

---

## Dependencies & Prerequisites

### Required Software
- Python 3.11+
- PostgreSQL 14+
- Poetry (package management)
- Docker (for testing)

### Python Libraries
- psqlpy >= 0.11.0
- pydantic >= 2.0
- python-dotenv
- pytest
- pytest-asyncio
- pytest-cov

---

## Risk Assessment

### High Risk
1. **Locking Mechanism Complexity:** PostgreSQL advisory locks and asyncio coordination
   - Mitigation: Thorough testing, clear state diagrams

2. **Timeout Coordination:** Multiple timeouts across async operations
   - Mitigation: Centralized timeout manager, extensive timeout tests

3. **Concurrent Meeting Management:** Race conditions in turn-based speaking
   - Mitigation: Database-level locking, atomic operations

### Medium Risk
1. **Generic Type Support:** Maintaining type safety with user-defined message models
   - Mitigation: Clear type hints, validation examples

2. **Handler Error Propagation:** Handling failures in user-provided handlers
   - Mitigation: Try-catch wrappers, error logging, clear documentation

3. **Database Migration:** Schema changes in future versions
   - Mitigation: Version tracking, migration scripts

### Low Risk
1. **Connection Pool Exhaustion:** Under heavy load
   - Mitigation: Configurable pool size, monitoring, backpressure

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Refine requirements** based on feedback
3. **Start Phase 1** with project setup
4. **Daily standups** to track progress
5. **Weekly demos** of completed features

---

## Notes

- This is an ambitious project requiring careful attention to concurrency
- Consider pair programming for complex locking mechanisms
- Prototype critical features (locking, timeouts) early
- Maintain comprehensive logs for debugging distributed agent interactions
