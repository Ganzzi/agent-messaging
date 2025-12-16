"""Configuration module for Agent Messaging Protocol SDK.

Supports three configuration methods:
1. Direct Python instantiation (recommended for PyPI installs)
2. Environment variables (recommended for Docker/Kubernetes)
3. .env file (convenient for local development only)

The .env file loading is optional and only attempted if python-dotenv is available.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field

# Optional .env loading - only if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, just use environment variables
    pass


class DatabaseConfig(BaseModel):
    """Database connection configuration.

    Supports environment variables with POSTGRES_ prefix and .env file loading.
    Environment variables take precedence over defaults.
    """

    host: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"),
        description="PostgreSQL host",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")),
        description="PostgreSQL port",
    )
    user: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"),
        description="PostgreSQL username",
    )
    password: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "postgres"),
        description="PostgreSQL password",
    )
    database: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_DATABASE", "agent_messaging"),
        description="Database name",
    )
    max_pool_size: int = Field(
        default_factory=lambda: int(os.getenv("POSTGRES_MAX_POOL_SIZE", "20")),
        description="Maximum connection pool size",
    )
    min_pool_size: int = Field(
        default_factory=lambda: int(os.getenv("POSTGRES_MIN_POOL_SIZE", "5")),
        description="Minimum connection pool size",
    )
    connect_timeout_sec: int = Field(
        default_factory=lambda: int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SEC", "10")),
        description="Connection timeout in seconds",
    )

    @property
    def dsn(self) -> str:
        """Generate PostgreSQL DSN string."""
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class MessagingConfig(BaseModel):
    """Messaging behavior configuration.

    Supports environment variables with MESSAGING_ prefix and .env file loading.
    Environment variables take precedence over defaults.
    """

    default_sync_timeout: float = Field(
        default_factory=lambda: float(os.getenv("MESSAGING_DEFAULT_SYNC_TIMEOUT", "30.0")),
        description="Default timeout for sync conversations (seconds)",
    )
    default_meeting_turn_duration: float = Field(
        default_factory=lambda: float(os.getenv("MESSAGING_DEFAULT_MEETING_TURN_DURATION", "60.0")),
        description="Default turn duration in meetings (seconds)",
    )
    handler_timeout: float = Field(
        default_factory=lambda: float(os.getenv("MESSAGING_HANDLER_TIMEOUT", "30.0")),
        description="Timeout for message handlers (seconds)",
    )


class Config(BaseModel):
    """Main configuration class for Agent Messaging Protocol SDK.

    This class provides type-safe configuration management and supports three
    initialization patterns:

    **Pattern 1: Direct Python (Recommended for PyPI users)**
    ```python
    from agent_messaging import AgentMessaging, Config

    config = Config(
        database=DatabaseConfig(
            host="localhost",
            port=5432,
            user="postgres",
            password="mypassword",
            database="agent_messaging"
        ),
        messaging=MessagingConfig(
            default_sync_timeout=30.0,
            default_meeting_turn_duration=60.0,
            handler_timeout=30.0
        ),
        debug=False,
        log_level="INFO"
    )

    async with AgentMessaging[dict](config=config) as sdk:
        # Use SDK with custom config
        pass
    ```

    **Pattern 2: Environment Variables (Recommended for Docker/K8s)**
    ```bash
    export POSTGRES_HOST=postgres
    export POSTGRES_PASSWORD=secure_pass
    export MESSAGING_DEFAULT_SYNC_TIMEOUT=60.0
    export DEBUG=false
    python your_app.py
    ```
    ```python
    from agent_messaging import AgentMessaging

    async with AgentMessaging[dict]() as sdk:  # Uses environment variables
        pass
    ```

    **Pattern 3: .env File (Convenient for local development)**
    ```bash
    # Install dev dependencies for .env support
    pip install agent-messaging[dev]

    # Create .env file
    echo "POSTGRES_HOST=localhost" > .env
    echo "POSTGRES_PASSWORD=devpass" >> .env
    echo "DEBUG=true" >> .env
    ```
    ```python
    from agent_messaging import AgentMessaging

    async with AgentMessaging[dict]() as sdk:  # Automatically loads .env file
        pass
    ```
    """

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    auto_initialize_schema: bool = Field(
        default_factory=lambda: os.getenv("AUTO_INITIALIZE_SCHEMA", "true").lower() == "true",
        description="Automatically initialize database schema on SDK initialization (idempotent)",
    )

    def __init__(self, **data):
        """Initialize Config, allowing field overrides while respecting environment variables."""
        # If fields aren't explicitly provided, they'll use the default_factory functions
        super().__init__(**data)


# Global config instance (for backward compatibility)
# This is optional - the recommended pattern is to pass Config directly
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Config: The global configuration instance

    Raises:
        RuntimeError: If no global configuration has been set
    """
    if _config is None:
        raise RuntimeError(
            "No global configuration set. Either:\n"
            "1. Pass config directly: AgentMessaging(config=Config(...))\n"
            "2. Set global config: set_config(Config(...))\n"
            "3. Use environment variables (automatic)"
        )
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance.

    Args:
        config: Configuration instance to set as global
    """
    global _config
    _config = config
