"""Base repository class for database operations."""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..manager import PostgreSQLManager

from ...exceptions import DatabaseError

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all repository implementations."""

    def __init__(self, db_manager: "PostgreSQLManager"):
        """Initialize repository with database manager.

        Args:
            db_manager: PostgreSQLManager instance
        """
        self.db_manager = db_manager

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
        async with self.db_manager.connection() as conn:
            try:
                result = await conn.execute(query, params or [])
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
        async with self.db_manager.connection() as conn:
            try:
                result = await conn.execute(query, params or [])
                rows = result.result()
                return rows[0] if rows else None
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
        async with self.db_manager.connection() as conn:
            try:
                result = await conn.execute(query, params or [])
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
        async with self.db_manager.connection() as conn:
            try:
                result = await conn.execute(query, params or [])
                rows = result.result()
                if rows and len(rows) > 0:
                    # Get first value of first row
                    first_row = rows[0]
                    if isinstance(first_row, dict) and first_row:
                        return next(iter(first_row.values()))
                return None
            except Exception as e:
                logger.error(f"Query fetch_val failed: {query} with params {params}")
                raise DatabaseError(f"Database query failed: {e}") from e
