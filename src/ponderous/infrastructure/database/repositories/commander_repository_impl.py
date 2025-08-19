"""Commander repository implementation."""

import logging
from typing import Any

from ponderous.domain.models.commander import Commander, CommanderRecommendation
from ponderous.domain.repositories.commander_repository import CommanderRepository
from ponderous.infrastructure.database.repositories.base import BaseRepository
from ponderous.shared.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class CommanderRepositoryImpl(BaseRepository, CommanderRepository):
    """Database implementation of commander repository."""

    def get_by_name(self, name: str) -> Commander | None:
        """Get commander by name."""
        if not self.db.table_exists("commanders"):
            return None

        result = self.fetch_one(
            """
            SELECT name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders WHERE LOWER(name) = LOWER(?)
            """,
            (name,),
        )

        if not result:
            return None

        return self._result_to_commander(result)

    def get_by_color_identity(self, color_identity: list[str]) -> list[Commander]:
        """Get commanders by color identity."""
        if not self.db.table_exists("commanders"):
            return []

        color_str = "".join(sorted(color_identity)) if color_identity else ""

        results = self.fetch_all(
            """
            SELECT name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders WHERE color_identity = ?
            ORDER BY popularity_rank
            """,
            (color_str,),
        )

        return [self._result_to_commander(row) for row in results]

    def get_popular_commanders(self, limit: int = 100) -> list[Commander]:
        """Get most popular commanders."""
        if not self.db.table_exists("commanders"):
            return []

        results = self.fetch_all(
            """
            SELECT name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders
            ORDER BY popularity_rank
            LIMIT ?
            """,
            (limit,),
        )

        return [self._result_to_commander(row) for row in results]

    def get_budget_commanders(
        self, max_price: float = 150.0, limit: int = 50
    ) -> list[Commander]:
        """Get budget-friendly commanders."""
        if not self.db.table_exists("commanders"):
            return []

        results = self.fetch_all(
            """
            SELECT name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders
            WHERE avg_deck_price <= ?
            ORDER BY popularity_rank
            LIMIT ?
            """,
            (max_price, limit),
        )

        return [self._result_to_commander(row) for row in results]

    def get_competitive_commanders(
        self, min_power: float = 7.0, limit: int = 50
    ) -> list[Commander]:
        """Get competitive commanders."""
        if not self.db.table_exists("commanders"):
            return []

        results = self.fetch_all(
            """
            SELECT name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders
            WHERE power_level >= ?
            ORDER BY power_level DESC, popularity_rank
            LIMIT ?
            """,
            (min_power, limit),
        )

        return [self._result_to_commander(row) for row in results]

    def search_by_archetype(self, archetype: str) -> list[Commander]:  # noqa: ARG002
        """Search commanders by archetype."""
        # This would require archetype data in commanders table or join with deck_variants
        # For now, return empty list as placeholder
        logger.warning("Archetype search not yet implemented - requires EDHREC data")
        return []

    def store(self, commander: Commander) -> None:
        """Store a commander entity."""
        self._ensure_commanders_table()

        query = """
            INSERT OR REPLACE INTO commanders (
                name, card_id, color_identity, total_decks, popularity_rank,
                avg_deck_price, salt_score, power_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        color_identity_str = (
            "".join(sorted(commander.color_identity))
            if commander.color_identity
            else ""
        )

        self.execute_query(
            query,
            (
                commander.name,
                commander.card_id,
                color_identity_str,
                commander.total_decks,
                commander.popularity_rank,
                commander.avg_deck_price,
                commander.salt_score,
                commander.power_level,
            ),
        )

    def store_batch(self, commanders: list[Commander]) -> tuple[int, int]:
        """Store multiple commanders in batch."""
        if not commanders:
            return 0, 0

        self._ensure_commanders_table()

        stored_count = 0
        skipped_count = 0

        try:
            with self.db.transaction() as conn:
                for commander in commanders:
                    try:
                        color_identity_str = (
                            "".join(sorted(commander.color_identity))
                            if commander.color_identity
                            else ""
                        )

                        conn.execute(
                            """
                            INSERT OR REPLACE INTO commanders (
                                name, card_id, color_identity, total_decks, popularity_rank,
                                avg_deck_price, salt_score, power_level
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                commander.name,
                                commander.card_id,
                                color_identity_str,
                                commander.total_decks,
                                commander.popularity_rank,
                                commander.avg_deck_price,
                                commander.salt_score,
                                commander.power_level,
                            ),
                        )
                        stored_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to store commander {commander.name}: {e}"
                        )
                        skipped_count += 1

        except Exception as e:
            raise DatabaseError(f"Failed to store commander batch: {e}") from e

        logger.info(f"Stored {stored_count} commanders, skipped {skipped_count}")
        return stored_count, skipped_count

    def update(self, commander: Commander) -> bool:
        """Update an existing commander."""
        if not self.db.table_exists("commanders"):
            return False

        existing = self.get_by_name(commander.name)
        if not existing:
            return False

        self.store(commander)
        return True

    def get_commander_stats(self) -> dict[str, Any]:
        """Get commander database statistics."""
        if not self.db.table_exists("commanders"):
            return {"total_commanders": 0}

        result = self.fetch_one(
            """
            SELECT
                COUNT(*) as total_commanders,
                COUNT(DISTINCT color_identity) as unique_color_identities,
                AVG(avg_deck_price) as avg_price,
                AVG(power_level) as avg_power_level
            FROM commanders
            """
        )

        if result:
            return {
                "total_commanders": result[0],
                "unique_color_identities": result[1],
                "avg_price": result[2] or 0.0,
                "avg_power_level": result[3] or 0.0,
            }
        return {"total_commanders": 0}

    def get_recommendations_for_collection(
        self,
        user_id: str,  # noqa: ARG002
        color_preferences: list[str] | None = None,  # noqa: ARG002
        budget_max: float | None = None,  # noqa: ARG002
        min_completion: float = 0.6,  # noqa: ARG002
        limit: int = 20,  # noqa: ARG002
    ) -> list[CommanderRecommendation]:
        """Get commander recommendations based on user's collection."""
        # This is a complex operation that requires:
        # 1. Collection data analysis
        # 2. Deck card lists
        # 3. Buildability scoring
        # For now, return empty list as placeholder
        logger.warning(
            "Commander recommendations not yet implemented - requires EDHREC deck data"
        )
        return []

    def calculate_buildability_score(
        self,
        commander_name: str,  # noqa: ARG002
        user_id: str,  # noqa: ARG002
    ) -> float:
        """Calculate buildability score for a commander based on user's collection."""
        # This requires deck card lists and collection analysis
        # For now, return 0 as placeholder
        logger.warning(
            "Buildability scoring not yet implemented - requires EDHREC deck data"
        )
        return 0.0

    def _ensure_commanders_table(self) -> None:
        """Ensure commanders table exists."""
        if not self.db.table_exists("commanders"):
            self._create_commanders_table()

    def _create_commanders_table(self) -> None:
        """Create commanders table."""
        query = """
            CREATE TABLE IF NOT EXISTS commanders (
                name TEXT PRIMARY KEY,
                card_id TEXT NOT NULL,
                color_identity TEXT NOT NULL,
                total_decks INTEGER DEFAULT 0,
                popularity_rank INTEGER DEFAULT 999999,
                avg_deck_price REAL DEFAULT 0.0,
                salt_score REAL DEFAULT 0.0,
                power_level REAL DEFAULT 5.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        self.execute_query(query)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_commanders_color_identity ON commanders(color_identity)",
            "CREATE INDEX IF NOT EXISTS idx_commanders_popularity ON commanders(popularity_rank)",
            "CREATE INDEX IF NOT EXISTS idx_commanders_price ON commanders(avg_deck_price)",
            "CREATE INDEX IF NOT EXISTS idx_commanders_power ON commanders(power_level)",
        ]

        for index_query in indexes:
            self.execute_query(index_query)

    def _result_to_commander(self, row: tuple) -> Commander:
        """Convert database row to Commander entity."""
        # Parse color identity from string back to list
        color_identity_str = row[2] or ""
        color_identity = list(color_identity_str) if color_identity_str else []

        return Commander(
            name=row[0],
            card_id=row[1],
            color_identity=color_identity,
            total_decks=row[3],
            popularity_rank=row[4],
            avg_deck_price=row[5],
            salt_score=row[6],
            power_level=row[7],
        )
