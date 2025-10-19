"""Unit tests for database repositories."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from agent_messaging.database.repositories.agent import AgentRepository
from agent_messaging.database.repositories.organization import OrganizationRepository
from agent_messaging.models import Agent, Organization


@pytest.fixture
def mock_pool():
    """Mock connection pool for testing."""
    return MagicMock()


@pytest.fixture
def org_repo(mock_pool):
    """Organization repository instance."""
    return OrganizationRepository(mock_pool)


@pytest.fixture
def agent_repo(mock_pool):
    """Agent repository instance."""
    return AgentRepository(mock_pool)


class TestOrganizationRepository:
    """Test cases for OrganizationRepository."""

    @pytest.mark.asyncio
    async def test_create_organization(self, org_repo, mock_pool):
        """Test creating a new organization."""
        # Mock the database response
        mock_result = {"id": str(uuid4())}
        org_repo._fetch_one = AsyncMock(return_value=mock_result)

        # Call the method
        org_id = await org_repo.create("org_001", "Test Organization")

        # Verify the call
        assert org_id == mock_result["id"]
        org_repo._fetch_one.assert_called_once_with(
            "\n            INSERT INTO organizations (external_id, name)\n            VALUES ($1, $2)\n            RETURNING id\n        ",
            ["org_001", "Test Organization"],
        )

    @pytest.mark.asyncio
    async def test_get_by_external_id_found(self, org_repo, mock_pool):
        """Test getting organization by external ID when found."""
        org_data = {
            "id": str(uuid4()),
            "external_id": "org_001",
            "name": "Test Organization",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        org_repo._fetch_one = AsyncMock(return_value=org_data)

        result = await org_repo.get_by_external_id("org_001")

        assert result is not None
        assert isinstance(result, Organization)
        assert result.external_id == "org_001"
        assert result.name == "Test Organization"

    @pytest.mark.asyncio
    async def test_get_by_external_id_not_found(self, org_repo, mock_pool):
        """Test getting organization by external ID when not found."""
        org_repo._fetch_one = AsyncMock(return_value=None)

        result = await org_repo.get_by_external_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, org_repo, mock_pool):
        """Test getting organization by ID when found."""
        org_id = uuid4()
        org_data = {
            "id": str(org_id),
            "external_id": "org_001",
            "name": "Test Organization",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        org_repo._fetch_one = AsyncMock(return_value=org_data)

        result = await org_repo.get_by_id(org_id)

        assert result is not None
        assert isinstance(result, Organization)
        assert result.id == org_id


class TestAgentRepository:
    """Test cases for AgentRepository."""

    @pytest.mark.asyncio
    async def test_create_agent(self, agent_repo, mock_pool):
        """Test creating a new agent."""
        org_id = uuid4()
        mock_result = {"id": str(uuid4())}
        agent_repo._fetch_one = AsyncMock(return_value=mock_result)

        agent_id = await agent_repo.create("alice", org_id, "Alice Agent")

        assert agent_id == mock_result["id"]
        agent_repo._fetch_one.assert_called_once_with(
            "\n            INSERT INTO agents (external_id, organization_id, name)\n            VALUES ($1, $2, $3)\n            RETURNING id\n        ",
            ["alice", str(org_id), "Alice Agent"],
        )

    @pytest.mark.asyncio
    async def test_get_by_external_id_found(self, agent_repo, mock_pool):
        """Test getting agent by external ID when found."""
        agent_data = {
            "id": str(uuid4()),
            "external_id": "alice",
            "organization_id": str(uuid4()),
            "name": "Alice Agent",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        agent_repo._fetch_one = AsyncMock(return_value=agent_data)

        result = await agent_repo.get_by_external_id("alice")

        assert result is not None
        assert isinstance(result, Agent)
        assert result.external_id == "alice"
        assert result.name == "Alice Agent"

    @pytest.mark.asyncio
    async def test_get_by_external_id_not_found(self, agent_repo, mock_pool):
        """Test getting agent by external ID when not found."""
        agent_repo._fetch_one = AsyncMock(return_value=None)

        result = await agent_repo.get_by_external_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_organization(self, agent_repo, mock_pool):
        """Test getting agents by organization."""
        org_id = uuid4()
        agent_data = [
            {
                "id": str(uuid4()),
                "external_id": "alice",
                "organization_id": str(org_id),
                "name": "Alice Agent",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": str(uuid4()),
                "external_id": "bob",
                "organization_id": str(org_id),
                "name": "Bob Agent",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
        ]
        agent_repo._fetch_all = AsyncMock(return_value=agent_data)

        results = await agent_repo.get_by_organization(org_id)

        assert len(results) == 2
        assert all(isinstance(agent, Agent) for agent in results)
        assert results[0].external_id == "alice"
        assert results[1].external_id == "bob"
