# Agent Messaging Protocol - Testing Strategy

## Overview

Comprehensive testing strategy covering unit tests, integration tests, performance tests, and end-to-end scenarios.

---

## Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E Tests │  (10% - Full scenarios)
                    └─────────────┘
                ┌───────────────────┐
                │ Integration Tests │  (30% - Component interactions)
                └───────────────────┘
            ┌─────────────────────────┐
            │      Unit Tests         │  (60% - Individual functions)
            └─────────────────────────┘
```

**Target Coverage:** 80%+ overall, 90%+ for critical paths

---

## Test Environment Setup

### Docker Compose for Test Database

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  postgres-test:
    image: postgres:15
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: agent_messaging_test
    ports:
      - "5433:5432"
    volumes:
      - postgres-test-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres-test-data:
```

### pytest Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto

# Markers
markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (require database)
    slow: Slow tests (>1 second)
    timeout: Tests involving timeouts
    concurrent: Tests with concurrent operations
    meeting: Meeting-related tests

# Coverage
addopts = 
    --cov=agent_messaging
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
    -v
    --tb=short
```

### Test Environment Variables

```bash
# .env.test
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
POSTGRES_DB=agent_messaging_test
```

---

## Unit Tests

### 1. Configuration Tests

**File:** `tests/unit/test_config.py`

```python
import pytest
from agent_messaging.config import Config


def test_config_defaults():
    """Test default configuration values."""
    config = Config()
    assert config.postgres_host == "localhost"
    assert config.max_pool_size == 10


def test_config_from_env(monkeypatch):
    """Test configuration from environment variables."""
    monkeypatch.setenv("POSTGRES_HOST", "testhost")
    monkeypatch.setenv("POSTGRES_PORT", "5555")
    
    config = Config()
    assert config.postgres_host == "testhost"
    assert config.postgres_port == 5555


def test_config_timeout_settings():
    """Test timeout configuration."""
    config = Config(
        default_conversation_timeout=120.0,
        default_meeting_timeout=300.0
    )
    assert config.default_conversation_timeout == 120.0
```

### 2. Model Tests

**File:** `tests/unit/test_models.py`

```python
import pytest
from uuid import uuid4
from datetime import datetime
from agent_messaging.models import (
    Organization, Agent, Session, Meeting,
    SessionType, SessionStatus, MeetingStatus
)


def test_organization_model():
    """Test organization model validation."""
    org = Organization(
        id=uuid4(),
        external_id="org_001",
        name="Test Org",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert org.external_id == "org_001"


def test_agent_model():
    """Test agent model validation."""
    org_id = uuid4()
    agent = Agent(
        id=uuid4(),
        external_id="agent_alice",
        organization_id=org_id,
        name="Alice",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert agent.organization_id == org_id


def test_session_status_enum():
    """Test session status enum values."""
    assert SessionStatus.ACTIVE == "active"
    assert SessionStatus.WAITING == "waiting"
    assert SessionStatus.ENDED == "ended"
```

### 3. Repository Tests (with mocked database)

**File:** `tests/unit/test_repositories.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from agent_messaging.database.repositories.agent import AgentRepository


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    manager = MagicMock()
    manager.connection = AsyncMock()
    return manager


@pytest.mark.unit
async def test_agent_repository_create(mock_db_manager):
    """Test creating an agent."""
    repo = AgentRepository(mock_db_manager)
    
    agent_id = uuid4()
    org_id = uuid4()
    
    # Mock the database response
    mock_db_manager.execute.return_value.result.return_value = [
        (agent_id, "agent_001", org_id, "Alice")
    ]
    
    result = await repo.create(
        external_id="agent_001",
        organization_id=org_id,
        name="Alice"
    )
    
    assert result.external_id == "agent_001"
```

---

## Integration Tests

### 1. Database Integration Tests

**File:** `tests/integration/test_database.py`

```python
import pytest
from agent_messaging import AgentMessaging
from agent_messaging.config import Config


@pytest.fixture
async def test_sdk():
    """Create SDK instance with test database."""
    config = Config(
        postgres_db="agent_messaging_test",
        postgres_port=5433
    )
    
    sdk = AgentMessaging(config=config)
    await sdk.initialize()
    
    yield sdk
    
    await sdk.close()


@pytest.fixture
async def test_agents(test_sdk):
    """Create test agents."""
    sdk = test_sdk
    
    # Create organization
    await sdk.register_organization("test_org", "Test Organization")
    
    # Create agents
    await sdk.register_agent("agent_a", "test_org", "Agent A")
    await sdk.register_agent("agent_b", "test_org", "Agent B")
    
    return sdk


@pytest.mark.integration
async def test_organization_crud(test_sdk):
    """Test organization CRUD operations."""
    sdk = test_sdk
    
    # Create
    org_id = await sdk.register_organization("org_test", "Test Org")
    assert org_id is not None
    
    # Read
    org = await sdk.get_organization("org_test")
    assert org.name == "Test Org"


@pytest.mark.integration
async def test_agent_crud(test_sdk):
    """Test agent CRUD operations."""
    sdk = test_sdk
    
    # Setup organization
    await sdk.register_organization("org_001", "Org 1")
    
    # Create agent
    agent_id = await sdk.register_agent("agent_001", "org_001", "Alice")
    assert agent_id is not None
    
    # Read agent
    agent = await sdk.get_agent("agent_001")
    assert agent.name == "Alice"
```

### 2. One-Way Messaging Integration

**File:** `tests/integration/test_one_way.py`

```python
import pytest
import asyncio
from pydantic import BaseModel


class TestMessage(BaseModel):
    text: str


@pytest.mark.integration
async def test_one_way_message(test_agents):
    """Test one-way message delivery."""
    sdk = test_agents
    
    # Track handler invocation
    received = []
    
    @sdk.register_handler("agent_b")
    async def handler(message: TestMessage, context):
        received.append(message)
    
    # Send message
    await sdk.one_way.send(
        "agent_a",
        "agent_b",
        TestMessage(text="Hello!")
    )
    
    # Wait a bit for async handler
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0].text == "Hello!"


@pytest.mark.integration
async def test_one_way_missing_handler(test_agents):
    """Test one-way message with missing handler."""
    sdk = test_agents
    
    with pytest.raises(Exception):  # HandlerNotRegisteredError
        await sdk.one_way.send(
            "agent_a",
            "agent_b",
            TestMessage(text="Hello!")
        )
```

### 3. Synchronous Conversation Integration

**File:** `tests/integration/test_sync_conversation.py`

```python
import pytest
import asyncio
from pydantic import BaseModel


class ConversationMessage(BaseModel):
    text: str


@pytest.mark.integration
async def test_sync_conversation_send_and_wait(test_agents):
    """Test synchronous send and wait."""
    sdk = test_agents
    
    @sdk.register_handler("agent_b")
    async def handler(message: ConversationMessage, context):
        if context.requires_reply:
            await sdk.sync_conversation.reply(
                "agent_b",
                context.sender_external_id,
                ConversationMessage(text=f"Reply to: {message.text}")
            )
    
    # Send and wait
    response = await sdk.sync_conversation.send_and_wait(
        "agent_a",
        "agent_b",
        ConversationMessage(text="Question?"),
        timeout=5.0
    )
    
    assert response.text == "Reply to: Question?"


@pytest.mark.integration
@pytest.mark.timeout
async def test_sync_conversation_timeout(test_agents):
    """Test synchronous conversation timeout."""
    sdk = test_agents
    
    @sdk.register_handler("agent_b")
    async def handler(message: ConversationMessage, context):
        # Don't reply - let it timeout
        await asyncio.sleep(10)
    
    with pytest.raises(Exception):  # ConversationTimeoutError
        await sdk.sync_conversation.send_and_wait(
            "agent_a",
            "agent_b",
            ConversationMessage(text="Question?"),
            timeout=1.0
        )
```

### 4. Meeting Integration Tests

**File:** `tests/integration/test_meeting.py`

```python
import pytest
import asyncio
from pydantic import BaseModel
from uuid import UUID


class MeetingMessage(BaseModel):
    speaker: str
    content: str


@pytest.fixture
async def meeting_sdk(test_sdk):
    """Setup meeting with 3 agents."""
    sdk = test_sdk
    
    await sdk.register_organization("meeting_org", "Meeting Org")
    await sdk.register_agent("host", "meeting_org", "Host")
    await sdk.register_agent("agent_1", "meeting_org", "Agent 1")
    await sdk.register_agent("agent_2", "meeting_org", "Agent 2")
    
    return sdk


@pytest.mark.integration
@pytest.mark.meeting
async def test_meeting_lifecycle(meeting_sdk):
    """Test complete meeting lifecycle."""
    sdk = meeting_sdk
    
    # Track attendance
    attended = []
    
    @sdk.register_handler("host")
    async def host_handler(message, context):
        if context.meeting_id:
            attended.append("host")
            await sdk.meeting.attend_meeting("host", context.meeting_id)
    
    @sdk.register_handler("agent_1")
    async def agent1_handler(message, context):
        if context.meeting_id:
            attended.append("agent_1")
            await sdk.meeting.attend_meeting("agent_1", context.meeting_id)
    
    @sdk.register_handler("agent_2")
    async def agent2_handler(message, context):
        if context.meeting_id:
            attended.append("agent_2")
            await sdk.meeting.attend_meeting("agent_2", context.meeting_id)
    
    # Create meeting
    meeting_id = await sdk.meeting.create_meeting(
        "host",
        ["host", "agent_1", "agent_2"],
        turn_duration=60.0
    )
    
    assert isinstance(meeting_id, UUID)
    
    # Wait for agents to attend
    await asyncio.sleep(0.5)
    assert len(attended) == 3
    
    # Get meeting status
    status = await sdk.meeting.get_meeting_status(meeting_id)
    assert status.participant_count == 3
    assert status.status == "ready"  # All attended


@pytest.mark.integration
@pytest.mark.meeting
async def test_meeting_speaking_turns(meeting_sdk):
    """Test turn-based speaking in meeting."""
    sdk = meeting_sdk
    
    # Setup handlers (simplified for test)
    # ... (similar to above)
    
    # Create and start meeting
    meeting_id = await sdk.meeting.create_meeting(
        "host",
        ["host", "agent_1", "agent_2"]
    )
    
    # ... wait for attendance ...
    
    # Start meeting
    await sdk.meeting.start_meeting(
        "host",
        meeting_id,
        MeetingMessage(speaker="Host", content="Welcome!"),
        next_speaker_external_id="agent_1"
    )
    
    # Get history
    history = await sdk.meeting.get_meeting_history(meeting_id)
    assert len(history) >= 1
    assert history[0].content["content"] == "Welcome!"
```

---

## Concurrent & Stress Tests

### 1. Concurrent Operations

**File:** `tests/concurrent/test_concurrent_operations.py`

```python
import pytest
import asyncio


@pytest.mark.concurrent
@pytest.mark.slow
async def test_concurrent_one_way_messages(test_agents):
    """Test sending multiple one-way messages concurrently."""
    sdk = test_agents
    
    received_count = 0
    
    @sdk.register_handler("agent_b")
    async def handler(message, context):
        nonlocal received_count
        received_count += 1
    
    # Send 100 messages concurrently
    tasks = []
    for i in range(100):
        task = sdk.one_way.send(
            "agent_a",
            "agent_b",
            TestMessage(text=f"Message {i}")
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    # Wait for handlers
    await asyncio.sleep(1)
    
    assert received_count == 100


@pytest.mark.concurrent
async def test_multiple_conversations(test_agents):
    """Test multiple concurrent conversations."""
    sdk = test_agents
    
    # Create more agents
    for i in range(10):
        await sdk.register_agent(f"agent_{i}", "test_org", f"Agent {i}")
    
    # Have agent_a talk to all 10 agents concurrently
    # ... (test implementation)
```

### 2. Connection Pool Stress Test

**File:** `tests/stress/test_connection_pool.py`

```python
@pytest.mark.slow
async def test_connection_pool_exhaustion(test_sdk):
    """Test behavior under connection pool exhaustion."""
    sdk = test_sdk
    
    # Attempt to create more connections than pool size
    # Should handle gracefully
    
    tasks = []
    for i in range(50):  # Pool size is 10
        task = sdk.get_agent("agent_a")
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # All should succeed (connections reused)
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) == 50
```

---

## Performance Tests

### 1. Message Throughput

**File:** `tests/performance/test_throughput.py`

```python
import pytest
import time


@pytest.mark.slow
async def test_one_way_message_throughput(test_agents):
    """Test message throughput (messages per second)."""
    sdk = test_agents
    
    message_count = 1000
    
    @sdk.register_handler("agent_b")
    async def handler(message, context):
        pass  # Minimal processing
    
    start_time = time.time()
    
    tasks = []
    for i in range(message_count):
        task = sdk.one_way.send(
            "agent_a",
            "agent_b",
            TestMessage(text=f"Msg {i}")
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    throughput = message_count / elapsed
    
    print(f"Throughput: {throughput:.2f} messages/second")
    
    # Expect at least 1000 messages/second
    assert throughput > 1000


@pytest.mark.slow
async def test_meeting_with_many_participants():
    """Test meeting with 50+ participants."""
    # Test large meeting performance
    # ...
```

---

## End-to-End Scenarios

### 1. Customer Support Scenario

**File:** `tests/e2e/test_customer_support.py`

```python
@pytest.mark.slow
async def test_customer_support_flow():
    """
    E2E: Customer submits ticket, support agent responds,
    customer replies, ticket resolved.
    """
    # Full scenario implementation
    # ...
```

### 2. Multi-Agent Brainstorming

**File:** `tests/e2e/test_brainstorming_meeting.py`

```python
@pytest.mark.slow
@pytest.mark.meeting
async def test_brainstorming_meeting():
    """
    E2E: 5 agents join meeting, take turns sharing ideas,
    host moderates, meeting ends with summary.
    """
    # Full scenario implementation
    # ...
```

---

## Test Utilities

### Fixtures

**File:** `tests/conftest.py`

```python
import pytest
import asyncio
from agent_messaging import AgentMessaging
from agent_messaging.config import Config


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def clean_database():
    """Clean database before each test."""
    # Truncate all tables
    # ...
    yield
    # Cleanup after test
    # ...


@pytest.fixture
def mock_message_handler():
    """Mock message handler for testing."""
    async def handler(message, context):
        return message
    return handler
```

### Test Helpers

**File:** `tests/helpers.py`

```python
from typing import Optional
import asyncio


async def wait_for_condition(
    condition_func,
    timeout: float = 5.0,
    interval: float = 0.1
) -> bool:
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)
    
    return False


async def create_test_agents(sdk, count: int, org_id: str = "test_org"):
    """Create multiple test agents."""
    agents = []
    for i in range(count):
        agent_id = await sdk.register_agent(
            f"agent_{i}",
            org_id,
            f"Agent {i}"
        )
        agents.append(agent_id)
    return agents
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: agent_messaging_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      
      - name: Run tests
        env:
          POSTGRES_HOST: localhost
          POSTGRES_PORT: 5433
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: agent_messaging_test
        run: |
          poetry run pytest
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Test Execution Commands

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run without slow tests
pytest -m "not slow"

# Run with coverage
pytest --cov=agent_messaging --cov-report=html

# Run specific test file
pytest tests/integration/test_one_way.py

# Run with verbose output
pytest -v

# Run in parallel (with pytest-xdist)
pytest -n auto

# Run and stop on first failure
pytest -x
```

---

## Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Core API (client.py) | 95% |
| Messaging classes | 90% |
| Repositories | 85% |
| Database manager | 85% |
| Models | 80% |
| Utilities | 75% |
| **Overall** | **80%+** |

---

## Summary

This testing strategy provides:

✓ **Comprehensive test coverage** across all layers  
✓ **Isolated unit tests** for fast feedback  
✓ **Integration tests** for component interactions  
✓ **Concurrent tests** for race conditions  
✓ **Performance benchmarks** for scalability  
✓ **E2E scenarios** for real-world validation  
✓ **CI/CD integration** for automation

Next steps:
1. Set up test database
2. Implement test fixtures
3. Write tests alongside implementation
4. Monitor coverage continuously
