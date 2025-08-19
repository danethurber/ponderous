"""Deck repository implementation."""

import logging
from typing import Any

from ponderous.domain.models.deck import Deck, DeckRecommendation, DeckVariant
from ponderous.domain.repositories.deck_repository import DeckRepository
from ponderous.infrastructure.database.repositories.base import BaseRepository
from ponderous.shared.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DeckRepositoryImpl(BaseRepository, DeckRepository):
    """Database implementation of deck repository."""

    def get_by_commander(self, commander_name: str) -> list[DeckVariant]:
        """Get deck variants for a commander."""
        if not self.db.table_exists("deck_variants"):
            return []

        results = self.fetch_all(
            """
            SELECT commander_name, archetype, theme, budget_range, avg_price,
                   total_decks, win_rate
            FROM deck_variants WHERE LOWER(commander_name) = LOWER(?)
            ORDER BY total_decks DESC
            """,
            (commander_name,),
        )

        return [self._result_to_deck_variant(row) for row in results]

    def get_by_archetype(self, archetype: str) -> list[DeckVariant]:
        """Get deck variants by archetype."""
        if not self.db.table_exists("deck_variants"):
            return []

        results = self.fetch_all(
            """
            SELECT commander_name, archetype, theme, budget_range, avg_price,
                   total_decks, win_rate
            FROM deck_variants WHERE LOWER(archetype) = LOWER(?)
            ORDER BY total_decks DESC
            """,
            (archetype,),
        )

        return [self._result_to_deck_variant(row) for row in results]

    def get_budget_decks(self, max_price: float = 150.0) -> list[DeckVariant]:
        """Get budget-friendly deck variants."""
        if not self.db.table_exists("deck_variants"):
            return []

        results = self.fetch_all(
            """
            SELECT commander_name, archetype, theme, budget_range, avg_price,
                   total_decks, win_rate
            FROM deck_variants
            WHERE avg_price <= ?
            ORDER BY total_decks DESC
            """,
            (max_price,),
        )

        return [self._result_to_deck_variant(row) for row in results]

    def get_popular_decks(self, limit: int = 50) -> list[DeckVariant]:
        """Get most popular deck variants."""
        if not self.db.table_exists("deck_variants"):
            return []

        results = self.fetch_all(
            """
            SELECT commander_name, archetype, theme, budget_range, avg_price,
                   total_decks, win_rate
            FROM deck_variants
            ORDER BY total_decks DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [self._result_to_deck_variant(row) for row in results]

    def get_deck_cards(self, commander_name: str, archetype: str) -> list[str]:
        """Get card list for a specific deck variant."""
        if not self.db.table_exists("deck_cards"):
            return []

        results = self.fetch_all(
            """
            SELECT card_name
            FROM deck_cards
            WHERE LOWER(commander_name) = LOWER(?) AND LOWER(archetype) = LOWER(?)
            ORDER BY card_name
            """,
            (commander_name, archetype),
        )

        return [row[0] for row in results]

    def store_variant(self, variant: DeckVariant) -> None:
        """Store a deck variant."""
        self._ensure_deck_variants_table()

        query = """
            INSERT OR REPLACE INTO deck_variants (
                commander_name, archetype, theme, budget_range, avg_price,
                total_decks, win_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        self.execute_query(
            query,
            (
                variant.commander_name,
                variant.archetype,
                variant.theme,
                variant.budget_range,
                variant.avg_price,
                variant.total_decks,
                variant.win_rate,
            ),
        )

    def store_deck(self, deck: Deck) -> None:
        """Store a complete deck with card list."""
        # Store the variant first
        self.store_variant(deck.variant)

        # Store the card list
        self.store_deck_cards(deck.commander_name, deck.variant.archetype, deck.cards)

    def store_deck_cards(
        self, commander_name: str, archetype: str, cards: list[str]
    ) -> None:
        """Store card list for a deck variant."""
        if not cards:
            return

        self._ensure_deck_cards_table()

        # Clear existing cards for this deck variant
        self.execute_query(
            "DELETE FROM deck_cards WHERE commander_name = ? AND archetype = ?",
            (commander_name, archetype),
        )

        # Insert new cards
        try:
            with self.db.transaction() as conn:
                for card_name in cards:
                    conn.execute(
                        """
                        INSERT INTO deck_cards (commander_name, archetype, card_name)
                        VALUES (?, ?, ?)
                        """,
                        (commander_name, archetype, card_name),
                    )
        except Exception as e:
            raise DatabaseError(f"Failed to store deck cards: {e}") from e

    def get_deck_stats(self) -> dict[str, Any]:
        """Get deck database statistics."""
        stats = {}

        if self.db.table_exists("deck_variants"):
            variant_result = self.fetch_one(
                """
                SELECT
                    COUNT(*) as total_variants,
                    COUNT(DISTINCT commander_name) as unique_commanders,
                    COUNT(DISTINCT archetype) as unique_archetypes,
                    AVG(avg_price) as avg_price
                FROM deck_variants
                """
            )
            if variant_result:
                stats.update(
                    {
                        "total_variants": variant_result[0],
                        "unique_commanders": variant_result[1],
                        "unique_archetypes": variant_result[2],
                        "avg_price": variant_result[3] or 0.0,
                    }
                )

        if self.db.table_exists("deck_cards"):
            cards_result = self.fetch_one(
                "SELECT COUNT(*) as total_deck_cards FROM deck_cards"
            )
            if cards_result:
                stats["total_deck_cards"] = cards_result[0]

        return stats

    def get_recommendations_for_collection(
        self,
        user_id: str,  # noqa: ARG002
        commander_name: str | None = None,  # noqa: ARG002
        archetype: str | None = None,  # noqa: ARG002
        budget_max: float | None = None,  # noqa: ARG002
        min_completion: float = 0.6,  # noqa: ARG002
        limit: int = 20,  # noqa: ARG002
    ) -> list[DeckRecommendation]:
        """Get deck recommendations based on user's collection."""
        # This is a complex operation that requires:
        # 1. Collection data analysis
        # 2. Deck completion calculation
        # 3. Missing cards analysis
        # For now, return empty list as placeholder
        logger.warning(
            "Deck recommendations not yet implemented - requires collection analysis"
        )
        return []

    def calculate_deck_completion(
        self,
        commander_name: str,  # noqa: ARG002
        archetype: str,  # noqa: ARG002
        user_id: str,  # noqa: ARG002
    ) -> tuple[float, int, int]:
        """Calculate completion percentage for a deck based on user's collection."""
        # This requires comparing deck cards with user collection
        # For now, return 0 as placeholder
        logger.warning("Deck completion calculation not yet implemented")
        return 0.0, 0, 0

    def get_missing_cards_analysis(
        self,
        commander_name: str,  # noqa: ARG002
        archetype: str,  # noqa: ARG002
        user_id: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Analyze missing cards for a deck variant."""
        # This requires deck cards and collection comparison
        # For now, return empty dict as placeholder
        logger.warning("Missing cards analysis not yet implemented")
        return {}

    def _ensure_deck_variants_table(self) -> None:
        """Ensure deck_variants table exists."""
        if not self.db.table_exists("deck_variants"):
            self._create_deck_variants_table()

    def _ensure_deck_cards_table(self) -> None:
        """Ensure deck_cards table exists."""
        if not self.db.table_exists("deck_cards"):
            self._create_deck_cards_table()

    def _create_deck_variants_table(self) -> None:
        """Create deck_variants table."""
        query = """
            CREATE TABLE IF NOT EXISTS deck_variants (
                id INTEGER PRIMARY KEY,
                commander_name TEXT NOT NULL,
                archetype TEXT NOT NULL,
                theme TEXT NOT NULL,
                budget_range TEXT NOT NULL,
                avg_price REAL DEFAULT 0.0,
                total_decks INTEGER DEFAULT 0,
                win_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(commander_name, archetype)
            )
        """
        self.execute_query(query)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_deck_variants_commander ON deck_variants(commander_name)",
            "CREATE INDEX IF NOT EXISTS idx_deck_variants_archetype ON deck_variants(archetype)",
            "CREATE INDEX IF NOT EXISTS idx_deck_variants_price ON deck_variants(avg_price)",
            "CREATE INDEX IF NOT EXISTS idx_deck_variants_popularity ON deck_variants(total_decks)",
        ]

        for index_query in indexes:
            self.execute_query(index_query)

    def _create_deck_cards_table(self) -> None:
        """Create deck_cards table."""
        query = """
            CREATE TABLE IF NOT EXISTS deck_cards (
                id INTEGER PRIMARY KEY,
                commander_name TEXT NOT NULL,
                archetype TEXT NOT NULL,
                card_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(commander_name, archetype, card_name)
            )
        """
        self.execute_query(query)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_deck_cards_commander ON deck_cards(commander_name)",
            "CREATE INDEX IF NOT EXISTS idx_deck_cards_archetype ON deck_cards(archetype)",
            "CREATE INDEX IF NOT EXISTS idx_deck_cards_card_name ON deck_cards(card_name)",
        ]

        for index_query in indexes:
            self.execute_query(index_query)

    def _result_to_deck_variant(self, row: tuple) -> DeckVariant:
        """Convert database row to DeckVariant entity."""
        return DeckVariant(
            commander_name=row[0],
            archetype=row[1],
            theme=row[2],
            budget_range=row[3],
            avg_price=row[4],
            total_decks=row[5],
            win_rate=row[6],
        )
