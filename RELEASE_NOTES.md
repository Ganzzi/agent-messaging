# Agent Messaging Protocol v0.1.0 - Release Notes

## 🎉 Welcome to Agent Messaging Protocol!

**Agent Messaging Protocol** is a production-ready Python SDK that enables AI agents to communicate naturally through human-like messaging patterns. Built with async-first architecture and PostgreSQL, it provides four distinct communication patterns that mirror real-world interactions.

## ✨ Key Features

### Four Communication Patterns

1. **📢 One-Way Messaging** - Fire-and-forget notifications and broadcasts
   - Send messages to single recipients or broadcast to multiple agents
   - Asynchronous delivery with guaranteed processing
   - Perfect for alerts, notifications, and status updates

2. **💬 Synchronous Conversations** - Blocking request-response dialogs
   - Send a message and wait for a response (with timeout)
   - Perfect for Q&A, approvals, and immediate feedback
   - Built-in coordination prevents race conditions

3. **📨 Asynchronous Conversations** - Non-blocking message queues
   - Send messages and check for responses later
   - Ideal for long-running tasks and background processing
   - Message queue pattern with conversation tracking

4. **🏛️ Multi-Agent Meetings** - Turn-based group coordination
   - Structured meetings with turn-based speaking
   - Automatic timeout handling (agents can't hold meetings hostage)
   - Event-driven architecture for extensibility

### 🏗️ Production-Ready Architecture

- **Type-Safe:** Full Pydantic v2 integration with generic message types
- **Async-First:** Complete asyncio/await support throughout
- **Database-Backed:** PostgreSQL with connection pooling and transactions
- **Resilient:** Comprehensive error handling and graceful degradation
- **Tested:** 134 comprehensive unit tests with 100% pass rate
- **Documented:** Complete API reference and working examples

## 🚀 Quick Start

```python
import asyncio
from agent_messaging import AgentMessaging

async def main():
    # Initialize SDK
    async with AgentMessaging[YourMessageType]() as sdk:
        # Register organization and agents
        await sdk.register_organization("my-org", "My Organization")
        await sdk.register_agent("alice", "my-org", "Alice")
        await sdk.register_agent("bob", "my-org", "Bob")

        # Register message handlers
        @sdk.register_handler("bob")
        async def bob_handler(message, context):
            return f"Hello {context.sender_id}, I received: {message.content}"

        # Send a synchronous conversation
        response = await sdk.conversation.send_and_wait(
            "alice", "bob", YourMessageType(content="Hi Bob!"),
            timeout=30.0
        )
        print(f"Bob replied: {response.content}")

asyncio.run(main())
```

## 📋 Requirements

- **Python:** 3.11 or higher
- **Database:** PostgreSQL 14+ with JSONB support
- **Memory:** Minimal (connection pooling, efficient queries)

## 📚 Documentation

- **API Reference:** Complete method documentation with examples
- **Usage Examples:** Four working examples covering all patterns
- **Quick Start Guide:** Get up and running in minutes
- **Architecture Guide:** Deep dive into design decisions

## 🔧 Installation

```bash
pip install agent-messaging
```

## 🎯 Use Cases

- **AI Agent Coordination:** Enable multiple AI agents to collaborate on tasks
- **Workflow Automation:** Build complex approval and review processes
- **Real-time Communication:** Create chat-like interfaces for AI systems
- **Distributed Processing:** Coordinate work across multiple AI workers
- **Meeting Facilitation:** Structured group discussions with AI participants

## 🛡️ Reliability & Performance

- **Concurrent:** Handles multiple simultaneous conversations and meetings
- **Scalable:** Connection pooling and efficient database queries
- **Timeout-Safe:** All operations have configurable timeouts
- **Error-Resilient:** Graceful handling of network issues and agent failures
- **Memory-Efficient:** Minimal memory footprint with proper cleanup

## 🤝 Contributing

We welcome contributions! The codebase is well-tested and documented. See CONTRIBUTING.md for guidelines.

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

Built with modern Python async patterns, inspired by human communication workflows, and designed for production AI agent systems.

---

**Ready to build communicating AI agents?** Check out the [documentation](https://agent-messaging.readthedocs.io/) and start building!