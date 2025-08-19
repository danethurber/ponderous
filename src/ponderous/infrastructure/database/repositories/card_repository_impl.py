"""Card repository implementation."""

import logging
from typing import Any

from ponderous.domain.models.card import Card
from ponderous.domain.repositories.card_repository import CardRepository
from ponderous.infrastructure.database.repositories.base import BaseRepository
from ponderous.shared.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class CardRepositoryImpl(BaseRepository, CardRepository):
    """Database implementation of card repository."""

    def get_by_id(self, card_id: str) -> Card | None:
        """Get card by unique identifier."""
        if not self.db.table_exists("cards"):
            return None

        result = self.fetch_one(
            """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards WHERE card_id = ?
            """,
            (card_id,),
        )

        if not result:
            return None

        return self._result_to_card(result)

    def get_by_name(self, name: str) -> list[Card]:
        """Get cards by name (may return multiple versions)."""
        if not self.db.table_exists("cards"):
            return []

        results = self.fetch_all(
            """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards WHERE LOWER(name) = LOWER(?)
            ORDER BY set_code, collector_number
            """,
            (name,),
        )

        return [self._result_to_card(row) for row in results]

    def get_by_name_and_set(self, name: str, set_code: str) -> Card | None:
        """Get specific card by name and set."""
        if not self.db.table_exists("cards"):
            return None

        result = self.fetch_one(
            """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards WHERE LOWER(name) = LOWER(?) AND LOWER(set_code) = LOWER(?)
            """,
            (name, set_code),
        )

        if not result:
            return None

        return self._result_to_card(result)

    def search_by_partial_name(self, partial_name: str, limit: int = 20) -> list[Card]:
        """Search cards by partial name match."""
        if not self.db.table_exists("cards"):
            return []

        results = self.fetch_all(
            """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards
            WHERE LOWER(name) LIKE LOWER(?)
            ORDER BY name
            LIMIT ?
            """,
            (f"%{partial_name}%", limit),
        )

        return [self._result_to_card(row) for row in results]

    def get_by_color_identity(self, color_identity: list[str]) -> list[Card]:
        """Get cards by color identity."""
        if not self.db.table_exists("cards"):
            return []

        # Convert color identity to string for comparison
        color_str = "".join(sorted(color_identity)) if color_identity else ""

        results = self.fetch_all(
            """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards WHERE color_identity = ?
            ORDER BY name
            """,
            (color_str,),
        )

        return [self._result_to_card(row) for row in results]

    def get_commanders(self, color_identity: list[str] | None = None) -> list[Card]:
        """Get cards that can be commanders."""
        if not self.db.table_exists("cards"):
            return []

        query = """
            SELECT card_id, name, mana_cost, cmc, color_identity, type_line,
                   oracle_text, power, toughness, loyalty, rarity, set_code,
                   collector_number, image_url, price_usd, price_eur
            FROM cards
            WHERE type_line LIKE '%Legendary%' AND type_line LIKE '%Creature%'
        """
        params = []

        if color_identity is not None:
            color_str = "".join(sorted(color_identity))
            query += " AND color_identity = ?"
            params.append(color_str)

        query += " ORDER BY name"

        results = self.fetch_all(query, tuple(params))
        return [self._result_to_card(row) for row in results]

    def store(self, card: Card) -> None:
        """Store a card entity."""
        self._ensure_cards_table()

        query = """
            INSERT OR REPLACE INTO cards (
                card_id, name, mana_cost, cmc, color_identity, type_line,
                oracle_text, power, toughness, loyalty, rarity, set_code,
                collector_number, image_url, price_usd, price_eur
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        color_identity_str = (
            "".join(sorted(card.color_identity)) if card.color_identity else ""
        )

        self.execute_query(
            query,
            (
                card.card_id,
                card.name,
                card.mana_cost,
                card.cmc,
                color_identity_str,
                card.type_line,
                card.oracle_text,
                card.power,
                card.toughness,
                card.loyalty,
                card.rarity,
                card.set_code,
                card.collector_number,
                card.image_url,
                card.price_usd,
                card.price_eur,
            ),
        )

    def store_batch(self, cards: list[Card]) -> tuple[int, int]:
        """Store multiple cards in batch."""
        if not cards:
            return 0, 0

        self._ensure_cards_table()

        stored_count = 0
        skipped_count = 0

        try:
            with self.db.transaction() as conn:
                for card in cards:
                    try:
                        color_identity_str = (
                            "".join(sorted(card.color_identity))
                            if card.color_identity
                            else ""
                        )

                        conn.execute(
                            """
                            INSERT OR REPLACE INTO cards (
                                card_id, name, mana_cost, cmc, color_identity, type_line,
                                oracle_text, power, toughness, loyalty, rarity, set_code,
                                collector_number, image_url, price_usd, price_eur
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                card.card_id,
                                card.name,
                                card.mana_cost,
                                card.cmc,
                                color_identity_str,
                                card.type_line,
                                card.oracle_text,
                                card.power,
                                card.toughness,
                                card.loyalty,
                                card.rarity,
                                card.set_code,
                                card.collector_number,
                                card.image_url,
                                card.price_usd,
                                card.price_eur,
                            ),
                        )
                        stored_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to store card {card.name}: {e}")
                        skipped_count += 1

        except Exception as e:
            raise DatabaseError(f"Failed to store card batch: {e}") from e

        logger.info(f"Stored {stored_count} cards, skipped {skipped_count}")
        return stored_count, skipped_count

    def update(self, card: Card) -> bool:
        """Update an existing card."""
        if not self.db.table_exists("cards"):
            return False

        existing = self.get_by_id(card.card_id)
        if not existing:
            return False

        self.store(card)
        return True

    def delete(self, card_id: str) -> bool:
        """Delete a card by ID."""
        if not self.db.table_exists("cards"):
            return False

        result = self.execute_query("DELETE FROM cards WHERE card_id = ?", (card_id,))
        return result is not None

    def get_card_stats(self) -> dict[str, Any]:
        """Get card database statistics."""
        if not self.db.table_exists("cards"):
            return {"total_cards": 0, "unique_names": 0}

        result = self.fetch_one(
            """
            SELECT
                COUNT(*) as total_cards,
                COUNT(DISTINCT LOWER(name)) as unique_names,
                COUNT(DISTINCT set_code) as sets_count
            FROM cards
            """
        )

        if result:
            return {
                "total_cards": result[0],
                "unique_names": result[1],
                "sets_count": result[2],
            }
        return {"total_cards": 0, "unique_names": 0, "sets_count": 0}

    def normalize_card_name(self, raw_name: str) -> str:
        """Normalize a card name for consistent matching."""
        # Basic normalization - can be enhanced
        return raw_name.strip().title()

    def find_matching_cards(
        self, collection_name: str, set_name: str | None = None
    ) -> list[Card]:
        """Find cards matching collection import data."""
        # Try exact match first
        if set_name:
            exact_match = self.get_by_name_and_set(collection_name, set_name)
            if exact_match:
                return [exact_match]

        # Try name-only match
        name_matches = self.get_by_name(collection_name)
        if name_matches:
            return name_matches

        # Try normalized name
        normalized_name = self.normalize_card_name(collection_name)
        if normalized_name != collection_name:
            normalized_matches = self.get_by_name(normalized_name)
            if normalized_matches:
                return normalized_matches

        return []

    def _ensure_cards_table(self) -> None:
        """Ensure cards table exists."""
        if not self.db.table_exists("cards"):
            self._create_cards_table()

    def _create_cards_table(self) -> None:
        """Create cards table."""
        query = """
            CREATE TABLE IF NOT EXISTS cards (
                card_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mana_cost TEXT,
                cmc INTEGER,
                color_identity TEXT,
                type_line TEXT,
                oracle_text TEXT,
                power TEXT,
                toughness TEXT,
                loyalty TEXT,
                rarity TEXT,
                set_code TEXT,
                collector_number TEXT,
                image_url TEXT,
                price_usd REAL,
                price_eur REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        self.execute_query(query)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(LOWER(name))",
            "CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_code)",
            "CREATE INDEX IF NOT EXISTS idx_cards_color_identity ON cards(color_identity)",
            "CREATE INDEX IF NOT EXISTS idx_cards_type_line ON cards(type_line)",
        ]

        for index_query in indexes:
            self.execute_query(index_query)

    def _result_to_card(self, row: tuple) -> Card:
        """Convert database row to Card entity."""
        # Parse color identity from string back to list
        color_identity_str = row[4] or ""
        color_identity = list(color_identity_str) if color_identity_str else None

        return Card(
            card_id=row[0],
            name=row[1],
            mana_cost=row[2],
            cmc=row[3],
            color_identity=color_identity,
            type_line=row[5],
            oracle_text=row[6],
            power=row[7],
            toughness=row[8],
            loyalty=row[9],
            rarity=row[10],
            set_code=row[11],
            collector_number=row[12],
            image_url=row[13],
            price_usd=row[14],
            price_eur=row[15],
        )
