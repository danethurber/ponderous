"""Commander repository interface."""

from abc import ABC, abstractmethod
from typing import Any

from ponderous.domain.models.commander import Commander, CommanderRecommendation


class CommanderRepository(ABC):
    """Abstract repository for commander data operations."""

    @abstractmethod
    def get_by_name(self, name: str) -> Commander | None:
        """Get commander by name.

        Args:
            name: Commander name

        Returns:
            Commander entity or None if not found
        """

    @abstractmethod
    def get_by_color_identity(self, color_identity: list[str]) -> list[Commander]:
        """Get commanders by color identity.

        Args:
            color_identity: List of color symbols (W, U, B, R, G)

        Returns:
            List of commanders matching the color identity
        """

    @abstractmethod
    def get_popular_commanders(self, limit: int = 100) -> list[Commander]:
        """Get most popular commanders.

        Args:
            limit: Maximum number of commanders to return

        Returns:
            List of popular commanders ordered by popularity rank
        """

    @abstractmethod
    def get_budget_commanders(
        self, max_price: float = 150.0, limit: int = 50
    ) -> list[Commander]:
        """Get budget-friendly commanders.

        Args:
            max_price: Maximum average deck price
            limit: Maximum number of commanders to return

        Returns:
            List of budget commanders
        """

    @abstractmethod
    def get_competitive_commanders(
        self, min_power: float = 7.0, limit: int = 50
    ) -> list[Commander]:
        """Get competitive commanders.

        Args:
            min_power: Minimum power level
            limit: Maximum number of commanders to return

        Returns:
            List of competitive commanders
        """

    @abstractmethod
    def search_by_archetype(self, archetype: str) -> list[Commander]:
        """Search commanders by archetype.

        Args:
            archetype: Archetype to search for

        Returns:
            List of commanders matching the archetype
        """

    @abstractmethod
    def store(self, commander: Commander) -> None:
        """Store a commander entity.

        Args:
            commander: Commander entity to store
        """

    @abstractmethod
    def store_batch(self, commanders: list[Commander]) -> tuple[int, int]:
        """Store multiple commanders in batch.

        Args:
            commanders: List of commander entities to store

        Returns:
            Tuple of (stored_count, skipped_count)
        """

    @abstractmethod
    def update(self, commander: Commander) -> bool:
        """Update an existing commander.

        Args:
            commander: Commander entity with updated data

        Returns:
            True if updated, False if not found
        """

    @abstractmethod
    def get_commander_stats(self) -> dict[str, Any]:
        """Get commander database statistics.

        Returns:
            Dictionary with commander statistics
        """

    @abstractmethod
    def get_recommendations_for_collection(
        self,
        user_id: str,
        color_preferences: list[str] | None = None,
        budget_max: float | None = None,
        min_completion: float = 0.6,
        limit: int = 20,
    ) -> list[CommanderRecommendation]:
        """Get commander recommendations based on user's collection.

        Args:
            user_id: User identifier
            color_preferences: Preferred color identity
            budget_max: Maximum budget for missing cards
            min_completion: Minimum completion percentage
            limit: Maximum number of recommendations

        Returns:
            List of commander recommendations
        """

    @abstractmethod
    def calculate_buildability_score(self, commander_name: str, user_id: str) -> float:
        """Calculate buildability score for a commander based on user's collection.

        Args:
            commander_name: Commander name
            user_id: User identifier

        Returns:
            Buildability score (0-10)
        """
