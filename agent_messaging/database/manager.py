"""PostgreSQL database manager using psqlpy."""

import logging
from typing import Optional

from psqlpy import ConnectionPool

from ..config import DatabaseConfig
from ..exceptions import DatabaseError

logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """Manages PostgreSQL connection pool using psqlpy."""

    def __init__(self, config: DatabaseConfig):
        """Initialize the database manager.

        Args:
            config: Database configuration
        """
        self.config = config
        self.pool: Optional[ConnectionPool] = None

    async def initialize(self) -> None:
        """Initialize the connection pool.

        Raises:
            DatabaseError: If pool initialization fails
        """
        try:
            logger.info(f"Initializing PostgreSQL connection pool to {self.config.dsn}")
            self.pool = ConnectionPool(
                dsn=self.config.dsn,
                max_db_pool_size=self.config.max_pool_size,
                connect_timeout_sec=self.config.connect_timeout_sec,
            )
            logger.info("PostgreSQL connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise DatabaseError(f"Failed to initialize database connection pool: {e}") from e

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            logger.info("Closing PostgreSQL connection pool")
            self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")

    async def connection(self):
        """Get a database connection from the pool.

        Returns:
            Connection: psqlpy connection (async context manager)

        Raises:
            DatabaseError: If pool is not initialized or connection fails
        """
        if not self.pool:
            raise DatabaseError("Database pool not initialized. Call initialize() first.")

        try:
            return await self.pool.acquire()
        except Exception as e:
            logger.error(f"Failed to acquire database connection: {e}")
            raise DatabaseError(f"Failed to acquire database connection: {e}") from e

    def get_pool_status(self) -> dict:
        """Get current pool status.

        Returns:
            dict: Pool status information

        Raises:
            DatabaseError: If pool is not initialized
        """
        if not self.pool:
            raise DatabaseError("Database pool not initialized")

        try:
            status = self.pool.status()
            return {
                "max_size": status.max_size,
                "size": status.size,
                "available": status.available,
                "waiting": status.waiting,
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            raise DatabaseError(f"Failed to get pool status: {e}") from e
