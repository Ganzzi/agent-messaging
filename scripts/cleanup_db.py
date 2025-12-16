#!/usr/bin/env python3
"""Clean up test data from database."""

import asyncio
from psqlpy import ConnectionPool


async def main():
    """Truncate all tables."""
    pool = ConnectionPool(dsn="postgres://postgres:postgres@localhost:5432/agent_messaging")

    try:
        print("Cleaning database...")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                TRUNCATE TABLE organizations, agents, sessions, meetings, 
                meeting_participants, messages, meeting_events CASCADE;
            """
            )
        print("✓ Database cleaned")
    finally:
        pool.close()


if __name__ == "__main__":
    asyncio.run(main())
