# Agent Messaging Protocol - V2 Refactor Plan

## Executive Summary

This document outlines a comprehensive refactor plan for the Agent Messaging Protocol SDK based on thorough code review. The plan addresses critical bugs, missing functionality, and architectural improvements identified in the current implementation.

**Review Date:** December 9, 2025  
**Current Version:** v0.1.0 (Phase 10 Complete)  
**Target Version:** v2.0.0  
**Estimated Duration:** 3-4 weeks  
**Priority:** HIGH (contains critical bug fixes)

---

## Critical Issues Summary

### 🔴 **CRITICAL** (Must Fix Immediately)

1. **Lock Connection Scope Mismatch** - Locks acquired and released on different connections
2. **Meeting Lock Not Implemented** - Turn-based coordination has no locking mechanism
3. **Handler Response Not Stored** - Handler return values not properly captured in sync conversations

### 🟡 **HIGH PRIORITY** (Fix Soon)

4. **Missing One-Way Message Queries** - Cannot retrieve sent/received one-way messages
5. **Limited Conversation Queries** - Missing session management and history methods
6. **Handler Architecture Limitations** - Single global handler insufficient for complex use cases

### 🟢 **MEDIUM PRIORITY** (Enhance Later)

7. **No Message Filtering** - Missing read status filtering, date ranges, pagination
8. **Limited Meeting Queries** - Cannot query meeting history, participant status changes
9. **No Custom Metadata Support** - Messages cannot carry user-defined metadata
10. **Missing Statistics/Analytics** - No message counts, session stats, meeting analytics

---

## Refactor Phases Overview

| Phase | Name | Duration | Priority | Dependencies |
|-------|------|----------|----------|--------------|
| 1 | Critical Bug Fixes | 3-4 days | CRITICAL | None |
| 2 | Essential Query Methods | 4-5 days | HIGH | Phase 1 |
| 3 | Handler Architecture Refactor | 5-6 days | HIGH | Phase 1 |
| 4 | Advanced Features | 4-5 days | MEDIUM | Phase 2, 3 |
| 5 | Testing & Documentation | 4-5 days | HIGH | All phases |

**Total Estimated Duration:** 20-25 days (3-4 weeks)

---

## Refactor Principles

### 1. **Backward Compatibility**
- Maintain existing API surface where possible
- Deprecate rather than remove (with migration guide)
- Version handlers to support gradual migration

### 2. **Safety First**
- All lock operations must be connection-scoped
- Always use try-finally for resource cleanup
- Comprehensive error handling and recovery

### 3. **Extensibility**
- Handler system should support multiple handler types
- Query methods should support filtering and pagination
- Architecture should support future plugin system

### 4. **Performance**
- Minimize database queries (use batching where appropriate)
- Optimize lock contention (reduce lock hold times)
- Add connection pooling optimizations

### 5. **Testability**
- All new methods must have unit tests
- Integration tests for lock mechanisms
- Performance benchmarks for critical paths

---

## Success Criteria

### Phase 1 (Critical Fixes)
- ✅ All locks properly acquired and released on same connection
- ✅ Meeting turn-based locking functional
- ✅ Handler responses properly stored
- ✅ Zero lock leaks under normal and error conditions
- ✅ All existing tests pass

### Phase 2 (Query Methods)
- ✅ Can retrieve one-way messages by sender/recipient/read status
- ✅ Can query conversation sessions and messages with filters
- ✅ Can mark messages read/unread individually
- ✅ Can get message statistics and counts
- ✅ Pagination works correctly for large result sets

### Phase 3 (Handler Refactor)
- ✅ Support multiple handler types (message, system, meeting)
- ✅ Per-message-type handlers work correctly
- ✅ Handler routing logic is clean and testable
- ✅ Backward compatibility maintained with deprecation warnings
- ✅ Handler error isolation (one handler failure doesn't break others)

### Phase 4 (Advanced Features)
- ✅ Message metadata system works
- ✅ Advanced filtering (date range, type, metadata) functional
- ✅ Meeting analytics provide useful insights
- ✅ Performance meets or exceeds targets

### Phase 5 (Testing & Docs)
- ✅ Test coverage ≥ 85%
- ✅ All critical paths have integration tests
- ✅ Performance benchmarks documented
- ✅ Migration guide complete
- ✅ API reference updated

---

## Risk Assessment

### High Risk
- **Lock refactoring** - Could introduce deadlocks if not careful
  - *Mitigation:* Comprehensive testing, gradual rollout, deadlock detection
- **Breaking changes** - Handler refactor might break existing code
  - *Mitigation:* Deprecation period, backward compatibility layer, migration guide

### Medium Risk
- **Performance regression** - New query methods might be slow
  - *Mitigation:* Performance benchmarks, query optimization, caching
- **Database migrations** - Schema changes for metadata support
  - *Mitigation:* Backward-compatible migrations, rollback plans

### Low Risk
- **Documentation lag** - Docs might not keep pace with code
  - *Mitigation:* Write docs alongside code, automated API doc generation

---

## Migration Strategy

### For Users on v0.1.0 → v2.0.0

**Step 1: Update to v1.9.x (transition version)**
- Includes all bug fixes
- Adds new methods with backward compatibility
- Deprecation warnings for old handler registration

**Step 2: Migrate handlers**
- Update handler registration to new typed system
- Test with both old and new APIs

**Step 3: Update to v2.0.0**
- Remove deprecated APIs
- Use new query methods
- Adopt new best practices

**Estimated Migration Time:** 1-2 days for typical application

---

## Resource Requirements

### Development
- 1 senior developer (full-time, 4 weeks)
- 1 code reviewer (20% time, 4 weeks)

### Testing
- 1 QA engineer (50% time, weeks 2-5)
- Integration test environment

### Documentation
- 1 technical writer (25% time, weeks 3-5)

---

## Deliverables

### Code
- [ ] Refactored messaging modules with bug fixes
- [ ] New query methods and repositories
- [ ] Refactored handler architecture
- [ ] Comprehensive test suite (unit + integration)
- [ ] Performance benchmarks

### Documentation
- [ ] Migration guide (v0.1.0 → v2.0.0)
- [ ] Updated API reference
- [ ] Handler architecture guide
- [ ] Query method examples
- [ ] Performance tuning guide
- [ ] Troubleshooting guide

### Release Artifacts
- [ ] v1.9.x (transition release with deprecations)
- [ ] v2.0.0 (final release)
- [ ] Release notes
- [ ] Breaking changes document

---

## Timeline

```
Week 1: Phase 1 (Critical Fixes) + Start Phase 2
├─ Day 1-2: Lock connection scope fixes
├─ Day 3-4: Meeting lock implementation
└─ Day 5: Handler response capture + Start Phase 2

Week 2: Phase 2 (Query Methods) + Start Phase 3
├─ Day 6-7: One-way message queries
├─ Day 8-9: Conversation queries
└─ Day 10: Message stats + Start Phase 3

Week 3: Phase 3 (Handler Refactor) + Start Phase 4
├─ Day 11-12: Handler type system design
├─ Day 13-14: Handler routing implementation
└─ Day 15: Backward compatibility + Start Phase 4

Week 4: Phase 4 (Advanced) + Phase 5 (Testing)
├─ Day 16-17: Message metadata + filtering
├─ Day 18: Meeting analytics
├─ Day 19-20: Comprehensive testing + documentation
```

---

## Next Steps

1. **Review and approve this plan** with stakeholders
2. **Set up development branch** for v2 work
3. **Create detailed phase documents** (see separate files)
4. **Begin Phase 1** immediately (critical fixes)
5. **Schedule weekly check-ins** to track progress

---

## References

- [Phase 1: Critical Bug Fixes](./01-critical-bug-fixes.md)
- [Phase 2: Essential Query Methods](./02-essential-query-methods.md)
- [Phase 3: Handler Architecture Refactor](./03-handler-architecture-refactor.md)
- [Phase 4: Advanced Features](./04-advanced-features.md)
- [Phase 5: Testing & Documentation](./05-testing-documentation.md)
- [Progress Checklist](./PROGRESS.md)
- [Breaking Changes](./BREAKING_CHANGES.md)
- [Migration Guide](./MIGRATION_GUIDE.md)

---

**Status:** 📝 Planning Complete - Ready for Review  
**Last Updated:** December 9, 2025  
**Author:** Code Review Analysis
