#!/usr/bin/env python3
"""Initialize database schema for Agent Messaging Protocol.

This script reads the migration file and executes it against the configured
PostgreSQL database using psqlpy connection.
"""

import asyncio
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_messaging.config import Config
from agent_messaging.database.manager import PostgreSQLManager


def _parse_sql_statements(sql_content: str) -> list[str]:
    """Parse SQL file into individual statements, handling dollar-quoted strings.

    This properly handles:
    - Multi-line statements
    - Dollar-quoted strings (used in functions): $$ ... $$
    - Comments
    """
    statements = []
    # Remove leading/trailing whitespace
    sql_content = sql_content.strip()

    i = 0
    current_statement = []
    in_dollar_quote = False
    dollar_marker = None

    while i < len(sql_content):
        # Check for dollar-quoted string markers like $$ or $name$
        if sql_content[i] == "$":
            # Find the end of the marker
            j = i + 1
            while j < len(sql_content) and sql_content[j] not in "$\n":
                if not (sql_content[j].isalnum() or sql_content[j] == "_"):
                    break
                j += 1

            if j < len(sql_content) and sql_content[j] == "$":
                # We found a complete marker
                marker = sql_content[i : j + 1]

                if not in_dollar_quote:
                    # Starting a dollar-quoted string
                    dollar_marker = marker
                    in_dollar_quote = True
                    current_statement.append(marker)
                    i = j + 1
                    continue
                elif marker == dollar_marker:
                    # Ending a dollar-quoted string
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


async def init_database():
    """Initialize the database schema."""
    print("🗄️  Agent Messaging Protocol - Database Initialization")
    print("=" * 60)

    # Load configuration
    config = Config()
    print(f"\n📋 Configuration:")
    print(f"   Host: {config.database.host}")
    print(f"   Port: {config.database.port}")
    print(f"   Database: {config.database.database}")
    print(f"   User: {config.database.user}")

    # Read migration file
    migration_file = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"
    print(f"\n📄 Reading migration file: {migration_file}")

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False

    with open(migration_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    print(f"   Read {len(schema_sql)} characters")

    # Initialize database manager
    print(f"\n🔌 Connecting to database...")
    db_manager = PostgreSQLManager(config.database)

    try:
        await db_manager.initialize()
        print("   ✅ Connected successfully")

        # Execute schema
        print(f"\n⚙️  Executing schema migration...")
        async with db_manager.connection() as conn:
            # Parse statements
            statements = _parse_sql_statements(schema_sql)

            for statement in statements:
                # Skip empty statements
                if not statement.strip():
                    continue

                try:
                    await conn.execute(statement)

                    # Print progress for major operations
                    upper_stmt = statement.upper()

                    if "CREATE TABLE" in upper_stmt:
                        # Extract table name using regex
                        match = re.search(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)", upper_stmt)
                        if match:
                            table_name = match.group(1)
                            print(f"   ✅ Created table: {table_name}")
                    elif "CREATE INDEX" in upper_stmt:
                        match = re.search(r"CREATE INDEX\s+(?:IF NOT EXISTS\s+)?(\w+)", upper_stmt)
                        if match:
                            idx_name = match.group(1)
                            print(f"   ✅ Created index: {idx_name}")
                    elif "CREATE EXTENSION" in upper_stmt:
                        match = re.search(
                            r'CREATE EXTENSION\s+(?:IF NOT EXISTS\s+)?"?(\w+)"?',
                            upper_stmt,
                        )
                        if match:
                            ext_name = match.group(1)
                            print(f"   ✅ Created extension: {ext_name}")
                    elif "CREATE OR REPLACE FUNCTION" in upper_stmt:
                        match = re.search(r"FUNCTION\s+(\w+)\s*\(", upper_stmt)
                        if match:
                            func_name = match.group(1)
                            print(f"   ✅ Created function: {func_name}")
                    elif "CREATE TRIGGER" in upper_stmt:
                        match = re.search(r"CREATE TRIGGER\s+(\w+)", upper_stmt, re.IGNORECASE)
                        if match:
                            trigger_name = match.group(1)
                            print(f"   ✅ Created trigger: {trigger_name}")
                    elif "DROP" in upper_stmt:
                        # Silently skip DROP statements that might fail
                        pass

                except Exception as e:
                    error_str = str(e).lower()
                    # Only warn for actual errors, not expected ones
                    if "already exists" not in error_str and "does not exist" not in error_str:
                        print(f"   ⚠️  Warning: {e}")

        print(f"\n✨ Database schema initialized successfully!")
        print(f"\n📊 Schema includes:")
        print(
            f"   • 7 tables: organizations, agents, sessions, meetings, meeting_participants, messages, meeting_events"
        )
        print(f"   • 20+ indexes for query performance")
        print(f"   • 3 triggers for timestamp updates")
        print(f"   • 1 helper function for advisory locks")
        print(f"\n🎉 Database is ready for Agent Messaging Protocol!")
        return True

    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await db_manager.close()
        print("\n🔌 Database connection closed")


def main():
    """Main entry point."""
    try:
        success = asyncio.run(init_database())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
