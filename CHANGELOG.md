# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-20

### Added
- **Complete Agent Messaging Protocol SDK** - Production-ready Python SDK for AI agent communication
- **Four Communication Patterns:**
  - One-Way Messaging (fire-and-forget notifications)
  - Synchronous Conversations (blocking request-response)
  - Asynchronous Conversations (non-blocking message queues)
  - Multi-Agent Meetings (turn-based coordination)
- **Database Layer:**
  - PostgreSQL 14+ with psqlpy async driver
  - 7-table schema with comprehensive indexes
  - Connection pooling and transaction management
  - Advisory locks for coordination
- **Type-Safe Architecture:**
  - Pydantic v2 models for all data structures
  - Generic types for user-defined message content
  - Comprehensive validation and serialization
- **Async-First Design:**
  - Full asyncio/await support throughout
  - Non-blocking operations with proper concurrency
  - Context manager lifecycle management
- **Production Features:**
  - Comprehensive error handling and validation
  - Timeout management for all operations
  - Graceful degradation and resilience patterns
  - Extensive logging and monitoring hooks

### Phase 1: Foundation (October 19, 2025)
- Complete project structure and configuration
- PostgreSQL database schema (7 tables, 42+ indexes, constraints)
- Pydantic models for all entities (organizations, agents, sessions, meetings, messages, events)
- Repository pattern implementation with async database operations
- Handler registry system for message processing
- AgentMessaging SDK class with async context manager
- Comprehensive exception hierarchy
- Development environment setup with Docker Compose
- Unit tests for repository layer (13/15 passing)

### Phase 2: One-Way Messaging (October 19, 2025)
- OneWayMessenger class with send() method
- Message validation and persistence to database
- Asynchronous handler invocation via asyncio.create_task()
- SDK integration with one_way property
- Comprehensive unit tests (7/7 passing)
- Package exports and documentation updates

### Phase 3: Synchronous Conversations (October 19, 2025)
- AdvisoryLock utility for PostgreSQL coordination
- SyncConversation class with send_and_wait() blocking method
- Session management with agent ordering and status tracking
- Timeout handling with configurable duration
- Reply mechanism for recipient responses
- End conversation functionality
- SDK integration with sync_conversation property
- Comprehensive unit tests (10/10 passing)

### Phase 4: Asynchronous Conversations (October 19, 2025)
- AsyncConversation class with message queue pattern
- Non-blocking send() and polling check_responses() methods
- Session-based conversation tracking
- Recipient response handling and storage
- SDK integration with async_conversation property
- Comprehensive unit tests (10/10 passing)

### Phase 5: Multi-Agent Meetings (October 19, 2025)
- MeetingManager class with complete meeting lifecycle
- MeetingTimeoutManager for turn-based coordination
- MeetingEventHandler with comprehensive event system
- Turn-based speaking with PostgreSQL advisory locks
- Participant management and status tracking
- Meeting history and status queries
- Event-driven architecture (meeting_started, turn_changed, meeting_ended, etc.)
- SDK integration with meeting property
- Comprehensive test fixtures and unit tests

### Phase 6: Core API & SDK Interface (October 19, 2025)
- Complete AgentMessaging SDK with organization/agent management
- CRUD operations for organizations and agents
- Handler registration decorators (@register_handler, @register_event_handler)
- Property-based access to all four messaging patterns
- Async context manager for proper resource lifecycle
- Comprehensive integration tests
- Package integration and dependency management

### Phase 7: Error Handling & Resilience (October 19, 2025)
- Comprehensive exception hierarchy with AgentMessagingError base class
- Input validation for all public methods with type checking
- Agent existence and state validation
- Session and meeting state validation
- Permission validation for operations
- Graceful degradation with connection pool error handling
- Handler execution failure handling with logging
- Retry logic for transient failures
- Production-ready resilience patterns

### Phase 8: Documentation & Examples (October 19, 2025)
- Complete API reference documentation (600+ lines)
- Four comprehensive usage examples:
  - Notification system (one-way messaging)
  - Interview simulation (synchronous conversations)
  - Task processing (asynchronous messaging)
  - Brainstorming meeting (multi-agent meetings)
- Test infrastructure with fixtures and configuration
- Documentation updates and status tracking

### Phase 9: Performance Optimization (October 19, 2025)
- Connection pooling optimization
- Query performance tuning
- Index optimization for common access patterns
- Load testing and performance validation
- Memory usage optimization
- Concurrent operation handling

### Phase 10: Major Refactoring (October 20, 2025)
- **Database Layer Refactoring:** Updated PostgreSQLManager with connection() context manager pattern
- **Handler Registry Simplification:** Global handler registration (not per-agent)
- **Type-Safe Event Models:** Created 6 type-safe event data models with Pydantic
- **One-to-Many Messaging:** Updated OneWayMessenger to support broadcast to multiple recipients
- **Unified Conversation Class:** Merged SyncConversation and AsyncConversation into single Conversation class
- **Architecture Improvements:** Clean separation of concerns, simplified patterns, better usability
- **Test Suite:** 134/134 tests passing (100% success rate)

### Technical Specifications
- **Python:** 3.11+ required
- **Database:** PostgreSQL 14+ with JSONB support
- **Dependencies:** psqlpy (async driver), Pydantic v2, pydantic-settings
- **Architecture:** Async-first, type-safe, repository pattern
- **Testing:** 134 comprehensive unit tests, 100% pass rate
- **Documentation:** Complete API reference and usage examples

### Breaking Changes
- None in v0.1.0 (initial release)

### Deprecated
- None

### Fixed
- None (initial release)

### Security
- Input validation on all public APIs
- SQL injection prevention via parameterized queries
- Connection pool isolation
- Advisory lock coordination for thread safety

---

[Unreleased]: https://github.com/Ganzzi/agent-messaging/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ganzzi/agent-messaging/releases/tag/v0.1.0
