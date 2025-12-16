# Agent Messaging Protocol

> A Python SDK for enabling AI agents to communicate like humans

[![PyPI version](https://img.shields.io/pypi/v/agent-messaging.svg)](https://pypi.org/project/agent-messaging/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: v0.3.0 Ready](https://img.shields.io/badge/Status-v0.3.0%20Released-brightgreen.svg)]()
[![Tests: 63/63 (100%)](https://img.shields.io/badge/Tests-63%2F63%20(100%25)-brightgreen.svg)]()

**Agent Messaging Protocol** is a Python SDK that enables AI agents to communicate with each other using human-like messaging patterns. It supports synchronous and asynchronous conversations, one-way notifications, and multi-agent meetings with turn-based coordination.

---

## 🌟 Features

### Four Communication Patterns

- **🔔 One-Way Messages:** Fire-and-forget notifications
- **💬 Synchronous Conversations:** Request-response with blocking waits
- **📨 Asynchronous Conversations:** Non-blocking messaging with queues
- **👥 Multi-Agent Meetings:** Turn-based speaking with timeout management

### Core Capabilities

- ✅ **Type-Safe:** Generic message types with Pydantic validation
- ✅ **High Performance:** PostgreSQL with psqlpy async driver
- ✅ **Scalable:** Connection pooling and efficient database design
- ✅ **Extensible:** Handler registration and event system
- ✅ **Async Native:** Full async/await support with asyncio
- ✅ **Production Ready:** Comprehensive error handling and timeout management

---

## 🚀 Quick Start

### Installation

### Configuration

Agent Messaging supports three configuration patterns:

**1. Direct Python Configuration (Recommended for PyPI users)**
```python
from agent_messaging import AgentMessaging, Config, DatabaseConfig, MessagingConfig

config = Config(
    database=DatabaseConfig(
        host="localhost",
        port=5432,
        user="postgres",
        password="mypassword",
        database="agent_messaging"
    ),
    messaging=MessagingConfig(
        default_sync_timeout=45.0,
        default_meeting_turn_duration=120.0,
        handler_timeout=60.0
    ),
    debug=True
)

async with AgentMessaging[dict](config=config) as sdk:
    # Use SDK with custom config
    pass
```

**2. Environment Variables (Recommended for Docker/K8s)**
```bash
export POSTGRES_HOST=postgres
export POSTGRES_PASSWORD=secure_pass
export DEBUG=false
python your_app.py
```

**3. .env File (Convenient for local development)**
```bash
# Install dev dependencies for .env support
pip install agent-messaging[dev]

# Create .env file
echo "POSTGRES_HOST=localhost" > .env
echo "POSTGRES_PASSWORD=devpass" >> .env
```

### Basic Example

```python
import asyncio
from agent_messaging import AgentMessaging
from pydantic import BaseModel


class ChatMessage(BaseModel):
    text: str


async def main():
    async with AgentMessaging[ChatMessage]() as sdk:
        # Register organization and agents
        await sdk.register_organization("my_org", "My Organization")
        await sdk.register_agent("alice", "my_org", "Alice")
        await sdk.register_agent("bob", "my_org", "Bob")
        
        # Register handler for bob
        @sdk.register_one_way_handler("bob")
        async def message_handler(message: ChatMessage, context):
            print(f"Bob received: {message.text}")
        
        # Send message (one-to-many pattern)
        await sdk.one_way.send(
            sender_external_id="alice",
            recipient_external_ids=["bob"],
            message=ChatMessage(text="Hello Bob!")
        )


if __name__ == "__main__":
    asyncio.run(main())
```

**Output:**
```
bob received: Hello Bob!
```

[See full Quick Start Guide →](docs/quick-start.md)

---

## 📖 Documentation

### Planning Documents

All planning documentation is complete and ready for implementation:

- **[Implementation Plan](docs/plan/00-implementation-plan.md)** - Complete roadmap (10 phases, 6-8 weeks)
- **[Architecture Design](docs/plan/01-architecture.md)** - System design and components
- **[Database Schema](docs/plan/02-database-schema.md)** - PostgreSQL schema design
- **[API Design](docs/plan/03-api-design.md)** - Public API specification
- **[State Machines](docs/plan/04-state-machines.md)** - State transitions and flows
- **[Testing Strategy](docs/plan/05-testing-strategy.md)** - Comprehensive test plan

### User Guides

- **[Quick Start](docs/quick-start.md)** - Get started in 5 minutes
- **[psqlpy Guide](docs/technical/psqlpy-complete-guide.md)** - Database driver reference

---

## 🎯 Use Cases

### Customer Support Bot

```python
response = await sdk.conversation.send_and_wait(
    sender_external_id="customer",
    recipient_external_id="support_agent",
    message=SupportMessage(query="How do I reset my password?"),
    timeout=60.0
)
print(f"Agent: {response.answer}")
```

### Multi-Agent Brainstorming

```python
meeting_id = await sdk.meeting.create_meeting(
    organizer_external_id="moderator",
    participant_external_ids=["designer", "engineer", "product_manager"],
    turn_duration=120.0
)

await sdk.meeting.start_meeting(
    organizer_external_id="moderator",
    meeting_id=meeting_id,
    initial_message=IdeaMessage(content="Let's discuss the new feature..."),
    next_speaker="designer"
)
```

### Task Pipeline

```python
# Step 1: Preprocess
result1 = await sdk.conversation.send_and_wait(
    sender_external_id="orchestrator",
    recipient_external_id="preprocessor",
    message=task_data
)

# Step 2: Analyze
result2 = await sdk.conversation.send_and_wait(
    sender_external_id="orchestrator",
    recipient_external_id="analyzer",
    message=result1
)

# Step 3: Generate output
final = await sdk.conversation.send_and_wait(
    sender_external_id="orchestrator",
    recipient_external_id="generator",
    message=result2
)
```

[See more examples →](examples/)

---

## 🏗️ Architecture (Phase 10: Refactored)

```
┌─────────────────────────────────────┐
│      User Application               │
│  (AI Agents, Business Logic)        │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Agent Messaging SDK               │
│                                     │
│  ┌──────────┐  ┌──────────────┐   │
│  │ One-Way  │  │ Unified      │   │
│  │ Messenger│  │ Conversation │   │
│  │(1-to-N)  │  │ (Sync/Async) │   │
│  └──────────┘  └──────────────┘   │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Meeting Manager            │  │
│  │   (Turn-based coordination)  │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Shared Handler Registry    │  │
│  │   + Typed Event System       │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Repository Layer           │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   PostgreSQL Manager         │  │
│  │   (psqlpy connection pool)   │  │
│  └──────────────────────────────┘  │
└────────────┬────────────────────────┘
             │
             ▼
      ┌─────────────┐
      │ PostgreSQL  │
      └─────────────┘
```

[See detailed architecture →](docs/plan/01-architecture.md)

---

## 💻 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11+ | Modern async features |
| Database | PostgreSQL 14+ | Robust data storage |
| DB Driver | psqlpy | High-performance async driver |
| Validation | Pydantic v2 | Type-safe data models |
| Async | asyncio | Native concurrency |
| Testing | pytest | Comprehensive testing |
| Packaging | Poetry | Dependency management |

---

## 🛠️ Development Status

**Current Phase:** ✅ v2.0.0 Released - Production Ready

### Implementation Timeline

```
Week 1-2:  Foundation, Database, One-Way Messaging    [Complete]
Week 3:    Synchronous Conversations                  [Complete]
Week 4:    Asynchronous Conversations                 [Complete]
Week 5-6:  Multi-Agent Meetings                       [Complete]
Week 7:    Core API, Error Handling, Testing          [Complete]
Week 8:    Testing & Quality Assurance                [Complete]
Week 9:    Documentation & Examples                   [Complete]
Week 10:   Major Refactoring (Architecture)           [Complete]
Week 11:   v2.0.0 Release (Dec 15, 2025)              [Complete]
```

**v2.0.0 Release Features:**
- Query methods for all message types
- Metadata support on all send operations
- Organization and agent de-registration
- Type-safe handler architecture with routing
- Comprehensive API documentation
- 162+ unit tests (100% pass rate)
- Fully backward compatible with v0.1.0

[See complete implementation plan →](docs/plan/00-implementation-plan.md)

---

## 🧪 Testing

Target test coverage: **80%+**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agent_messaging --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

[See testing strategy →](docs/plan/05-testing-strategy.md)

---

## 📊 Performance Goals

| Metric | Target | Notes |
|--------|--------|-------|
| Message Throughput | 1000+ msg/sec | One-way messages |
| Conversation Latency | <50ms | Excluding handler time |
| Concurrent Meetings | 100+ | Simultaneous meetings |
| Connection Pool | 10-20 | Configurable |
| Database Queries | <10ms | With proper indexes |

---

## 🤝 Contributing

**Status:** Accepting contributions (Phase 2 complete, Phase 3 in progress)

Once implementation begins, contributions will be welcome! Areas we'll need help:
- Core implementation
- Test coverage
- Documentation
- Example applications
- Performance optimization

---

## 📋 Requirements

### System Requirements

- Python 3.11 or higher
- PostgreSQL 14 or higher
- 2GB+ RAM (for development)
- Unix-like OS or Windows

### Python Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
psqlpy = "^0.11.0"
pydantic = "^2.0"
python-dotenv = "^1.0"
```

---

## 🔒 Security

- **No authentication built-in:** Users manage auth
- **SQL injection protected:** Parameterized queries only
- **Environment variables:** Sensitive data in .env
- **Advisory locks:** PostgreSQL-native locking

[Security considerations →](docs/plan/01-architecture.md#security-considerations)

---

## 📝 License

To be determined (suggested: MIT or Apache 2.0)

---

## 🙏 Acknowledgments

- **[psqlpy](https://github.com/qaspen-python/psqlpy)** - High-performance PostgreSQL driver
- **[Pydantic](https://pydantic.dev/)** - Data validation library
- **[PostgreSQL](https://www.postgresql.org/)** - Robust database system

---

## 📞 Contact & Support

- **Documentation:** [docs/](docs/)
- **Issues:** GitHub Issues (once repo is public)
- **Questions:** Discussion board or Slack

---

## 🗺️ Roadmap

### Phase 1: MVP (v0.1.0)
- [x] Complete planning documentation
- [x] Core infrastructure
- [x] All four messaging patterns
- [x] Basic error handling
- [x] Test coverage 80%+

### Phase 2: Production Ready (v0.2.0)
- [ ] Advanced error recovery
- [ ] Performance optimization
- [ ] Comprehensive examples
- [ ] API stability

### Phase 3: Enhanced Features (v0.3.0)
- [ ] Message persistence options
- [ ] Monitoring and metrics
- [ ] Advanced scheduling
- [ ] Web dashboard

---

## 🎓 Learn More

### Core Concepts

- **Organizations & Agents:** Entities stored with external IDs for reference
- **Message Types:** User-defined Pydantic models for type safety
- **Handlers:** Functions registered to process incoming messages
- **Sessions:** Managed conversations between agents
- **Meetings:** Coordinated multi-agent interactions
- **Events:** Extensibility hooks for meeting lifecycle

### When to Use Each Pattern

| Pattern | Use When |
|---------|----------|
| One-Way | Notifications, no response needed |
| Sync Conversation | Immediate response required |
| Async Conversation | Delayed response acceptable |
| Meeting | Multiple agents coordinate |

---

## 📈 Project Stats

- **Planning Documents:** 6 comprehensive guides
- **Total Tasks:** 100+ identified
- **Code Coverage Goal:** 80%+
- **Estimated LOC:** 5000-7000
- **Documentation Pages:** 2000+ lines

---
**Status:** Phase 10 Complete - Major Refactoring Complete

**Next Step:** Phase 11 - Packaging & Release
**Next Step:** Phase 10 - Packaging & Release

---

*Built with ❤️ for the AI agent community*
