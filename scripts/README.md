# Agent Messaging Protocol - Scripts

Utility scripts for development, testing, and database management.

## Scripts Overview

### 🗄️ `init_db.py`
Initialize the database schema from the migration file.

**Usage:**
```bash
uv run python scripts/init_db.py
```

**What it does:**
- Connects to PostgreSQL using config from `.env`
- Reads `migrations/001_initial_schema.sql`
- Creates all tables, indexes, triggers, and functions
- Shows progress for each database object created

**Requirements:**
- PostgreSQL running (use `start_postgres.py` to start)
- Valid `.env` configuration file

---

### 🐳 `start_postgres.py`
Manage PostgreSQL Docker container using docker-compose.

**Usage:**
```bash
# Start PostgreSQL container
uv run python scripts/start_postgres.py start

# Stop PostgreSQL container
uv run python scripts/start_postgres.py stop

# Check status
uv run python scripts/start_postgres.py status

# View logs
uv run python scripts/start_postgres.py logs
```

**What it does:**
- Manages Docker container lifecycle
- Uses `docker-compose.yml` from project root
- Waits for PostgreSQL to be ready after starting
- Shows connection details and next steps

**Requirements:**
- Docker installed and running
- docker-compose or docker compose plugin

---

### 🧪 `test_client.py`
Manual test client demonstrating all AgentMessaging features.

**Usage:**
```bash
uv run python scripts/test_client.py
```

**What it demonstrates:**
1. **One-Way Messaging** - Broadcast to multiple recipients
2. **Synchronous Conversations** - Request-response with blocking
3. **Asynchronous Conversations** - Non-blocking message queues
4. **Multi-Agent Meetings** - Turn-based coordination

**What it does:**
- Creates test organization and agents
- Registers shared message handler
- Tests all communication patterns
- Shows real-time output of message flow

**Requirements:**
- PostgreSQL running with initialized schema
- Valid `.env` configuration file

---

### 🧪 `run_tests.py`
Run the full test suite with automatic setup and coverage reporting.

**Usage:**
```bash
# Run all tests with full setup
uv run python scripts/run_tests.py

# Skip Docker/database setup (if already running)
uv run python scripts/run_tests.py --skip-setup

# Run without coverage report
uv run python scripts/run_tests.py --no-coverage

# Quiet mode (less verbose)
uv run python scripts/run_tests.py --quiet
```

**Options:**
- `--skip-setup` - Skip Docker and database initialization
- `--no-coverage` - Run tests without coverage report
- `--quiet`, `-q` - Less verbose output
- `--help`, `-h` - Show help message

**What it does:**
1. Checks Docker is running
2. Starts PostgreSQL container if needed
3. Initializes database schema
4. Runs pytest with coverage
5. Generates HTML coverage report
6. Shows summary of results

**Requirements:**
- Docker installed and running
- All Python dependencies installed (`uv sync`)

---

## Quick Start Workflow

### First Time Setup

```bash
# 1. Start PostgreSQL
uv run python scripts/start_postgres.py start

# 2. Initialize database schema
uv run python scripts/init_db.py

# 3. Run manual test client
uv run python scripts/test_client.py

# 4. Run full test suite4
uv run python scripts/run_tests.py
```

### Daily Development

```bash
# Run tests (auto-setup)
uv run python scripts/run_tests.py

# Test specific features manually
uv run python scripts/test_client.py

# Check PostgreSQL status
uv run python scripts/start_postgres.py status
```

### Cleanup

```bash
# Stop PostgreSQL container
uv run python scripts/start_postgres.py stop
```

---

## Environment Setup

Create a `.env` file in the project root:

```bash
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=agent_messaging

# Optional: Connection pooling
MAX_POOL_SIZE=20

# Optional: Timeouts (seconds)
DEFAULT_SYNC_TIMEOUT=30.0
DEFAULT_MEETING_TURN_DURATION=60.0
HANDLER_TIMEOUT=30.0
```

---

## Troubleshooting

### Docker Issues

**Problem:** Docker not running
```bash
# Check Docker status
docker ps

# Start Docker Desktop (Windows/Mac) or Docker daemon (Linux)
```

**Problem:** Port 5432 already in use
```bash
# Find process using port 5432
netstat -ano | findstr :5432  # Windows
lsof -i :5432                 # Mac/Linux

# Stop conflicting PostgreSQL instance or change port in docker-compose.yml
```

### Database Issues

**Problem:** Connection refused
```bash
# Check PostgreSQL is running
uv run python scripts/start_postgres.py status

# Check logs for errors
uv run python scripts/start_postgres.py logs

# Restart container
uv run python scripts/start_postgres.py stop
uv run python scripts/start_postgres.py start
```

**Problem:** Schema already exists
```bash
# Drop and recreate database (WARNING: destroys data)
docker exec -it agent_messaging_postgres psql -U postgres -c "DROP DATABASE agent_messaging;"
docker exec -it agent_messaging_postgres psql -U postgres -c "CREATE DATABASE agent_messaging;"
uv run python scripts/init_db.py
```

### Test Issues

**Problem:** Tests fail with import errors
```bash
# Install dependencies
uv sync

# Verify installation
uv run python -c "import agent_messaging; print('OK')"
```

**Problem:** Tests fail with database errors
```bash
# Reinitialize database
uv run python scripts/init_db.py

# Run tests with full setup
uv run python scripts/run_tests.py
```

---

## Development Tips

### Running Specific Tests

```bash
# Run specific test file
uv run pytest tests/test_conversation.py -v

# Run specific test function
uv run pytest tests/test_conversation.py::test_send_and_wait -v

# Run tests matching pattern
uv run pytest tests/ -k "conversation" -v
```

### Coverage Reports

```bash
# Generate coverage report
uv run pytest --cov=agent_messaging --cov-report=html

# Open report in browser
# Windows
start htmlcov/index.html

# Mac
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

### Database Inspection

```bash
# Connect to PostgreSQL
docker exec -it agent_messaging_postgres psql -U postgres -d agent_messaging

# List tables
\dt

# Describe table
\d agents

# Query data
SELECT * FROM agents;

# Exit
\q
```

---

## CI/CD Integration

These scripts are designed to work in CI/CD environments:

```yaml
# Example GitHub Actions workflow
steps:
  - uses: actions/checkout@v2
  
  - name: Set up Python
    uses: actions/setup-python@v2
    with:
      python-version: '3.11'
  
  - name: Install uv
    run: pip install uv
  
  - name: Install dependencies
    run: uv sync
  
  - name: Run tests
    run: uv run python scripts/run_tests.py
```

---

## Contributing

When adding new scripts:
1. Follow the naming convention: `action_noun.py`
2. Include `#!/usr/bin/env python3` shebang
3. Add docstring explaining purpose
4. Add error handling and user-friendly messages
5. Update this README with usage instructions
6. Support `--help` flag for command-line scripts

---

## License

See [LICENSE](../LICENSE) for the full license text.
