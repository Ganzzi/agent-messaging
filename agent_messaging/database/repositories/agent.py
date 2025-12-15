"""Agent repository for database operations."""

from typing import Optional
from uuid import UUID

from .base import BaseRepository
from ...models import Agent


class AgentRepository(BaseRepository):
    """Repository for agent-related database operations."""

    async def create(self, external_id: str, organization_id: UUID, name: str) -> UUID:
        """Create a new agent.

        Args:
            external_id: External identifier for the agent
            organization_id: Organization UUID
            name: Human-readable name

        Returns:
            UUID of the created agent
        """
        query = """
            INSERT INTO agents (external_id, organization_id, name)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        result = await self._fetch_one(query, [external_id, organization_id, name])
        agent_id = result["id"]
        if isinstance(agent_id, str):
            agent_id = UUID(agent_id)
        return agent_id

    async def get_by_external_id(self, external_id: str) -> Optional[Agent]:
        """Get agent by external ID.

        Args:
            external_id: External identifier

        Returns:
            Agent if found, None otherwise
        """
        query = """
            SELECT id, external_id, organization_id, name, created_at, updated_at
            FROM agents
            WHERE external_id = $1
        """
        result = await self._fetch_one(query, [external_id])
        return Agent(**result) if result else None

    async def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent by internal ID.

        Args:
            agent_id: Internal UUID

        Returns:
            Agent if found, None otherwise
        """
        query = """
            SELECT id, external_id, organization_id, name, created_at, updated_at
            FROM agents
            WHERE id = $1
        """
        result = await self._fetch_one(query, [agent_id])
        return Agent(**result) if result else None

    async def get_by_organization(self, organization_id: UUID) -> list[Agent]:
        """Get all agents in an organization.

        Args:
            organization_id: Organization UUID

        Returns:
            List of agents in the organization
        """
        query = """
            SELECT id, external_id, organization_id, name, created_at, updated_at
            FROM agents
            WHERE organization_id = $1
            ORDER BY created_at
        """
        results = await self._fetch_all(query, [organization_id])
        return [Agent(**result) for result in results]

    async def delete(self, external_id: str) -> bool:
        """Delete agent by external ID.

        Note: This will cascade delete all related sessions, messages, and meeting
        participations due to foreign key constraints in the database schema.

        Args:
            external_id: External identifier

        Returns:
            True if agent was deleted, False if not found
        """
        query = """
            DELETE FROM agents
            WHERE external_id = $1
            RETURNING id
        """
        result = await self._fetch_one(query, [external_id])
        return result is not None
