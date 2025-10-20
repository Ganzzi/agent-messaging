"""Configuration module for Agent Messaging Protocol SDK."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    user: str = Field(default="postgres", description="PostgreSQL username")
    password: str = Field(default="postgres", description="PostgreSQL password")
    database: str = Field(default="agent_messaging", description="Database name")
    max_pool_size: int = Field(default=20, description="Maximum connection pool size")
    min_pool_size: int = Field(default=5, description="Minimum connection pool size")
    connect_timeout_sec: int = Field(default=10, description="Connection timeout in seconds")

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    @property
    def dsn(self) -> str:
        """Generate PostgreSQL DSN string."""
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class MessagingConfig(BaseSettings):
    """Messaging behavior configuration."""

    default_sync_timeout: float = Field(
        default=30.0, description="Default timeout for sync conversations (seconds)"
    )
    default_meeting_turn_duration: float = Field(
        default=60.0, description="Default turn duration in meetings (seconds)"
    )
    handler_timeout: float = Field(
        default=30.0, description="Timeout for message handlers (seconds)"
    )

    model_config = SettingsConfigDict(env_prefix="MESSAGING_")


class Config(BaseSettings):
    """Main configuration class using environment variables."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        """Pydantic settings configuration."""

        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables


# Global configuration instance
config = Config()
