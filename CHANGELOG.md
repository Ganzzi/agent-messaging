# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 1: Complete project foundation
  - Project structure and package configuration
  - Database layer with PostgreSQL manager
  - Repository pattern implementation
  - Handler registry system
  - Main SDK client class
  - Pydantic models and exceptions
  - Database schema with 7 tables and 42+ indexes
- Phase 2: One-Way Messaging implementation
  - OneWayMessenger class with send() method
  - Message validation and persistence
  - Asynchronous handler invocation
  - SDK integration with one_way property
  - Comprehensive unit tests (7/7 passing)
- Phase 3: Synchronous Conversations implementation
  - Advisory locks utility for PostgreSQL coordination
  - SyncConversation class with send_and_wait() method
  - Blocking communication with timeout handling
  - Session management with agent ordering
  - Reply mechanism for recipient responses
  - End conversation functionality
  - SDK integration with sync_conversation property

### Changed

### Deprecated

### Removed

### Fixed

### Security

---

## [0.1.0] - 2025-10-19

### Added
- Initial project setup
- Complete Phase 1 foundation implementation

---

[Unreleased]: https://github.com/Ganzzi/agent-messaging/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ganzzi/agent-messaging/releases/tag/v0.1.0
