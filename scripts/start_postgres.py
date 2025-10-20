#!/usr/bin/env python3
"""Start/stop PostgreSQL Docker container for Agent Messaging Protocol.

This script manages the PostgreSQL Docker container using docker-compose.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(command: list[str], cwd: Path = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def check_docker():
    """Check if Docker is available."""
    code, _, _ = run_command(["docker", "--version"])
    return code == 0


def check_docker_compose():
    """Check if docker-compose is available."""
    # Try docker compose (newer)
    code, _, _ = run_command(["docker", "compose", "version"])
    if code == 0:
        return True, ["docker", "compose"]

    # Try docker-compose (older)
    code, _, _ = run_command(["docker-compose", "--version"])
    if code == 0:
        return True, ["docker-compose"]

    return False, []


def start_postgres(project_root: Path, compose_cmd: list[str]):
    """Start PostgreSQL container."""
    print("🐳 Starting PostgreSQL Docker container...")
    print("=" * 60)

    compose_file = project_root / "docker-compose.yml"
    if not compose_file.exists():
        print(f"❌ docker-compose.yml not found at: {compose_file}")
        return False

    print(f"\n📄 Using compose file: {compose_file}")

    # Start container
    print(f"\n🚀 Starting container...")
    code, stdout, stderr = run_command(compose_cmd + ["up", "-d"], cwd=project_root)

    if code != 0:
        print(f"❌ Failed to start container:")
        print(stderr)
        return False

    print("   ✅ Container started")

    # Wait for PostgreSQL to be ready
    print(f"\n⏳ Waiting for PostgreSQL to be ready...")
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        code, _, _ = run_command(compose_cmd + ["exec", "-T", "postgres", "pg_isready"])
        if code == 0:
            print(f"   ✅ PostgreSQL is ready (attempt {attempt}/{max_attempts})")
            break
        print(f"   ⏳ Waiting... (attempt {attempt}/{max_attempts})")
        time.sleep(1)
    else:
        print(f"   ⚠️  PostgreSQL might not be ready yet, but continuing...")

    # Show container status
    print(f"\n📊 Container status:")
    code, stdout, _ = run_command(compose_cmd + ["ps"], cwd=project_root)
    print(stdout)

    print(f"\n✨ PostgreSQL is running!")
    print(f"\n📋 Connection details:")
    print(f"   Host: localhost")
    print(f"   Port: 5432")
    print(f"   Database: agent_messaging")
    print(f"   User: postgres")
    print(f"   Password: postgres")

    print(f"\n💡 Next steps:")
    print(f"   1. Initialize database: uv run python scripts/init_db.py")
    print(f"   2. Run tests: uv run python scripts/run_tests.py")
    print(f"   3. Stop container: uv run python scripts/start_postgres.py stop")

    return True


def stop_postgres(project_root: Path, compose_cmd: list[str]):
    """Stop PostgreSQL container."""
    print("🛑 Stopping PostgreSQL Docker container...")
    print("=" * 60)

    print(f"\n🛑 Stopping container...")
    code, stdout, stderr = run_command(compose_cmd + ["down"], cwd=project_root)

    if code != 0:
        print(f"❌ Failed to stop container:")
        print(stderr)
        return False

    print("   ✅ Container stopped")
    print(stdout)

    print(f"\n✨ PostgreSQL container stopped successfully!")

    return True


def status_postgres(project_root: Path, compose_cmd: list[str]):
    """Show PostgreSQL container status."""
    print("📊 PostgreSQL Docker container status")
    print("=" * 60)

    code, stdout, stderr = run_command(compose_cmd + ["ps"], cwd=project_root)

    if code != 0:
        print(f"❌ Failed to get status:")
        print(stderr)
        return False

    print(stdout)

    # Check if container is running
    if "agent_messaging_postgres" in stdout and "Up" in stdout:
        print(f"\n✅ PostgreSQL is running")
        print(f"\n📋 Connection details:")
        print(f"   Host: localhost")
        print(f"   Port: 5432")
        print(f"   Database: agent_messaging")
    else:
        print(f"\n⚠️  PostgreSQL is not running")
        print(f"\n💡 Start with: uv run python scripts/start_postgres.py start")

    return True


def logs_postgres(project_root: Path, compose_cmd: list[str]):
    """Show PostgreSQL container logs."""
    print("📜 PostgreSQL Docker container logs")
    print("=" * 60)

    code, stdout, stderr = run_command(
        compose_cmd + ["logs", "--tail=50", "postgres"], cwd=project_root
    )

    if code != 0:
        print(f"❌ Failed to get logs:")
        print(stderr)
        return False

    print(stdout)

    return True


def main():
    """Main entry point."""
    # Get project root
    project_root = Path(__file__).parent.parent

    # Check Docker availability
    if not check_docker():
        print("❌ Docker is not available. Please install Docker first.")
        print("   Visit: https://docs.docker.com/get-docker/")
        sys.exit(1)

    # Check docker-compose availability
    has_compose, compose_cmd = check_docker_compose()
    if not has_compose:
        print("❌ docker-compose is not available. Please install Docker Compose first.")
        print("   Visit: https://docs.docker.com/compose/install/")
        sys.exit(1)

    # Parse command
    command = sys.argv[1] if len(sys.argv) > 1 else "start"

    if command == "start":
        success = start_postgres(project_root, compose_cmd)
    elif command == "stop":
        success = stop_postgres(project_root, compose_cmd)
    elif command == "status":
        success = status_postgres(project_root, compose_cmd)
    elif command == "logs":
        success = logs_postgres(project_root, compose_cmd)
    elif command in ["--help", "-h"]:
        print("Usage: python scripts/start_postgres.py [command]")
        print("\nCommands:")
        print("  start   - Start PostgreSQL container (default)")
        print("  stop    - Stop PostgreSQL container")
        print("  status  - Show container status")
        print("  logs    - Show container logs")
        print("  --help  - Show this help message")
        sys.exit(0)
    else:
        print(f"❌ Unknown command: {command}")
        print("   Use --help for usage information")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
