
# PostgreSQL Manager Example

```python
"""
PostgreSQL connection management using PSQLPy.

Provides connection pool management for the context_bridge package.
"""

import asyncio
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from psqlpy import ConnectionPool, Connection

from context_bridge.config import Config


logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """
    PostgreSQL connection manager for context_bridge.

    Manages connection pool lifecycle and provides connections
    for repository operations.
    """

    def __init__(self, config: Config):
        """
        Initialize PostgreSQL manager.

        Args:
            config: Configuration object with database settings
        """
        self.config = config
        self._pool: Optional[ConnectionPool] = None
        self._initialized = False

        # Build DSN from config
        self.dsn = (
            f"postgresql://{config.postgres_user}:{config.postgres_password}"
            f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

        logger.info(
            f"PostgreSQL manager configured for {config.postgres_host}:{config.postgres_port}/{config.postgres_db}"
        )

    async def initialize(self) -> None:
        """Initialize the connection pool with retry logic."""
        if self._initialized:
            logger.warning("PostgreSQL manager already initialized")
            return

        max_retries = 5
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                if self._pool is None:
                    self._pool = ConnectionPool(
                        dsn=self.dsn,
                        max_db_pool_size=self.config.postgres_max_pool_size,
                    )
                    self._initialized = True
                    logger.info(
                        f"PostgreSQL connection pool initialized (max_size={self.config.postgres_max_pool_size})"
                    )
                    return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to initialize PostgreSQL connection pool after {max_retries} attempts: {e}"
                    )
                    raise

                delay = base_delay * (2**attempt)  # Exponential backoff
                logger.warning(
                    f"Failed to initialize PostgreSQL connection pool (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

    async def health_check(self) -> bool:
        """Verify database connectivity and return health status."""
        if not self._initialized or not self._pool:
            logger.warning("PostgreSQL manager not initialized")
            return False

        try:
            async with self.connection() as conn:
                result = await conn.execute("SELECT 1 as health")
                rows = result.result()
                # PSQLPy returns results as list of dicts with column names as keys
                if rows and len(rows) > 0 and rows[0].get("health") == 1:
                    logger.debug("PostgreSQL health check passed")
                    return True
                else:
                    logger.error(f"PostgreSQL health check failed: unexpected result {rows}")
                    return False
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    def log_pool_stats(self) -> None:
        """Log current connection pool statistics."""
        if not self._initialized or not self._pool:
            logger.warning("PostgreSQL manager not initialized - cannot log pool stats")
            return

        # Note: PSQLPy doesn't expose detailed pool statistics directly
        # We can log basic info about the pool state
        pool_status = "initialized" if self._initialized else "not initialized"
        logger.info(
            f"PostgreSQL connection pool status: {pool_status}, max_size={self.config.postgres_max_pool_size}"
        )

    async def close(self) -> None:
        """Close the connection pool and clean up resources gracefully."""
        if not self._pool:
            logger.debug("PostgreSQL connection pool already closed")
            return

        try:
            # Log final stats before closing
            self.log_pool_stats()

            # Close the pool with timeout handling
            # Note: PSQLPy's close() is synchronous, but we'll wrap it for future async support
            self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("PostgreSQL connection pool closed gracefully")

        except Exception as e:
            logger.error(f"Error during PostgreSQL connection pool shutdown: {e}")
            # Ensure state is cleaned up even on error
            self._pool = None
            self._initialized = False
            raise

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Connection, None]:
        """
        Get a connection from the pool (context manager).

        Usage:
            async with manager.connection() as conn:
                result = await conn.execute("SELECT * FROM table")

        Yields:
            Connection from the pool
        """
        if not self._initialized or not self._pool:
            raise RuntimeError("PostgreSQL manager not initialized. Call initialize() first.")

        conn: Connection = await self._pool.connection()
        try:
            yield conn
        finally:
            # Connection is automatically returned to pool when context exits
            pass

    async def execute(self, query: str, parameters: Optional[list] = None):
        """
        Execute a query using a connection from the pool.

        Args:
            query: SQL query to execute
            parameters: Query parameters (optional)

        Returns:
            Query result
        """
        async with self.connection() as conn:
            return await conn.execute(query, parameters or [])

    async def execute_transaction(self, operations: list) -> None:
        """
        Execute multiple operations in a transaction with rollback support.

        Args:
            operations: List of tuples (query, parameters) to execute

        Raises:
            Exception: If any operation fails, transaction is rolled back
        """
        if not self._initialized or not self._pool:
            raise RuntimeError("PostgreSQL manager not initialized. Call initialize() first.")

        async with self.connection() as conn:
            try:
                # Start transaction
                await conn.execute("BEGIN")

                for query, parameters in operations:
                    await conn.execute(query, parameters or [])

                # Commit transaction
                await conn.execute("COMMIT")
                logger.debug(
                    f"Transaction completed successfully with {len(operations)} operations"
                )

            except Exception as e:
                # Rollback on error
                try:
                    await conn.execute("ROLLBACK")
                    logger.warning("Transaction rolled back due to error")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")

                logger.error(f"Transaction failed: {e}")
                raise

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
```

## Usage Example

```python
from typing import Optional, List
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from context_bridge.database.postgres_manager import PostgreSQLManager


logger = logging.getLogger(__name__)


class Document(BaseModel):
    id: int
    name: str
    version: str
    source_url: Optional[str] = None
    description: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentRepository:
    def __init__(self, db_manager: PostgreSQLManager):
        """
        Initialize document repository.

        Args:
            db_manager: PostgreSQL connection manager
        """
        self.db_manager = db_manager
        logger.debug("DocumentRepository initialized")

    async def create(
        self,
        name: str,
        version: str,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        try:
            # Use PSQLPy parameter binding with $1, $2, etc.
            query = """
                INSERT INTO documents (name, version, source_url, description, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(
                    query, [name, version, source_url, description, metadata or {}]
                )
                rows = result.result()
                if rows:
                    doc_id = rows[0]["id"]  # PSQLPy returns dicts
                    logger.info(f"Created document '{name}' v{version} with ID {doc_id}")
                    return doc_id
                else:
                    raise RuntimeError(f"Failed to create document '{name}' v{version}")
        except Exception as e:
            logger.error(f"Failed to create document '{name}' v{version}: {e}")
            raise

    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        try:
            query = """
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                WHERE id = $1
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [doc_id])
                rows = result.result()
                if rows:
                    doc = self._row_to_document(rows[0])
                    logger.debug(f"Retrieved document ID {doc_id}: '{doc.name}' v{doc.version}")
                    return doc
                logger.debug(f"Document ID {doc_id} not found")
                return None
        except Exception as e:
            logger.error(f"Failed to get document by ID {doc_id}: {e}")
            raise

    async def list_all(self, offset: int = 0, limit: int = 100) -> List[Document]:
        try:
            query = """
                SELECT id, name, version, source_url, description, metadata, created_at, updated_at
                FROM documents
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [limit, offset])
                rows = result.result()
                documents = [self._row_to_document(row) for row in rows]
                logger.debug(f"Listed {len(documents)} documents (offset={offset}, limit={limit})")
                return documents
        except Exception as e:
            logger.error(f"Failed to list documents (offset={offset}, limit={limit}): {e}")
            raise

    async def update(self, doc_id: int, **fields) -> bool:
        try:
            if not fields:
                logger.warning(f"Update called on document {doc_id} with no fields")
                return False

            # Build dynamic update query with proper parameter binding
            set_parts = []
            values = []
            param_count = 1

            allowed_fields = ["name", "version", "source_url", "description", "metadata"]
            for field, value in fields.items():
                if field in allowed_fields:
                    set_parts.append(f"{field} = ${param_count}")
                    values.append(value)
                    param_count += 1
                else:
                    logger.warning(f"Ignoring invalid field '{field}' in update")

            if not set_parts:
                logger.warning(f"No valid fields to update for document {doc_id}")
                return False

            set_clause = ", ".join(set_parts)
            query = f"""
                UPDATE documents
                SET {set_clause}, updated_at = NOW()
                WHERE id = ${param_count}
            """
            values.append(doc_id)

            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, values)
                # PSQLPy result contains string representation like "UPDATE 1" or "UPDATE 0"
                result_str = str(result.result())
                affected = "UPDATE 0" not in result_str and result.result() != 0
                if affected:
                    logger.info(f"Updated document {doc_id} with fields: {list(fields.keys())}")
                else:
                    logger.warning(f"No rows affected when updating document {doc_id}")
                return affected
        except Exception as e:
            logger.error(
                f"Failed to update document {doc_id} with fields {list(fields.keys())}: {e}"
            )
            raise

    async def delete(self, doc_id: int) -> bool:
        try:
            query = "DELETE FROM documents WHERE id = $1"
            async with self.db_manager.connection() as conn:
                result = await conn.execute(query, [doc_id])
                # PSQLPy result contains string representation like "DELETE 1" or "DELETE 0"
                result_str = str(result.result())
                deleted = "DELETE 0" not in result_str and result.result() != 0
                if deleted:
                    logger.info(f"Deleted document ID {doc_id}")
                else:
                    logger.warning(f"No document found with ID {doc_id} to delete")
                return deleted
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            raise

    def _row_to_document(self, row: dict) -> Document:
        return Document(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            source_url=row.get("source_url"),
            description=row.get("description"),
            metadata=row.get("metadata") or {},  # Ensure empty dict if NULL
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

```