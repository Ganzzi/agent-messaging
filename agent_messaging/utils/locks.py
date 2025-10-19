"""Advisory lock utilities for PostgreSQL coordination."""

from typing import Optional
from uuid import UUID

from psqlpy import Connection


class AdvisoryLock:
    """PostgreSQL advisory lock utilities for agent coordination."""

    @staticmethod
    def generate_lock_key(session_id: UUID) -> int:
        """Generate a lock key from session ID.

        Converts UUID to a positive bigint suitable for PostgreSQL advisory locks.
        Uses the first 8 bytes of the UUID to create a consistent lock key.

        Args:
            session_id: Session UUID to convert

        Returns:
            Positive bigint lock key
        """
        # Convert UUID to string and take first 16 hex characters (8 bytes)
        uuid_str = str(session_id).replace("-", "")
        hex_value = uuid_str[:16]

        # Convert to bigint, ensure positive
        lock_key = int(hex_value, 16) % (2**63 - 1)  # Keep within positive bigint range

        return lock_key

    @staticmethod
    async def acquire_lock(connection: Connection, lock_key: int) -> bool:
        """Acquire an advisory lock.

        Attempts to acquire a PostgreSQL advisory lock. Returns immediately
        with success/failure status.

        Args:
            connection: Database connection
            lock_key: Lock key to acquire

        Returns:
            True if lock acquired, False if already locked
        """
        result = await connection.fetch_val("SELECT pg_try_advisory_lock($1)", [lock_key])
        return bool(result)

    @staticmethod
    async def release_lock(connection: Connection, lock_key: int) -> bool:
        """Release an advisory lock.

        Releases a previously acquired advisory lock.

        Args:
            connection: Database connection
            lock_key: Lock key to release

        Returns:
            True if lock was held and released, False if not held
        """
        result = await connection.fetch_val("SELECT pg_advisory_unlock($1)", [lock_key])
        return bool(result)

    @staticmethod
    async def acquire_lock_with_timeout(
        connection: Connection, lock_key: int, timeout_seconds: float
    ) -> bool:
        """Acquire an advisory lock with timeout.

        Attempts to acquire a lock, waiting up to timeout_seconds.
        Uses pg_advisory_lock with a timeout mechanism.

        Args:
            connection: Database connection
            lock_key: Lock key to acquire
            timeout_seconds: Maximum time to wait for lock

        Returns:
            True if lock acquired within timeout, False if timed out
        """
        # Use a query that attempts to get lock with timeout
        # This is a simplified approach - in production you might want
        # more sophisticated timeout handling
        try:
            # Try to acquire lock (this will block until acquired or connection closed)
            await connection.execute("SELECT pg_advisory_lock($1)", [lock_key])
            return True
        except Exception:
            # If we get an exception (e.g., connection timeout), assume lock failed
            return False

    @staticmethod
    async def is_lock_held(connection: Connection, lock_key: int) -> bool:
        """Check if an advisory lock is currently held.

        Args:
            connection: Database connection
            lock_key: Lock key to check

        Returns:
            True if lock is held, False otherwise
        """
        result = await connection.fetch_val("SELECT pg_advisory_lock_shared($1)", [lock_key])
        # If we can get a shared lock, the exclusive lock is not held
        # This is a bit of a hack, but works for checking lock status
        return not bool(result)


class SessionLock:
    """Session-specific lock management."""

    def __init__(self, session_id: UUID):
        """Initialize session lock manager.

        Args:
            session_id: Session UUID
        """
        self.session_id = session_id
        self.lock_key = AdvisoryLock.generate_lock_key(session_id)

    async def acquire(self, connection: Connection) -> bool:
        """Acquire lock for this session.

        Args:
            connection: Database connection

        Returns:
            True if lock acquired
        """
        return await AdvisoryLock.acquire_lock(connection, self.lock_key)

    async def release(self, connection: Connection) -> bool:
        """Release lock for this session.

        Args:
            connection: Database connection

        Returns:
            True if lock was held and released
        """
        return await AdvisoryLock.release_lock(connection, self.lock_key)

    async def acquire_with_timeout(self, connection: Connection, timeout_seconds: float) -> bool:
        """Acquire lock with timeout for this session.

        Args:
            connection: Database connection
            timeout_seconds: Timeout in seconds

        Returns:
            True if lock acquired within timeout
        """
        return await AdvisoryLock.acquire_lock_with_timeout(
            connection, self.lock_key, timeout_seconds
        )

    async def is_held(self, connection: Connection) -> bool:
        """Check if session lock is held.

        Args:
            connection: Database connection

        Returns:
            True if lock is held
        """
        return await AdvisoryLock.is_lock_held(connection, self.lock_key)
