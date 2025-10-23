"""Unit tests for configuration module."""

import os
import pytest
from unittest.mock import patch

from agent_messaging.config import Config, DatabaseConfig, MessagingConfig


class TestDatabaseConfig:
    """Test DatabaseConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.user == "postgres"
        assert config.password == "postgres"
        assert config.database == "agent_messaging"
        assert config.max_pool_size == 20
        assert config.min_pool_size == 5
        assert config.connect_timeout_sec == 10

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            user="testuser",
            password="testpass",
            database="testdb",
            max_pool_size=10,
            min_pool_size=2,
            connect_timeout_sec=5,
        )
        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.user == "testuser"
        assert config.password == "testpass"
        assert config.database == "testdb"
        assert config.max_pool_size == 10
        assert config.min_pool_size == 2
        assert config.connect_timeout_sec == 5

    def test_dsn_generation(self):
        """Test DSN string generation."""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            user="postgres",
            password="mypassword",
            database="agent_messaging",
        )
        expected_dsn = "postgres://postgres:mypassword@localhost:5432/agent_messaging"
        assert config.dsn == expected_dsn

    def test_dsn_with_special_characters(self):
        """Test DSN generation with special characters in password."""
        config = DatabaseConfig(user="user@domain", password="pass@word:123", database="test_db")
        dsn = config.dsn
        assert "user@domain" in dsn
        assert "pass@word:123" in dsn
        assert "test_db" in dsn

    def test_validation_positive_values(self):
        """Test validation of positive values."""
        config = DatabaseConfig(max_pool_size=0, min_pool_size=-1)
        # Pydantic should allow these, but they might not be sensible
        assert config.max_pool_size == 0
        assert config.min_pool_size == -1


class TestMessagingConfig:
    """Test MessagingConfig model."""

    def test_default_values(self):
        """Test default messaging configuration values."""
        config = MessagingConfig()
        assert config.default_sync_timeout == 30.0
        assert config.default_meeting_turn_duration == 60.0
        assert config.handler_timeout == 30.0

    def test_custom_values(self):
        """Test custom messaging configuration values."""
        config = MessagingConfig(
            default_sync_timeout=10.0, default_meeting_turn_duration=120.0, handler_timeout=15.0
        )
        assert config.default_sync_timeout == 10.0
        assert config.default_meeting_turn_duration == 120.0
        assert config.handler_timeout == 15.0

    def test_zero_timeouts_allowed(self):
        """Test that zero timeouts are allowed."""
        config = MessagingConfig(
            default_sync_timeout=0.0, default_meeting_turn_duration=0.0, handler_timeout=0.0
        )
        assert config.default_sync_timeout == 0.0
        assert config.default_meeting_turn_duration == 0.0
        assert config.handler_timeout == 0.0

    def test_negative_timeouts_allowed(self):
        """Test that negative timeouts are allowed (though not sensible)."""
        config = MessagingConfig(default_sync_timeout=-1.0)
        assert config.default_sync_timeout == -1.0


class TestConfig:
    """Test main Config class."""

    def test_default_values(self):
        """Test default main configuration values."""
        config = Config()
        assert config.debug is False
        assert config.log_level == "INFO"
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.messaging, MessagingConfig)

    def test_custom_values(self):
        """Test custom main configuration values."""
        db_config = DatabaseConfig(host="custom.host")
        msg_config = MessagingConfig(default_sync_timeout=15.0)

        config = Config(database=db_config, messaging=msg_config, debug=True, log_level="DEBUG")
        assert config.database.host == "custom.host"
        assert config.messaging.default_sync_timeout == 15.0
        assert config.debug is True
        assert config.log_level == "DEBUG"

    @patch.dict(
        os.environ,
        {
            "POSTGRES_HOST": "env.host",
            "POSTGRES_PORT": "5433",
            "POSTGRES_USER": "env_user",
            "POSTGRES_PASSWORD": "env_pass",
            "POSTGRES_DATABASE": "env_db",
            "POSTGRES_MAX_POOL_SIZE": "15",
            "MESSAGING_DEFAULT_SYNC_TIMEOUT": "20.0",
            "MESSAGING_DEFAULT_MEETING_TURN_DURATION": "90.0",
            "DEBUG": "true",
            "LOG_LEVEL": "WARNING",
        },
    )
    def test_environment_variables(self):
        """Test loading configuration from environment variables."""
        # Force reload of config to pick up environment changes
        from importlib import reload
        import agent_messaging.config

        reload(agent_messaging.config)
        from agent_messaging.config import Config

        config = Config()

        # Database config from env
        assert config.database.host == "env.host"
        assert config.database.port == 5433
        assert config.database.user == "env_user"
        assert config.database.password == "env_pass"
        assert config.database.database == "env_db"
        assert config.database.max_pool_size == 15

        # Messaging config from env
        assert config.messaging.default_sync_timeout == 20.0
        assert config.messaging.default_meeting_turn_duration == 90.0

        # Main config from env
        assert config.debug is True
        assert config.log_level == "WARNING"

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_environment(self):
        """Test configuration with no environment variables set."""
        config = Config()
        # Should use all defaults
        assert config.database.host == "localhost"
        assert config.database.port == 5432
        assert config.debug is False
        assert config.log_level == "INFO"

    def test_env_file_loading(self):
        """Test that .env file loading is optional and works when available."""
        # Since .env loading is now optional and handled at module level,
        # we test that Config can be instantiated without python-dotenv
        config = Config()
        # Config should work regardless of .env availability
        assert isinstance(config, Config)
        assert config.database.host == "localhost"  # default value

    def test_config_mutability(self):
        """Test that config objects are mutable (Pydantic default behavior)."""
        config = Config()
        original_debug = config.debug

        # Should be able to modify (Pydantic allows this)
        config.debug = not original_debug
        assert config.debug != original_debug

    def test_database_config_mutability(self):
        """Test that database config is mutable (Pydantic default behavior)."""
        db_config = DatabaseConfig()
        original_host = db_config.host

        # Should be able to modify (Pydantic allows this)
        db_config.host = "new.host"
        assert db_config.host != original_host
        assert db_config.host == "new.host"

    def test_dsn_property_caching(self):
        """Test that DSN property works correctly."""
        config = DatabaseConfig(
            host="test.host", port=9999, user="testuser", password="testpass", database="testdb"
        )

        dsn1 = config.dsn
        dsn2 = config.dsn

        # Should return the same value
        assert dsn1 == dsn2
        assert dsn1 == "postgres://testuser:testpass@test.host:9999/testdb"

    def test_config_equality(self):
        """Test configuration equality."""
        config1 = Config()
        config2 = Config()

        # Two default configs should be equal
        assert config1 == config2

        # Different configs should not be equal
        config3 = Config(debug=True)
        assert config1 != config3

    def test_config_not_hashable(self):
        """Test that configs are not hashable (Pydantic default behavior)."""
        config = Config()
        # Should not be able to hash (Pydantic models are mutable)
        with pytest.raises(TypeError):
            hash(config)

    def test_json_serialization(self):
        """Test that configs can be JSON serialized."""
        config = Config()
        json_str = config.model_dump_json()
        assert isinstance(json_str, str)
        assert "localhost" in json_str
        assert "agent_messaging" in json_str

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config should work
        config = Config()
        assert config is not None

        # Should handle edge cases gracefully
        config = Config(database=DatabaseConfig(), messaging=MessagingConfig())
        assert config.database is not None
        assert config.messaging is not None
