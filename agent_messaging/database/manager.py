"""PostgreSQL database manager using psqlpy."""

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
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

    async def initialize_schema(self) -> None:
        """Initialize database schema from migrations (idempotent).

        Reads and executes all migration files in order. Uses IF NOT EXISTS
        and other idempotent SQL patterns, so this is safe to call multiple times.

        Raises:
            DatabaseError: If schema initialization fails
        """
        if not self.pool:
            raise DatabaseError("Database pool not initialized. Call initialize() first.")

        try:
            migrations_dir = Path(__file__).parent.parent.parent / "migrations"
            migration_files = sorted(migrations_dir.glob("*.sql"))

            if not migration_files:
                logger.warning("No migration files found in migrations directory")
                return

            logger.info(f"Initializing database schema from {len(migration_files)} migration(s)")

            for migration_file in migration_files:
                logger.info(f"Executing migration: {migration_file.name}")

                with open(migration_file, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # Parse and execute statements
                statements = self._parse_sql_statements(sql_content)

                async with self.connection() as conn:
                    for statement in statements:
                        if not statement.strip():
                            continue

                        try:
                            await conn.execute(statement)
                        except Exception as e:
                            error_str = str(e).lower()
                            # Ignore expected errors (table already exists, etc.)
                            if (
                                "already exists" not in error_str
                                and "does not exist" not in error_str
                            ):
                                logger.warning(f"Warning during schema init: {e}")

                logger.info(f"✅ Completed migration: {migration_file.name}")

            logger.info("✅ Database schema initialization complete")

        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise DatabaseError(f"Failed to initialize database schema: {e}") from e

    @staticmethod
    def _parse_sql_statements(sql_content: str) -> list[str]:
        """Parse SQL file into individual statements, handling dollar-quoted strings.

        Handles:
        - Multi-line statements
        - Dollar-quoted strings ($$...$$ or $name$...$name$)
        - Comments (-- and /* */)

        Returns:
            List of SQL statements
        """
        statements = []
        sql_content = sql_content.strip()

        i = 0
        current_statement = []
        in_dollar_quote = False
        dollar_marker = None

        while i < len(sql_content):
            # Check for dollar-quoted string markers
            if sql_content[i] == "$":
                j = i + 1
                while j < len(sql_content) and sql_content[j] not in "$\n":
                    if not (sql_content[j].isalnum() or sql_content[j] == "_"):
                        break
                    j += 1

                if j < len(sql_content) and sql_content[j] == "$":
                    marker = sql_content[i : j + 1]

                    if not in_dollar_quote:
                        dollar_marker = marker
                        in_dollar_quote = True
                        current_statement.append(marker)
                        i = j + 1
                        continue
                    elif marker == dollar_marker:
                        current_statement.append(marker)
                        in_dollar_quote = False
                        dollar_marker = None
                        i = j + 1
                        continue

            # Check for statement terminator (semicolon outside dollar quotes)
            if sql_content[i] == ";" and not in_dollar_quote:
                current_statement.append(";")
                stmt = "".join(current_statement).strip()

                # Filter out lines that are just comments
                lines = stmt.split("\n")
                non_comment_lines = [
                    line for line in lines if line.strip() and not line.strip().startswith("--")
                ]

                if non_comment_lines:
                    statements.append(stmt)

                current_statement = []
                i += 1
                continue

            current_statement.append(sql_content[i])
            i += 1

        return statements

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
