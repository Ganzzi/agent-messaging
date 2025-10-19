"""Organization repository for database operations."""

from typing import Optional
from uuid import UUID

from .base import BaseRepository
from ...models import Organization


class OrganizationRepository(BaseRepository):
    """Repository for organization-related database operations."""

    async def create(self, external_id: str, name: str) -> UUID:
        """Create a new organization.

        Args:
            external_id: External identifier for the organization
            name: Human-readable name

        Returns:
            UUID of the created organization
        """
        query = """
            INSERT INTO organizations (external_id, name)
            VALUES ($1, $2)
            RETURNING id
        """
        result = await self._fetch_one(query, [external_id, name])
        return result["id"]

    async def get_by_external_id(self, external_id: str) -> Optional[Organization]:
        """Get organization by external ID.

        Args:
            external_id: External identifier

        Returns:
            Organization if found, None otherwise
        """
        query = """
            SELECT id, external_id, name, created_at, updated_at
            FROM organizations
            WHERE external_id = $1
        """
        result = await self._fetch_one(query, [external_id])
        return Organization(**result) if result else None

    async def get_by_id(self, organization_id: UUID) -> Optional[Organization]:
        """Get organization by internal ID.

        Args:
            organization_id: Internal UUID

        Returns:
            Organization if found, None otherwise
        """
        query = """
            SELECT id, external_id, name, created_at, updated_at
            FROM organizations
            WHERE id = $1
        """
        result = await self._fetch_one(query, [str(organization_id)])
        return Organization(**result) if result else None
