"""Base repository class for database operations."""

import logging
from typing import Any, Dict, List, Optional

from psqlpy import Connection

from ...exceptions import DatabaseError

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all repository implementations."""

    def __init__(self, pool: Any):
        """Initialize repository with connection pool.

        Args:
            pool: psqlpy ConnectionPool instance
        """
        self.pool = pool

    async def _execute(self, query: str, params: Optional[List[Any]] = None) -> Any:
        """Execute a query and return the result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            QueryResult from psqlpy

        Raises:
            DatabaseError: If query execution fails
        """
        async with self.pool.acquire() as connection:
            try:
                result = await connection.execute(query, params or [])
                return result
            except Exception as e:
                logger.error(f"Query execution failed: {query} with params {params}")
                raise DatabaseError(f"Database query failed: {e}") from e

    async def _fetch_one(
        self, query: str, params: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a query and return a single row.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row as dict, or None if no results

        Raises:
            DatabaseError: If query execution fails
        """
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetch_row(query, params or [])
                return result.result() if result else None
            except Exception as e:
                logger.error(f"Query fetch_one failed: {query} with params {params}")
                raise DatabaseError(f"Database query failed: {e}") from e

    async def _fetch_all(
        self, query: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return all rows.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows as dicts

        Raises:
            DatabaseError: If query execution fails
        """
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetch(query, params or [])
                return result.result()
            except Exception as e:
                logger.error(f"Query fetch_all failed: {query} with params {params}")
                raise DatabaseError(f"Database query failed: {e}") from e

    async def _fetch_val(self, query: str, params: Optional[List[Any]] = None) -> Any:
        """Execute a query and return a single value.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single value from the query

        Raises:
            DatabaseError: If query execution fails
        """
        async with self.pool.acquire() as connection:
            try:
                result = await connection.fetch_val(query, params or [])
                return result
            except Exception as e:
                logger.error(f"Query fetch_val failed: {query} with params {params}")
                raise DatabaseError(f"Database query failed: {e}") from e
