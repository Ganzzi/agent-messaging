# Handler System Refactor Plan

**Date**: December 19, 2025  
**Status**: Planning  
**Priority**: High  
**Breaking Changes**: Minor (removal of unused APIs)

## Executive Summary

The current handler system has three major issues:
1. **Lost Type Safety**: Generic types from SDK are not preserved in handlers
2. **Dual Systems**: Global registry and class-based event handlers cause confusion
3. **Unused Code**: MEETING and SYSTEM handler contexts are defined but never used

This refactor will clean up unused code, clarify the architecture, and improve type documentation without breaking existing functionality.

## Problem Analysis

### Problem 1: Type Safety Lost in Registry

**Current Implementation:**
```python
# SDK declares generic types
class AgentMessaging(Generic[T_OneWay, T_Conversation, T_Meeting]):
    ...

# Handler registry uses Any
AnyHandler = Callable[[Any, MessageContext], Any]
_handlers: Dict[HandlerContext, AnyHandler] = {}
```

**Issue**: Type information from `AgentMessaging[Notification, Query, MeetingMsg]` is lost when handlers are registered and invoked.

**Impact**: 
- No IDE autocomplete for message types in handlers
- No type checking - handlers can accept wrong message types
- Runtime errors possible if handler expects wrong type

**Example of Lost Safety:**
```python
# User declares types
async with AgentMessaging[Notification, Query, MeetingMsg]() as sdk:
    await sdk.one_way.send("alice", ["bob"], Notification(text="Hi"))

# Handler has no type enforcement
@register_one_way_handler
async def handle(message: Any, context: MessageContext) -> None:
    # IDE doesn't know message is Notification
    # No autocomplete, no type checking
    text = message.text  # Could fail at runtime
```

### Problem 2: Two Handler Systems

**Global Handler Registry** (`handlers/registry.py`):
- Purpose: Process message content (ONE_WAY, CONVERSATION, etc.)
- Pattern: Global decorator-based registration
- Storage: Global `_handlers` dict
- Lifecycle: Application-wide, shared across all SDK instances

**Instance-Based Event Handlers** (`handlers/events.py`):
- Purpose: Process meeting lifecycle events (MEETING_STARTED, TURN_CHANGED, etc.)
- Pattern: Instance-based class with methods
- Storage: Per-instance `self._handlers` dict
- Lifecycle: Per-SDK-instance, isolated between instances

**Why Two Systems Exist:**
- Meeting events are lifecycle/state changes, not message content
- Events need per-SDK-instance handlers (different apps, different behaviors)
- Message handlers are global (same handler logic for all SDK instances)

**Issue**: Confusion about when to use which system, inconsistent API patterns.

### Problem 3: Unused Handler Contexts

**Defined but Never Used:**

1. **`HandlerContext.MEETING`**
   - Defined in `types.py`
   - `register_meeting_handler()` exists in `registry.py`
   - `MeetingHandler` protocol defined in `types.py`
   - **NEVER INVOKED**: `MeetingManager.speak()` doesn't use handler registry
   - Meeting messages are processed directly, not through handlers

2. **`HandlerContext.SYSTEM`**
   - Defined in `types.py`
   - `register_system_handler()` exists in `registry.py`
   - `SystemHandler` protocol defined in `types.py`
   - **NEVER INVOKED**: No code path calls system handlers
   - System messages (timeouts, errors) are handled directly

**Why They Exist:**
- Planned features that were never fully implemented
- Architecture evolved but dead code remained

**Impact**:
- Confuses users who try to use these handlers
- Clutters API surface with non-functional features
- Maintenance burden for unused code

## Proposed Solution

### Design Principles

1. **Clarity over Consistency**: Accept that two handler patterns exist for good reasons
2. **Document the Why**: Make it clear when to use each system
3. **Remove Dead Code**: Delete unused handler contexts
4. **Improve Type UX**: Add comprehensive type documentation and examples
5. **No Breaking Changes**: Keep existing working handlers functional

### Architecture Decision: Keep Both Systems

**Decision**: Maintain both global registry and instance-based event handlers.

**Rationale**:

| Aspect | Global Registry | Instance Event Handlers |
|--------|----------------|-------------------------|
| **Purpose** | Process message content | React to meeting lifecycle |
| **Scope** | Application-wide | Per-SDK-instance |
| **Use Case** | Business logic (handle queries, notifications) | Integration logic (logging, monitoring) |
| **Examples** | "Process support ticket", "Send notification" | "Log meeting start", "Update dashboard" |

**These serve different purposes and should remain separate.**

### Refactor Strategy

#### Phase 1: Remove Unused Code ✅ PRIORITY

**Remove from `handlers/types.py`:**
- `HandlerContext.MEETING` enum value
- `HandlerContext.SYSTEM` enum value
- `MeetingHandler` protocol
- `SystemHandler` protocol

**Remove from `handlers/registry.py`:**
- `register_meeting_handler()` function
- `register_system_handler()` function

**Update exports in `handlers/__init__.py`:**
- Remove `register_meeting_handler` from `__all__`
- Remove `register_system_handler` from `__all__`

**Impact**: 
- **Breaking**: Users calling these functions will get `ImportError`
- **Risk**: LOW - These functions are never invoked, likely never used
- **Migration**: Remove calls to these unused decorators

#### Phase 2: Improve Type Documentation ✅ PRIORITY

**Add Type Hints to Protocol Examples:**

```python
# handlers/types.py
class OneWayHandler(Protocol[T_OneWay]):
    """Protocol for one-way message handlers.
    
    Example with proper typing:
        @register_one_way_handler
        async def handle_notification(
            message: Notification,  # ← Type hint matches T_OneWay
            context: MessageContext
        ) -> None:
            print(f"Received: {message.text}")
    """
```

**Create Type Safety Guide:**
- Document that `T_OneWay`, `T_Conversation`, `T_Meeting` are for user documentation
- Explain how to use type hints in handler functions
- Show IDE autocomplete examples
- Clarify runtime vs compile-time type checking

**Update All Examples:**
- `examples/01_notification_system.py`
- `examples/02_interview.py`
- `examples/03_task_processing.py`
- `examples/04_brainstorming_meeting.py`
- Add proper type hints to all handler functions

#### Phase 3: Document Architecture ✅ PRIORITY

**Create `docs/architecture/handler-systems.md`:**

Contents:
1. **Overview**: Why two systems exist
2. **Global Message Handlers**: When and how to use
3. **Instance Event Handlers**: When and how to use
4. **Type Safety Guide**: How to get good IDE support
5. **Decision Tree**: Which system should I use?
6. **Migration Guide**: Updating from old patterns

**Update `docs/api-reference.md`:**
- Add Handler Systems section
- Cross-reference architecture doc
- Clarify handler registration APIs

**Update `README.md`:**
- Add handler examples with proper types
- Link to architecture documentation

#### Phase 4: Code Quality Improvements (Optional)

**Improve Type Hints in Registry:**
```python
# Current
AnyHandler = Callable[[Any, MessageContext], Any]

# Improved (with documentation)
AnyHandler = Callable[[Any, MessageContext], Any]
"""Handler callable accepting any message type.

While the registry uses Any for flexibility, handlers should use specific
type hints for IDE support:

    @register_one_way_handler
    async def my_handler(
        message: MyMessageType,  # ← Specific type for IDE
        context: MessageContext
    ) -> None:
        pass
"""
```

**Add Runtime Type Validation (Optional):**
- Add optional type checking at handler invocation
- Use `typing.get_type_hints()` to extract handler's expected type
- Validate message type matches at runtime
- Make validation opt-in to avoid breaking changes

## Implementation Plan

### Step 1: Create Backup Branch ✅

```bash
git checkout -b feature/handler-refactor
```

### Step 2: Remove Unused Code

**Files to Modify:**
1. `agent_messaging/handlers/types.py`
2. `agent_messaging/handlers/registry.py`
3. `agent_messaging/handlers/__init__.py`

**Test Strategy:**
- Run full test suite
- Ensure no tests reference removed handlers
- Check for any import errors

### Step 3: Update Documentation

**Create New Docs:**
1. `docs/architecture/handler-systems.md` - Comprehensive architecture guide
2. `docs/guides/type-safety-handlers.md` - Type safety best practices

**Update Existing Docs:**
1. `docs/api-reference.md` - Update handler API section
2. `docs/quick-start.md` - Add type hints to examples
3. `README.md` - Update handler examples

### Step 4: Update Examples

**Files to Modify:**
1. `examples/01_notification_system.py`
2. `examples/02_interview.py`
3. `examples/03_task_processing.py`
4. `examples/04_brainstorming_meeting.py`
5. `examples/05_message_notifications.py`

**Changes:**
- Add explicit type hints to all handler functions
- Add comments explaining type safety
- Show IDE autocomplete examples

### Step 5: Update Tests

**Verify:**
- All tests still pass
- No tests use removed handlers
- Type hints work correctly

### Step 6: Version and Release

**Version Update:**
- Bump version to `0.4.0` (minor version - removed APIs)
- Update `CHANGELOG.md` with breaking changes section

**Migration Guide:**
```markdown
## Migrating to v0.4.0

### Removed APIs

The following unused handler registration functions have been removed:
- `register_meeting_handler()` - Meeting messages don't use handlers
- `register_system_handler()` - System events don't use handlers

**Migration**: If you were using these (unlikely), remove the decorator:

```python
# Before (didn't work anyway)
@register_meeting_handler
async def handle_meeting(message, context):
    pass

# After - Remove decorator, use direct meeting handling
# Or use meeting event handlers for lifecycle events
```

### Improved Type Safety

Add explicit type hints to your handlers for better IDE support:

```python
# Before
@register_one_way_handler
async def handle(message, context):
    text = message.text  # No autocomplete

# After
@register_one_way_handler
async def handle(message: Notification, context: MessageContext) -> None:
    text = message.text  # Full autocomplete!
```
```

## Success Criteria

✅ **Functionality**:
- All existing tests pass
- No regression in message handling
- Event handlers still work

✅ **Code Quality**:
- No unused handler contexts remain
- Code is clearer and more maintainable
- Type hints improve IDE experience

✅ **Documentation**:
- Architecture clearly explained
- Type safety guide available
- Migration path documented

✅ **User Experience**:
- Clear error messages if using removed APIs
- Better autocomplete in handlers
- Less confusion about handler patterns

## Risks and Mitigation

### Risk 1: Breaking Existing Code

**Impact**: Users may have code calling `register_meeting_handler()` or `register_system_handler()`

**Likelihood**: LOW - These handlers were never invoked, likely not used

**Mitigation**:
- Clear migration guide in CHANGELOG
- Deprecation notices in release notes
- Version bump to indicate breaking change (0.3.x → 0.4.0)

### Risk 2: Confusion About Two Systems

**Impact**: Users may still be confused about when to use which handler system

**Likelihood**: MEDIUM - Architecture is complex

**Mitigation**:
- Comprehensive architecture documentation
- Decision tree for choosing handler system
- Clear examples for each use case
- FAQ section addressing common questions

### Risk 3: Type Safety Still Not Perfect

**Impact**: Type hints help but don't enforce types at runtime

**Likelihood**: HIGH - This is a limitation of Python's type system

**Mitigation**:
- Document clearly that types are for IDE/linters, not runtime
- Provide optional runtime validation for users who want it
- Show how to use mypy or pyright for static type checking

## Future Improvements

### Optional: Runtime Type Validation

Add opt-in runtime type checking:

```python
@register_one_way_handler(validate_types=True)
async def handle(message: Notification, context: MessageContext) -> None:
    pass

# At invocation, check that message is actually a Notification
```

### Optional: Generic Handler Registry

Make registry generic to preserve types:

```python
class HandlerRegistry(Generic[T_OneWay, T_Conversation, T_Meeting]):
    def register_one_way(self, handler: OneWayHandler[T_OneWay]) -> None:
        ...
```

**Challenge**: Would require significant refactoring and might break existing code.

### Optional: Unified Event System

Merge global and instance handlers into single system:

```python
# Global scope
@register_handler(scope="global", context="one_way")
async def handle_all(message, context): pass

# Instance scope
@sdk.register_handler(scope="instance", context="meeting_event")
async def handle_this_sdk(event): pass
```

**Challenge**: Would require major breaking changes.

## Appendix A: Handler Usage Survey

### Current Handler Usage in Codebase

**Global Handlers (in use):**
- `HandlerContext.ONE_WAY` → Used by `OneWayMessenger.send()`
- `HandlerContext.CONVERSATION` → Used by `Conversation.send_and_wait()`, `send_no_wait()`
- `HandlerContext.MESSAGE_NOTIFICATION` → Used by `Conversation.send_and_wait()`, `send_no_wait()`

**Global Handlers (unused):**
- `HandlerContext.MEETING` → Defined but never invoked
- `HandlerContext.SYSTEM` → Defined but never invoked

**Instance Handlers (in use):**
- `MeetingEventHandler` → Used by `MeetingManager` for lifecycle events
  - `MEETING_STARTED`, `MEETING_ENDED`, `TURN_CHANGED`, etc.

### Handler Invocation Points

```
OneWayMessenger.send()
  └─> invoke_handler_async(HandlerContext.ONE_WAY, message, context)

Conversation.send_and_wait()
  ├─> invoke_handler_async(HandlerContext.MESSAGE_NOTIFICATION, ...) [if not locked]
  └─> invoke_handler(HandlerContext.CONVERSATION, message, context)

Conversation.send_no_wait()
  ├─> invoke_handler_async(HandlerContext.MESSAGE_NOTIFICATION, ...) [if not locked]
  └─> invoke_handler_async(HandlerContext.CONVERSATION, message, context)

MeetingManager.start_meeting()
  └─> event_handler.emit_meeting_started(meeting_id, host_id, participant_ids)

MeetingManager.speak()
  └─> [NO HANDLER INVOCATION - processes message directly]

MeetingManager.end_meeting()
  └─> event_handler.emit_meeting_ended(meeting_id, host_id)
```

## Appendix B: Type System Analysis

### Python Type System Limitations

**Generic Type Erasure:**
```python
# At compile time
AgentMessaging[Notification, Query, MeetingMsg]

# At runtime (types erased)
AgentMessaging  # Generic parameters not available
```

**Why This Matters:**
- Can't inspect generic parameters at runtime
- Can't validate message type matches T_OneWay at invocation time
- Registry can't enforce type safety dynamically

**Workarounds:**
1. Use type hints for static analysis (mypy, pyright)
2. Document expected types clearly
3. Add optional runtime validation using `isinstance()`

### Type Hint Best Practices

**DO:**
```python
@register_one_way_handler
async def handle(
    message: Notification,  # ✅ Specific type
    context: MessageContext
) -> None:
    ...
```

**DON'T:**
```python
@register_one_way_handler
async def handle(message, context):  # ❌ No type hints
    ...
```

## Appendix C: Meeting Message Handler Decision

### Why Meeting Messages Don't Use Handler Registry

**Current Implementation:**
```python
# In MeetingManager.speak()
async def speak(self, agent_external_id: str, meeting_id: UUID, message: T_Meeting):
    # Message is processed directly - NO handler invocation
    # Store message and update meeting state
    message_id = await self._message_repo.create(...)
    await self._meeting_repo.advance_turn(meeting_id)
```

**Reasons:**
1. **State Management**: Meeting turns are tightly coupled to message processing
2. **Synchronization**: Turn advancement must happen atomically with message storage
3. **Complexity**: Handlers would need meeting-specific context and state
4. **Event System**: Meeting events already provide extensibility

**Alternative Considered:**
```python
# Could add handler for meeting message processing
@register_meeting_handler
async def process_meeting_message(message: MeetingMsg, context: MessageContext) -> MeetingMsg:
    # Process message content
    # But when does turn advance? Before? After?
    # Who updates meeting state?
    return processed_message
```

**Decision**: Keep meeting messages without handler registry. Use event system for extensibility.

## Timeline

- **Phase 1 (Remove Unused)**: 2 hours
- **Phase 2 (Type Docs)**: 3 hours
- **Phase 3 (Architecture Docs)**: 4 hours
- **Phase 4 (Update Examples)**: 2 hours
- **Testing & QA**: 2 hours
- **Total**: ~13 hours (1-2 days)

## Approval

- [ ] Technical Lead Review
- [ ] Architecture Review
- [ ] Breaking Changes Approved
- [ ] Ready to Implement
