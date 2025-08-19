"""Card repository interface."""

from abc import ABC, abstractmethod
from typing import Any

from ponderous.domain.models.card import Card


class CardRepository(ABC):
    """Abstract repository for card data operations."""

    @abstractmethod
    def get_by_id(self, card_id: str) -> Card | None:
        """Get card by unique identifier.

        Args:
            card_id: Unique card identifier

        Returns:
            Card entity or None if not found
        """

    @abstractmethod
    def get_by_name(self, name: str) -> list[Card]:
        """Get cards by name (may return multiple versions).

        Args:
            name: Card name to search for

        Returns:
            List of card entities matching the name
        """

    @abstractmethod
    def get_by_name_and_set(self, name: str, set_code: str) -> Card | None:
        """Get specific card by name and set.

        Args:
            name: Card name
            set_code: Set code

        Returns:
            Card entity or None if not found
        """

    @abstractmethod
    def search_by_partial_name(self, partial_name: str, limit: int = 20) -> list[Card]:
        """Search cards by partial name match.

        Args:
            partial_name: Partial card name to search
            limit: Maximum number of results

        Returns:
            List of matching card entities
        """

    @abstractmethod
    def get_by_color_identity(self, color_identity: list[str]) -> list[Card]:
        """Get cards by color identity.

        Args:
            color_identity: List of color symbols (W, U, B, R, G)

        Returns:
            List of cards matching the color identity
        """

    @abstractmethod
    def get_commanders(self, color_identity: list[str] | None = None) -> list[Card]:
        """Get cards that can be commanders.

        Args:
            color_identity: Optional color identity filter

        Returns:
            List of legendary creatures that can be commanders
        """

    @abstractmethod
    def store(self, card: Card) -> None:
        """Store a card entity.

        Args:
            card: Card entity to store
        """

    @abstractmethod
    def store_batch(self, cards: list[Card]) -> tuple[int, int]:
        """Store multiple cards in batch.

        Args:
            cards: List of card entities to store

        Returns:
            Tuple of (stored_count, skipped_count)
        """

    @abstractmethod
    def update(self, card: Card) -> bool:
        """Update an existing card.

        Args:
            card: Card entity with updated data

        Returns:
            True if updated, False if not found
        """

    @abstractmethod
    def delete(self, card_id: str) -> bool:
        """Delete a card by ID.

        Args:
            card_id: Card identifier

        Returns:
            True if deleted, False if not found
        """

    @abstractmethod
    def get_card_stats(self) -> dict[str, Any]:
        """Get card database statistics.

        Returns:
            Dictionary with card statistics
        """

    @abstractmethod
    def normalize_card_name(self, raw_name: str) -> str:
        """Normalize a card name for consistent matching.

        Args:
            raw_name: Raw card name from import

        Returns:
            Normalized card name
        """

    @abstractmethod
    def find_matching_cards(
        self, collection_name: str, set_name: str | None = None
    ) -> list[Card]:
        """Find cards matching collection import data.

        Args:
            collection_name: Card name from collection import
            set_name: Optional set name from import

        Returns:
            List of matching card entities
        """
