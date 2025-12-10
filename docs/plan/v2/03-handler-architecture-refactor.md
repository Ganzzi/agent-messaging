# Phase 3: Handler Architecture Refactor

**Priority:** 🟡 HIGH  
**Duration:** 5-6 days  
**Depends On:** Phase 1 (Critical Bug Fixes)  
**Risk Level:** MEDIUM (potential breaking changes, requires deprecation strategy)

---

## Overview

The current handler system is too limited for real-world applications. This phase refactors the handler architecture to support multiple handler types, per-message-type routing, and better extensibility while maintaining backward compatibility.

---

## Current Limitations

### Problem 1: Single Global Handler
```python
# Current: Only ONE handler for ALL message types
@sdk.register_handler()
async def my_handler(message: T, context: MessageContext) -> Optional[T]:
    # Must handle ALL scenarios:
    # - One-way messages
    # - Conversation requests
    # - System messages
    # - Ending messages
    # - Different user message types
    pass
```

**Issues:**
- Handler becomes complex and unmaintainable
- No way to separate concerns
- Difficult to test individual scenarios
- No support for different agents needing different handlers

### Problem 2: No Message Type Routing
```python
# Current: Handler must inspect message manually
async def my_handler(message: Any, context: MessageContext):
    if isinstance(message, dict):
        if message.get("type") == "query":
            # Handle query
        elif message.get("type") == "command":
            # Handle command
    # etc...
```

**Issues:**
- No type safety
- Manual routing error-prone
- Difficult to add new message types

### Problem 3: No Context-Specific Handlers
```python
# Current: Can't differentiate between:
# - One-way messages (no response expected)
# - Sync conversation (response required)
# - Async conversation (response optional)
# - Meeting messages (special handling)
```

---

## New Handler Architecture

### Design Goals

1. **Multiple Handler Types** - Support different handlers for different contexts
2. **Type-Based Routing** - Automatically route to handler based on message type
3. **Backward Compatible** - Existing code continues to work with deprecation warnings
4. **Extensible** - Easy to add new handler types
5. **Type Safe** - Leverage Python typing for better IDE support

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   HandlerRegistry                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  One-Way     │  │ Conversation │  │   Meeting    │ │
│  │  Handlers    │  │   Handlers   │  │   Handlers   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Type-Based Router                        │  │
│  │  (Route by message type/class)                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Default/Fallback Handler                 │  │
│  │  (Backward compatibility)                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 3.1: Handler Type System

### New Handler Types

#### 3.1.1: OneWayHandler
```python
from typing import Protocol, Optional

class OneWayHandler(Protocol[T]):
    """Handler for one-way messages (no response expected)."""
    
    async def __call__(
        self,
        message: T,
        context: MessageContext,
    ) -> None:
        """Handle one-way message.
        
        Args:
            message: The message content
            context: Message context (sender, recipient, timestamp, etc.)
        
        Note: Return value is ignored for one-way messages.
        """
        ...
```

#### 3.1.2: ConversationHandler
```python
class ConversationHandler(Protocol[T]):
    """Handler for conversation messages (may need to respond)."""
    
    async def __call__(
        self,
        message: T,
        context: MessageContext,
    ) -> Optional[T]:
        """Handle conversation message.
        
        Args:
            message: The message content
            context: Message context (includes session_id)
        
        Returns:
            Response message (for sync conversations) or None (for async)
        """
        ...
```

#### 3.1.3: MeetingHandler
```python
class MeetingHandler(Protocol[T]):
    """Handler for meeting messages (multi-agent context)."""
    
    async def __call__(
        self,
        message: T,
        context: MessageContext,
    ) -> None:
        """Handle meeting message.
        
        Args:
            message: The message content
            context: Message context (includes meeting_id, all participants)
        
        Note: Return value is ignored for meeting messages.
        Use meeting.speak() to respond.
        """
        ...
```

#### 3.1.4: SystemHandler
```python
class SystemHandler(Protocol):
    """Handler for system messages (ending, timeout, etc.)."""
    
    async def __call__(
        self,
        message: Dict[str, Any],
        context: MessageContext,
    ) -> None:
        """Handle system message.
        
        Args:
            message: System message (type, reason, etc.)
            context: Message context
        """
        ...
```

### Enhanced MessageContext

```python
class MessageContext(BaseModel):
    """Context information for message handlers."""
    
    # Existing fields
    sender_id: str  # External ID
    recipient_id: str  # External ID
    message_id: UUID
    timestamp: datetime
    
    # New fields
    message_type: MessageType  # USER_DEFINED, SYSTEM, TIMEOUT, ENDING
    session_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    
    # Additional context
    is_one_way: bool = False  # True for one-way messages
    is_sync: bool = False  # True for sync conversations
    requires_response: bool = False  # True if sender is waiting
    
    # Meeting-specific
    meeting_participants: Optional[List[str]] = None  # All participant external IDs
    
    # Utility methods
    def is_conversation(self) -> bool:
        return self.session_id is not None
    
    def is_meeting(self) -> bool:
        return self.meeting_id is not None
```

---

## 3.2: New HandlerRegistry Implementation

### Refactored HandlerRegistry

```python
from typing import Dict, List, Type, Callable, Any
from enum import Enum

class HandlerContext(str, Enum):
    """Handler context types."""
    ONE_WAY = "one_way"
    CONVERSATION = "conversation"
    MEETING = "meeting"
    SYSTEM = "system"
    DEFAULT = "default"  # Fallback/backward compatibility


class HandlerRegistry:
    """Enhanced handler registry with type-based routing."""
    
    def __init__(self, handler_timeout: float = 30.0):
        self._handler_timeout = handler_timeout
        self._background_tasks: set = set()
        
        # Context-specific handlers
        self._one_way_handlers: Dict[Type, Callable] = {}
        self._conversation_handlers: Dict[Type, Callable] = {}
        self._meeting_handlers: Dict[Type, Callable] = {}
        self._system_handlers: Dict[str, Callable] = {}  # Key = system message type
        
        # Default handler (backward compatibility)
        self._default_handler: Optional[Callable] = None
    
    # ===== Registration Methods =====
    
    def register_one_way_handler(
        self,
        message_type: Optional[Type] = None,
    ) -> Callable:
        """Register handler for one-way messages.
        
        Args:
            message_type: Optional message type to handle specifically
        
        Example:
            @registry.register_one_way_handler(NotificationMessage)
            async def handle_notification(msg: NotificationMessage, ctx: MessageContext):
                print(f"Notification: {msg.text}")
        """
        def decorator(handler: Callable) -> Callable:
            key = message_type or Any
            self._one_way_handlers[key] = handler
            logger.info(f"Registered one-way handler for {key}")
            return handler
        return decorator
    
    def register_conversation_handler(
        self,
        message_type: Optional[Type] = None,
    ) -> Callable:
        """Register handler for conversation messages.
        
        Args:
            message_type: Optional message type to handle specifically
        
        Example:
            @registry.register_conversation_handler(QueryMessage)
            async def handle_query(msg: QueryMessage, ctx: MessageContext) -> ResponseMessage:
                return ResponseMessage(answer="...")
        """
        def decorator(handler: Callable) -> Callable:
            key = message_type or Any
            self._conversation_handlers[key] = handler
            logger.info(f"Registered conversation handler for {key}")
            return handler
        return decorator
    
    def register_meeting_handler(
        self,
        message_type: Optional[Type] = None,
    ) -> Callable:
        """Register handler for meeting messages."""
        def decorator(handler: Callable) -> Callable:
            key = message_type or Any
            self._meeting_handlers[key] = handler
            logger.info(f"Registered meeting handler for {key}")
            return handler
        return decorator
    
    def register_system_handler(
        self,
        system_type: str,  # "conversation_ended", "timeout", etc.
    ) -> Callable:
        """Register handler for system messages.
        
        Args:
            system_type: Type of system message to handle
        
        Example:
            @registry.register_system_handler("conversation_ended")
            async def handle_end(msg: Dict, ctx: MessageContext):
                print("Conversation ended")
        """
        def decorator(handler: Callable) -> Callable:
            self._system_handlers[system_type] = handler
            logger.info(f"Registered system handler for '{system_type}'")
            return handler
        return decorator
    
    def register(self, handler: Callable) -> Callable:
        """Register default handler (DEPRECATED - for backward compatibility).
        
        This method is deprecated. Use context-specific registration methods:
        - register_one_way_handler()
        - register_conversation_handler()
        - register_meeting_handler()
        - register_system_handler()
        """
        import warnings
        warnings.warn(
            "register() is deprecated. Use register_conversation_handler() or "
            "register_one_way_handler() for better type safety and routing.",
            DeprecationWarning,
            stacklevel=2
        )
        self._default_handler = handler
        logger.warning(f"Registered DEPRECATED default handler: {handler.__name__}")
        return handler
    
    # ===== Handler Selection =====
    
    def _select_handler(
        self,
        message: Any,
        context: MessageContext,
    ) -> Optional[Callable]:
        """Select appropriate handler based on context and message type."""
        
        # Determine context
        if context.message_type == MessageType.SYSTEM:
            # System message - check system handlers
            if isinstance(message, dict):
                msg_type = message.get("type")
                if msg_type in self._system_handlers:
                    return self._system_handlers[msg_type]
        
        elif context.is_meeting():
            # Meeting message
            handlers = self._meeting_handlers
        
        elif context.is_conversation():
            # Conversation message
            handlers = self._conversation_handlers
        
        elif context.is_one_way:
            # One-way message
            handlers = self._one_way_handlers
        
        else:
            # Unknown context - use default
            return self._default_handler
        
        # Find handler by message type
        message_type = type(message)
        
        # Try exact match
        if message_type in handlers:
            return handlers[message_type]
        
        # Try Any match (wildcard)
        if Any in handlers:
            return handlers[Any]
        
        # Fallback to default
        return self._default_handler
    
    # ===== Invocation Methods =====
    
    async def invoke_handler(
        self,
        message: Any,
        context: MessageContext,
    ) -> Optional[Any]:
        """Invoke handler synchronously (wait for result)."""
        
        handler = self._select_handler(message, context)
        
        if not handler:
            if context.requires_response:
                raise NoHandlerRegisteredError(
                    f"No handler registered for {type(message).__name__} in context {context}"
                )
            else:
                # No handler, no response required - just log
                logger.debug(f"No handler for {type(message).__name__}, skipping")
                return None
        
        try:
            result = await asyncio.wait_for(
                handler(message, context),
                timeout=self._handler_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Handler {handler.__name__} timed out")
            raise HandlerTimeoutError(f"Handler timed out after {self._handler_timeout}s")
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            raise
    
    def invoke_handler_async(
        self,
        message: Any,
        context: MessageContext,
    ) -> Optional[asyncio.Task]:
        """Invoke handler asynchronously (fire-and-forget)."""
        
        handler = self._select_handler(message, context)
        
        if not handler:
            logger.debug(f"No handler for {type(message).__name__}, skipping")
            return None
        
        # Create task with error handling
        task = asyncio.create_task(self._safe_handler_invoke(handler, message, context))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        return task
    
    # ===== Helper Methods =====
    
    def has_handler(self, context: Optional[HandlerContext] = None) -> bool:
        """Check if any handler is registered.
        
        Args:
            context: Optional context to check specifically
        """
        if context == HandlerContext.ONE_WAY:
            return len(self._one_way_handlers) > 0
        elif context == HandlerContext.CONVERSATION:
            return len(self._conversation_handlers) > 0
        elif context == HandlerContext.MEETING:
            return len(self._meeting_handlers) > 0
        elif context == HandlerContext.SYSTEM:
            return len(self._system_handlers) > 0
        else:
            # Check if ANY handler registered
            return (
                len(self._one_way_handlers) > 0
                or len(self._conversation_handlers) > 0
                or len(self._meeting_handlers) > 0
                or len(self._system_handlers) > 0
                or self._default_handler is not None
            )
```

---

## 3.3: Update SDK Registration API

### Enhanced AgentMessaging Class

```python
class AgentMessaging(Generic[T]):
    """Main SDK class."""
    
    # ===== Handler Registration (New Methods) =====
    
    def register_one_way_handler(
        self,
        message_type: Optional[Type[T]] = None,
    ) -> Callable:
        """Register handler for one-way messages.
        
        Example:
            @sdk.register_one_way_handler()
            async def handle_notification(msg: dict, ctx: MessageContext):
                print(f"Got notification: {msg}")
        """
        return self._handler_registry.register_one_way_handler(message_type)
    
    def register_conversation_handler(
        self,
        message_type: Optional[Type[T]] = None,
    ) -> Callable:
        """Register handler for conversation messages.
        
        Example:
            @sdk.register_conversation_handler()
            async def handle_request(msg: dict, ctx: MessageContext) -> dict:
                return {"response": "OK"}
        """
        return self._handler_registry.register_conversation_handler(message_type)
    
    def register_meeting_handler(
        self,
        message_type: Optional[Type[T]] = None,
    ) -> Callable:
        """Register handler for meeting messages."""
        return self._handler_registry.register_meeting_handler(message_type)
    
    def register_system_handler(
        self,
        system_type: str,
    ) -> Callable:
        """Register handler for system messages.
        
        Example:
            @sdk.register_system_handler("conversation_ended")
            async def handle_end(msg: dict, ctx: MessageContext):
                print("Conversation ended")
        """
        return self._handler_registry.register_system_handler(system_type)
    
    def register_handler(self) -> Callable:
        """Register default handler (DEPRECATED).
        
        Use register_conversation_handler() or register_one_way_handler() instead.
        """
        return self._handler_registry.register()
```

---

## 3.4: Migration Strategy

### Backward Compatibility Approach

**Phase 3a: Add New API (Week 1)**
- Implement new handler types
- Keep old `register_handler()` working
- Add deprecation warnings

**Phase 3b: Transition Period (3-6 months)**
- Users migrate to new API
- Both APIs work simultaneously
- Documentation shows both approaches

**Phase 3c: Remove Old API (v3.0.0)**
- Remove deprecated `register_handler()`
- Only new API available

### Migration Examples

**Before (v0.1.0):**
```python
@sdk.register_handler()
async def my_handler(message: dict, context: MessageContext) -> Optional[dict]:
    # Handle all message types
    if context.session_id:
        # Conversation message
        return {"response": "OK"}
    else:
        # One-way message
        return None
```

**After (v2.0.0):**
```python
@sdk.register_conversation_handler()
async def handle_conversation(message: dict, context: MessageContext) -> dict:
    # Only handle conversation messages
    return {"response": "OK"}

@sdk.register_one_way_handler()
async def handle_notification(message: dict, context: MessageContext) -> None:
    # Only handle one-way messages
    print(f"Notification: {message}")
```

---

## Implementation Plan

### Day 1-2: Core Architecture
- [ ] Implement `HandlerContext` enum
- [ ] Refactor `HandlerRegistry` with new storage
- [ ] Implement handler selection logic
- [ ] Add deprecation warnings
- [ ] Write unit tests

### Day 3: Message Context
- [ ] Enhance `MessageContext` model
- [ ] Add context detection logic
- [ ] Update conversation.py to set context flags
- [ ] Update one_way.py to set context flags
- [ ] Update meeting.py to set context flags

### Day 4: SDK API
- [ ] Add new registration methods to `AgentMessaging`
- [ ] Update conversation handler invocation
- [ ] Update one-way handler invocation
- [ ] Update meeting handler invocation
- [ ] Write integration tests

### Day 5: Testing & Documentation
- [ ] Comprehensive testing of new API
- [ ] Test backward compatibility
- [ ] Write migration guide
- [ ] Update API reference
- [ ] Create examples

### Day 6: Code Review & Refinement
- [ ] Code review
- [ ] Fix issues
- [ ] Performance testing
- [ ] Final documentation updates

---

## Testing Requirements

### Unit Tests
- ✅ Handler selection works for each context
- ✅ Type-based routing works correctly
- ✅ Fallback to default handler works
- ✅ Deprecation warnings are raised
- ✅ Multiple handlers can coexist

### Integration Tests
- ✅ One-way messages route to one-way handlers
- ✅ Conversation messages route to conversation handlers
- ✅ Meeting messages route to meeting handlers
- ✅ System messages route to system handlers
- ✅ Backward compatibility with old register() method
- ✅ Handler errors don't break other handlers

### Migration Tests
- ✅ Old code continues to work with warnings
- ✅ New code works as expected
- ✅ Mixed old/new code works together

---

## Acceptance Criteria

- [ ] New handler types implemented and working
- [ ] Type-based routing functional
- [ ] Backward compatibility maintained
- [ ] Deprecation warnings added
- [ ] Test coverage ≥ 85%
- [ ] Migration guide complete
- [ ] Examples updated
- [ ] API reference updated
- [ ] Code review approved

---

**Status:** 📝 Ready for Implementation  
**Depends On:** Phase 1 Complete  
**Estimated Completion:** Day 15-16
