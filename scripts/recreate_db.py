#!/usr/bin/env python3
"""Drop and recreate the database with proper schema."""

import asyncio
from psqlpy import ConnectionPool


async def main():
    """Drop and recreate database."""
    print("Dropping and recreating database...")

    # Connect to postgres database to execute admin commands
    admin_pool = ConnectionPool(dsn="postgres://postgres:postgres@localhost:5432/postgres")

    try:
        # Drop existing connections and database
        print("\n1. Terminating existing connections...")
        async with admin_pool.acquire() as conn:
            await conn.execute(
                """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = 'agent_messaging'
                AND pid <> pg_backend_pid();
            """
            )
        print("   ✓ Connections terminated")

        # Drop database
        print("\n2. Dropping database...")
        async with admin_pool.acquire() as conn:
            await conn.execute("DROP DATABASE IF EXISTS agent_messaging;")
        print("   ✓ Database dropped")

        # Create database
        print("\n3. Creating database...")
        async with admin_pool.acquire() as conn:
            await conn.execute("CREATE DATABASE agent_messaging;")
        print("   ✓ Database created")

        print("\n✓ Database recreated successfully")
        print("\nNow run: uv run python scripts/init_db.py")
        return True

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        admin_pool.close()


if __name__ == "__main__":
    result = asyncio.run(main())
    import sys

    sys.exit(0 if result else 1)
