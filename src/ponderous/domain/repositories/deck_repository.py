"""Deck repository interface."""

from abc import ABC, abstractmethod
from typing import Any

from ponderous.domain.models.deck import Deck, DeckRecommendation, DeckVariant


class DeckRepository(ABC):
    """Abstract repository for deck data operations."""

    @abstractmethod
    def get_by_commander(self, commander_name: str) -> list[DeckVariant]:
        """Get deck variants for a commander.

        Args:
            commander_name: Commander name

        Returns:
            List of deck variants for the commander
        """

    @abstractmethod
    def get_by_archetype(self, archetype: str) -> list[DeckVariant]:
        """Get deck variants by archetype.

        Args:
            archetype: Deck archetype

        Returns:
            List of deck variants matching the archetype
        """

    @abstractmethod
    def get_budget_decks(self, max_price: float = 150.0) -> list[DeckVariant]:
        """Get budget-friendly deck variants.

        Args:
            max_price: Maximum average deck price

        Returns:
            List of budget deck variants
        """

    @abstractmethod
    def get_popular_decks(self, limit: int = 50) -> list[DeckVariant]:
        """Get most popular deck variants.

        Args:
            limit: Maximum number of deck variants

        Returns:
            List of popular deck variants ordered by deck count
        """

    @abstractmethod
    def get_deck_cards(self, commander_name: str, archetype: str) -> list[str]:
        """Get card list for a specific deck variant.

        Args:
            commander_name: Commander name
            archetype: Deck archetype

        Returns:
            List of card names in the deck
        """

    @abstractmethod
    def store_variant(self, variant: DeckVariant) -> None:
        """Store a deck variant.

        Args:
            variant: Deck variant to store
        """

    @abstractmethod
    def store_deck(self, deck: Deck) -> None:
        """Store a complete deck with card list.

        Args:
            deck: Deck entity to store
        """

    @abstractmethod
    def store_deck_cards(
        self, commander_name: str, archetype: str, cards: list[str]
    ) -> None:
        """Store card list for a deck variant.

        Args:
            commander_name: Commander name
            archetype: Deck archetype
            cards: List of card names
        """

    @abstractmethod
    def get_deck_stats(self) -> dict[str, Any]:
        """Get deck database statistics.

        Returns:
            Dictionary with deck statistics
        """

    @abstractmethod
    def get_recommendations_for_collection(
        self,
        user_id: str,
        commander_name: str | None = None,
        archetype: str | None = None,
        budget_max: float | None = None,
        min_completion: float = 0.6,
        limit: int = 20,
    ) -> list[DeckRecommendation]:
        """Get deck recommendations based on user's collection.

        Args:
            user_id: User identifier
            commander_name: Optional commander filter
            archetype: Optional archetype filter
            budget_max: Maximum budget for missing cards
            min_completion: Minimum completion percentage
            limit: Maximum number of recommendations

        Returns:
            List of deck recommendations
        """

    @abstractmethod
    def calculate_deck_completion(
        self, commander_name: str, archetype: str, user_id: str
    ) -> tuple[float, int, int]:
        """Calculate completion percentage for a deck based on user's collection.

        Args:
            commander_name: Commander name
            archetype: Deck archetype
            user_id: User identifier

        Returns:
            Tuple of (completion_percentage, owned_cards, total_cards)
        """

    @abstractmethod
    def get_missing_cards_analysis(
        self, commander_name: str, archetype: str, user_id: str
    ) -> dict[str, Any]:
        """Analyze missing cards for a deck variant.

        Args:
            commander_name: Commander name
            archetype: Deck archetype
            user_id: User identifier

        Returns:
            Dictionary with missing cards analysis
        """
