#!/usr/bin/env python3
"""Run full test suite for Agent Messaging Protocol.

This script:
1. Checks Docker and PostgreSQL availability
2. Initializes/resets the test database
3. Runs pytest with coverage
4. Generates coverage report
5. Shows summary of results
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], cwd: Path = None, check: bool = True) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)

        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(command)}")
            if result.stdout:
                print(f"   stdout: {result.stdout}")
            if result.stderr:
                print(f"   stderr: {result.stderr}")

        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return 1, "", str(e)


def check_docker():
    """Check if Docker is running."""
    code, stdout, _ = run_command(["docker", "ps"], check=False)
    return code == 0


def check_postgres(project_root: Path):
    """Check if PostgreSQL container is running."""
    # Try docker compose ps
    code, stdout, _ = run_command(["docker", "compose", "ps"], cwd=project_root, check=False)
    if code != 0:
        code, stdout, _ = run_command(["docker-compose", "ps"], cwd=project_root, check=False)

    if code != 0:
        return False

    return "agent_messaging_postgres" in stdout and "Up" in stdout


def start_postgres(project_root: Path):
    """Start PostgreSQL container."""
    print("\n🐳 Starting PostgreSQL container...")

    # Try docker compose up
    code, _, _ = run_command(["docker", "compose", "up", "-d"], cwd=project_root, check=False)

    if code != 0:
        # Try docker-compose
        code, _, _ = run_command(["docker-compose", "up", "-d"], cwd=project_root, check=False)

    if code != 0:
        print("❌ Failed to start PostgreSQL container")
        return False

    # Wait for PostgreSQL
    print("   ⏳ Waiting for PostgreSQL to be ready...")
    import time

    for i in range(30):
        code, _, _ = run_command(
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready"], check=False
        )
        if code != 0:
            code, _, _ = run_command(
                ["docker-compose", "exec", "-T", "postgres", "pg_isready"], check=False
            )

        if code == 0:
            print("   ✅ PostgreSQL is ready")
            return True

        time.sleep(1)

    print("   ⚠️  PostgreSQL might not be ready, continuing anyway...")
    return True


def init_database(project_root: Path):
    """Initialize database schema."""
    print("\n🗄️  Initializing database schema...")

    init_script = project_root / "scripts" / "init_db.py"
    code, stdout, stderr = run_command(["uv", "run", "python", str(init_script)], check=False)

    if code != 0:
        print("❌ Failed to initialize database")
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)
        return False

    print("   ✅ Database initialized")
    return True


def run_tests(project_root: Path, coverage: bool = True, verbose: bool = True):
    """Run pytest tests."""
    print("\n🧪 Running test suite...")
    print("=" * 60)

    command = ["uv", "run", "pytest", "tests/"]

    if verbose:
        command.append("-v")

    if coverage:
        command.extend(["--cov=agent_messaging", "--cov-report=term", "--cov-report=html"])

    # Run tests (don't check, we want to see results even if some fail)
    code, stdout, stderr = run_command(command, cwd=project_root, check=False)

    # Print output
    if stdout:
        print(stdout)
    if stderr and "warning" in stderr.lower():
        print(stderr)

    return code == 0


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent

    print("🧪 Agent Messaging Protocol - Test Suite Runner")
    print("=" * 60)

    # Parse arguments
    skip_setup = "--skip-setup" in sys.argv
    no_coverage = "--no-coverage" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print("\nUsage: python scripts/run_tests.py [options]")
        print("\nOptions:")
        print("  --skip-setup    Skip Docker and database setup")
        print("  --no-coverage   Run tests without coverage report")
        print("  --quiet, -q     Less verbose output")
        print("  --help, -h      Show this help message")
        sys.exit(0)

    # Step 1: Check Docker (unless skipping setup)
    if not skip_setup:
        print("\n📋 Step 1: Checking Docker...")
        if not check_docker():
            print("❌ Docker is not running. Please start Docker first.")
            print("   Or use --skip-setup if database is already running")
            sys.exit(1)
        print("   ✅ Docker is running")

        # Step 2: Check/Start PostgreSQL
        print("\n📋 Step 2: Checking PostgreSQL...")
        if not check_postgres(project_root):
            print("   PostgreSQL is not running, starting it...")
            if not start_postgres(project_root):
                sys.exit(1)
        else:
            print("   ✅ PostgreSQL is already running")

        # Step 3: Initialize database
        print("\n📋 Step 3: Initializing database...")
        if not init_database(project_root):
            sys.exit(1)
    else:
        print("\n⚠️  Skipping Docker and database setup (--skip-setup)")

    # Step 4: Run tests
    print("\n📋 Step 4: Running tests...")
    success = run_tests(project_root, coverage=not no_coverage, verbose=not quiet)

    # Summary
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed. Review output above.")

    if not no_coverage:
        coverage_report = project_root / "htmlcov" / "index.html"
        if coverage_report.exists():
            print(f"\n📊 Coverage report: {coverage_report}")

    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
