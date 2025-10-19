# Contributing to Agent Messaging Protocol

Thank you for your interest in contributing to the Agent Messaging Protocol! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome all skill levels
- Focus on constructive feedback
- Help others succeed

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Poetry
- Git

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/agent-messaging.git
cd agent-messaging

# Install dependencies
poetry install

# Create database
psql -U postgres -c "CREATE DATABASE agent_messaging_dev;"

# Initialize schema
psql -U postgres -d agent_messaging_dev -f migrations/001_initial_schema.sql

# Copy environment template
cp .env.example .env
# Edit .env with your settings
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive names:
- `feature/one-way-messaging`
- `fix/connection-pool-leak`
- `docs/api-reference`
- `test/meeting-concurrency`

### 2. Make Changes

- Follow PEP 8 style guide
- Write tests alongside code
- Add docstrings to public methods
- Use type hints throughout

### 3. Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=agent_messaging

# Run specific test
poetry run pytest tests/test_repositories.py
```

### 4. Code Quality

```bash
# Format code
poetry run black agent_messaging tests

# Lint code
poetry run ruff check agent_messaging tests

# Type check
poetry run mypy agent_messaging
```

### 5. Commit Changes

```bash
# Use clear commit messages
git commit -m "feat: implement one-way messaging system"
git commit -m "fix: connection pool cleanup on shutdown"
git commit -m "docs: add database schema documentation"
git commit -m "test: add concurrent meeting tests"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `perf:` - Performance improvement

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Create PR with:
- Clear title describing changes
- Description of what/why/how
- Reference related issues (#123)
- Link to any relevant documentation

## Testing Guidelines

### Unit Tests

```python
# Test a single component in isolation
def test_organization_repository_create():
    """Test creating an organization."""
    # Arrange
    repo = OrganizationRepository(mock_pool)
    
    # Act
    org_id = await repo.create("org_001", "Test Org")
    
    # Assert
    assert org_id is not None
```

### Integration Tests

```python
# Test components working together
@pytest.mark.asyncio
async def test_one_way_messaging():
    """Test sending one-way message end-to-end."""
    async with AgentMessaging() as sdk:
        # Setup
        await sdk.register_organization("org", "Test")
        await sdk.register_agent("alice", "org", "Alice")
        
        # Execute
        msg_id = await sdk.one_way.send(...)
        
        # Verify
        assert msg_id is not None
```

### Test Coverage

- Target: 80%+ overall coverage
- All public methods should have tests
- Test both happy path and error cases
- Test edge cases and boundary conditions

## Documentation

### Docstrings

```python
async def send_message(
    self,
    from_agent_id: str,
    to_agent_id: str,
    message: T,
) -> UUID:
    """Send a one-way message.
    
    Args:
        from_agent_id: Sender's external ID
        to_agent_id: Recipient's external ID
        message: Message content
        
    Returns:
        UUID of the created message
        
    Raises:
        AgentNotFoundError: If agent doesn't exist
        NoHandlerRegisteredError: If no handler registered
    """
```

### Comments

Use comments to explain *why*, not *what*:

```python
# Good
# Use UUID ordering to ensure consistent session IDs regardless of agent registration order
if agent_a_id > agent_b_id:
    agent_a_id, agent_b_id = agent_b_id, agent_a_id

# Avoid
# Swap the IDs
agent_a_id, agent_b_id = agent_b_id, agent_a_id
```

## Updating CHECKLIST.md

When completing work on a phase:

1. Update the checklist with completion status
2. Mark completed items with [x]
3. Update progress percentage
4. Document any blockers or notes

Example:
```markdown
## Phase 1: Foundation (Complete)

### 1.1 Project Structure
- [x] Create `agent_messaging/` package directory
- [x] Create `agent_messaging/__init__.py`
- [x] Create `agent_messaging/config.py`

**Phase 1 Progress:** 100% (25/25 items complete)
```

## Pull Request Process

1. **Before Submitting**
   - [ ] All tests passing (`poetry run pytest`)
   - [ ] Code formatted (`poetry run black`)
   - [ ] Linting clean (`poetry run ruff check`)
   - [ ] Type checking passes (`poetry run mypy`)
   - [ ] Docstrings added
   - [ ] Changelog updated

2. **PR Description**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation
   
   ## Related Issues
   Fixes #123
   
   ## Testing
   How to test the changes
   
   ## Checklist
   - [ ] Tests pass
   - [ ] Documentation updated
   - [ ] CHECKLIST.md updated
   ```

3. **Review Process**
   - Code review required
   - Tests must pass
   - Maintainer approval required

## Reporting Issues

### Bug Reports

Include:
- Python version
- PostgreSQL version
- Reproducible example
- Expected vs actual behavior
- Error traceback

### Feature Requests

Include:
- Clear description of feature
- Motivation/use case
- Proposed implementation (optional)
- Examples of how it would be used

## Release Process

Only maintainers can release, but contributors help by:

1. Testing pre-release versions
2. Reporting issues early
3. Updating CHANGELOG.md
4. Reviewing release notes

## Performance Considerations

When contributing code that might affect performance:

1. Benchmark before and after
2. Consider connection pool implications
3. Think about database query efficiency
4. Document performance implications

## Security

- Never commit secrets or credentials
- Use environment variables for sensitive data
- Report security issues privately to maintainers
- No security-critical code in public issues

## Questions?

- Check existing documentation
- Search GitHub issues
- Open a discussion
- Email maintainers

## Recognition

Contributors are recognized in:
- CHANGELOG.md
- GitHub contributors page
- Release notes

Thank you for contributing! 🎉
