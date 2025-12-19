# Meeting Turn-Based Locking Enhancement

**Status:** Planning  
**Created:** December 19, 2025  
**Version:** 0.5.0 (proposed)

---

## Overview

This document outlines enhancements to the meeting system to add turn-based locking capabilities to `attend_meeting` and `speak` methods, along with returning recent messages when waiting for turns.

---

## Motivation

Currently, the meeting system has different behaviors for different methods:

- **`attend_meeting`**: Marks an agent as present and returns immediately (non-blocking)
- **`speak`**: Validates the speaker's turn but doesn't provide waiting capabilities

This creates challenges for agents that want to:
1. Wait for their turn to speak without busy-polling
2. Receive messages that occurred while waiting
3. Have consistent locking behavior across meeting operations

---

## Goals

1. **Unified Locking Behavior**: Both `attend_meeting` and `speak` should support optional turn-based waiting
2. **Message Return**: When waiting for a turn, return all messages that occurred during the wait
3. **Backward Compatibility**: Default behavior should remain unchanged (non-blocking)
4. **Simplification**: Remove unused query methods to reduce API surface

---

## Proposed Changes

### 1. Add `wait_for_turn` Parameter

Both `attend_meeting` and `speak` will accept an optional `wait_for_turn: bool = False` parameter:

```python
async def attend_meeting(
    self,
    agent_external_id: str,
    meeting_id: UUID,
    wait_for_turn: bool = False,
) -> Union[bool, Tuple[bool, List[Dict[str, Any]]]]:
    """
    Args:
        agent_external_id: External ID of the agent attending
        meeting_id: Meeting UUID
        wait_for_turn: If True, blocks until it's the agent's turn and returns messages
        
    Returns:
        - If wait_for_turn=False: bool (success status)
        - If wait_for_turn=True: Tuple[bool, List[Dict]] (success, messages since attend)
    """
```

```python
async def speak(
    self,
    agent_external_id: str,
    meeting_id: UUID,
    message: T_Meeting,
    metadata: Optional[Dict[str, Any]] = None,
    wait_for_turn: bool = False,
) -> Union[UUID, Tuple[UUID, List[Dict[str, Any]]]]:
    """
    Args:
        agent_external_id: External ID of the speaker
        meeting_id: Meeting UUID
        message: Message content
        metadata: Optional metadata
        wait_for_turn: If True, blocks until it's the agent's turn and returns messages
        
    Returns:
        - If wait_for_turn=False: UUID (message ID, or raises NotYourTurnError)
        - If wait_for_turn=True: Tuple[UUID, List[Dict]] (message_id, messages since wait started)
    """
```

### 2. Locking Mechanism

When `wait_for_turn=True`:

1. **Record start timestamp**: Capture the current time when the method is called
2. **Acquire agent lock**: Use existing `SessionLock` mechanism to block
3. **Wait for turn**: Lock is released when it becomes the agent's turn
4. **Fetch messages**: Query messages created after the start timestamp
5. **Return messages**: Include all meeting messages since the method was called

### 3. Helper Method for Message Fetching

Add a private helper method to fetch messages since a timestamp:

```python
async def _get_messages_since(
    self,
    meeting_id: UUID,
    since_timestamp: datetime,
) -> List[Dict[str, Any]]:
    """
    Get all messages in a meeting since a specific timestamp.
    
    Args:
        meeting_id: Meeting UUID
        since_timestamp: Timestamp to fetch messages from
        
    Returns:
        List of message dictionaries with content, sender, and timestamp
    """
```

### 4. Remove Deprecated Query Methods

The following methods will be removed as they're not essential to core functionality:

- `get_participant_history(meeting_id: str)` → Use `get_meeting_history()` instead
- `get_meeting_statistics(agent_id: str)` → Application-level concern
- `get_participation_analysis(meeting_id: str)` → Application-level concern
- `get_meeting_timeline(meeting_id: str)` → Use `get_meeting_history()` instead
- `get_turn_statistics(meeting_id: str)` → Application-level concern

These methods add complexity without clear use cases in the core SDK.

---

## Implementation Details

### Message Structure

Messages returned from `_get_messages_since` will have the structure:

```python
{
    "message_id": str,          # UUID as string
    "sender_external_id": str,  # External ID of sender
    "content": Dict[str, Any],  # Message content (JSONB)
    "metadata": Dict[str, Any], # Optional metadata
    "created_at": str,          # ISO 8601 timestamp
    "speaker_order": int        # Turn number in meeting
}
```

### Lock Acquisition Flow

```
1. attend_meeting(agent_id, meeting_id, wait_for_turn=True)
   ↓
2. Mark participant as PRESENT
   ↓
3. Check if it's agent's turn
   ↓ (if not their turn)
4. Record current_timestamp
   ↓
5. Acquire SessionLock(meeting_id, agent_id)
   ↓
6. [BLOCKED] Wait for turn...
   ↓ (turn assigned by start_meeting or speak)
7. Lock released
   ↓
8. Fetch messages since current_timestamp
   ↓
9. Return (True, messages)
```

### Backward Compatibility

- Default behavior (`wait_for_turn=False`) remains unchanged
- Existing code continues to work without modifications
- New behavior is opt-in via parameter

---

## Testing Strategy

### Unit Tests

1. **Test `attend_meeting` with `wait_for_turn=False`** (current behavior)
   - Should return immediately with boolean
   - Should mark participant as present

2. **Test `attend_meeting` with `wait_for_turn=True`**
   - Should block until agent's turn
   - Should return messages that occurred during wait
   - Should handle timeout scenarios

3. **Test `speak` with `wait_for_turn=False`** (current behavior)
   - Should raise `NotYourTurnError` if not agent's turn
   - Should succeed immediately if it is agent's turn

4. **Test `speak` with `wait_for_turn=True`**
   - Should wait until it's the agent's turn
   - Should return messages that occurred during wait
   - Should send the message when turn arrives

5. **Test `_get_messages_since` helper**
   - Should return only messages after timestamp
   - Should handle empty results
   - Should order messages correctly

### Integration Tests

1. **Multi-agent concurrent attendance**
   - Multiple agents call `attend_meeting(wait_for_turn=True)` concurrently
   - Verify all agents receive messages in order
   - Verify locks are properly released

2. **Speaking while others wait**
   - Agent A calls `speak(wait_for_turn=True)`
   - Agent B (has turn) speaks
   - Verify Agent A receives Agent B's message

3. **Message consistency**
   - Verify returned messages match `get_meeting_history()`
   - Verify no duplicates or missing messages

### Edge Cases

1. Meeting ends while agent is waiting
2. Agent leaves meeting while waiting
3. Multiple agents waiting for same turn slot
4. Timeout during wait
5. Empty message history (first attendee)

---

## API Changes Summary

### Modified Methods

| Method | Change | Breaking? |
|--------|--------|-----------|
| `attend_meeting` | Added `wait_for_turn` parameter and changed return type | No* |
| `speak` | Added `wait_for_turn` parameter and changed return type | No* |

*Not breaking due to default parameter value maintaining current behavior

### Removed Methods

| Method | Replacement |
|--------|-------------|
| `get_participant_history` | Use `get_meeting_history` |
| `get_meeting_statistics` | Application-level analysis |
| `get_participation_analysis` | Application-level analysis |
| `get_meeting_timeline` | Use `get_meeting_history` |
| `get_turn_statistics` | Application-level analysis |

### New Internal Methods

| Method | Purpose |
|--------|---------|
| `_get_messages_since` | Fetch messages after a timestamp |

---

## Example Usage

### Example 1: Blocking Attendance

```python
# Agent attends and waits for their turn
success, messages = await sdk.meeting.attend_meeting(
    agent_external_id="alice",
    meeting_id=meeting_id,
    wait_for_turn=True  # Block until it's Alice's turn
)

print(f"Attended: {success}")
print(f"Messages while waiting: {len(messages)}")
for msg in messages:
    print(f"  - {msg['sender_external_id']}: {msg['content']}")
```

### Example 2: Blocking Speak

```python
# Agent waits for their turn to speak
message_id, messages = await sdk.meeting.speak(
    agent_external_id="bob",
    meeting_id=meeting_id,
    message={"text": "My idea..."},
    wait_for_turn=True  # Wait for turn, then speak
)

print(f"Spoke with message ID: {message_id}")
print(f"Missed {len(messages)} messages while waiting")
```

### Example 3: Backward Compatible (Non-blocking)

```python
# Current behavior still works
success = await sdk.meeting.attend_meeting(
    agent_external_id="carol",
    meeting_id=meeting_id,
    # wait_for_turn defaults to False
)
print(f"Attended: {success}")
```

---

## Migration Guide

### For Existing Users

If you're using the current API, no changes are required. The new `wait_for_turn` parameter defaults to `False`, maintaining current behavior.

### To Adopt New Features

1. **Change `attend_meeting` calls** that need waiting:
   ```python
   # Before
   success = await sdk.meeting.attend_meeting(agent_id, meeting_id)
   
   # After (if you want to wait)
   success, messages = await sdk.meeting.attend_meeting(
       agent_id, meeting_id, wait_for_turn=True
   )
   ```

2. **Change `speak` calls** that need waiting:
   ```python
   # Before (would raise NotYourTurnError)
   try:
       msg_id = await sdk.meeting.speak(agent_id, meeting_id, message)
   except NotYourTurnError:
       # Handle error
   
   # After (waits automatically)
   msg_id, messages = await sdk.meeting.speak(
       agent_id, meeting_id, message, wait_for_turn=True
   )
   ```

3. **Replace removed query methods**:
   ```python
   # Before
   history = await sdk.meeting.get_participant_history(meeting_id)
   
   # After
   history = await sdk.meeting.get_meeting_history(meeting_id)
   # Then filter/analyze at application level
   ```

---

## Implementation Phases

### Phase 1: Core Implementation
- [ ] Implement `_get_messages_since` helper method
- [ ] Refactor `attend_meeting` with `wait_for_turn` parameter
- [ ] Refactor `speak` with `wait_for_turn` parameter
- [ ] Remove deprecated query methods

### Phase 2: Testing
- [ ] Write unit tests for new functionality
- [ ] Write integration tests for concurrent scenarios
- [ ] Test backward compatibility
- [ ] Test edge cases

### Phase 3: Documentation
- [ ] Update API reference documentation
- [ ] Update examples in `examples/` folder
- [ ] Add migration guide
- [ ] Update README.md if needed

### Phase 4: Validation
- [ ] Run full test suite
- [ ] Manual testing of examples
- [ ] Performance testing for blocking scenarios
- [ ] Review for edge cases

---

## Open Questions

1. **Timeout behavior**: Should `wait_for_turn` have a default timeout? Or rely on asyncio cancellation?
   - **Decision**: Use asyncio cancellation, allow users to set timeout externally

2. **Message limit**: Should we limit the number of returned messages?
   - **Decision**: No limit initially, can add `max_messages` parameter later if needed

3. **Type hints**: How to handle Union return types elegantly?
   - **Decision**: Use Union types, consider overloads in future for better type inference

---

## Success Criteria

1. ✅ Both methods support optional turn-based waiting
2. ✅ Messages are returned when waiting for turn
3. ✅ Backward compatibility maintained
4. ✅ All tests pass (100% coverage of new code)
5. ✅ Documentation updated
6. ✅ Examples demonstrate new functionality

---

## References

- [Handler Systems Architecture](../architecture/handler-systems.md)
- [API Reference](../api-reference.md)
- [Meeting Manager Implementation](../../agent_messaging/messaging/meeting.py)
- [Lock Mechanisms](../../agent_messaging/utils/locks.py)
