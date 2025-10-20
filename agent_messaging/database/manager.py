"""PostgreSQL database manager using psqlpy."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from psqlpy import Connection, ConnectionPool

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

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Connection, None]:
        """Get a connection from the pool (context manager).

        Usage:
            async with db_manager.connection() as conn:
                result = await conn.execute("SELECT * FROM table")

        Yields:
            Connection from the pool

        Raises:
            DatabaseError: If pool is not initialized or connection fails
        """
        if not self.pool:
            raise DatabaseError("Database pool not initialized. Call initialize() first.")

        try:
            conn: Connection = await self.pool.connection()
            try:
                yield conn
            finally:
                # Connection is automatically returned to pool when context exits
                pass
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
