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
            SELECT commander_name, card_id, color_identity, total_decks, popularity_rank,
                   avg_deck_price, salt_score, power_level
            FROM commanders WHERE LOWER(commander_name) = LOWER(?)
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
            SELECT commander_name, card_id, color_identity, total_decks, popularity_rank,
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
            SELECT commander_name, card_id, color_identity, total_decks, popularity_rank,
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
            SELECT commander_name, card_id, color_identity, total_decks, popularity_rank,
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
            SELECT commander_name, card_id, color_identity, total_decks, popularity_rank,
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
        query = """
            INSERT OR REPLACE INTO commanders (
                commander_name, card_id, color_identity, total_decks, popularity_rank,
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
                                commander_name, card_id, color_identity, total_decks, popularity_rank,
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
        user_id: str,
        color_preferences: list[str] | None = None,
        budget_max: float | None = None,
        min_completion: float = 0.6,
        limit: int = 20,
    ) -> list[CommanderRecommendation]:
        """Get commander recommendations based on user's collection.

        Args:
            user_id: User identifier for collection lookup
            color_preferences: List of preferred colors (e.g., ['W', 'U'])
            budget_max: Maximum budget consideration
            min_completion: Minimum buildability score to include
            limit: Maximum number of recommendations

        Returns:
            List of commander recommendations sorted by buildability score
        """
        if not self.db.table_exists("commanders"):
            logger.warning("No commanders table - run update-edhrec first")
            return []

        if not self.db.table_exists("deck_card_inclusions"):
            logger.warning("No deck card inclusions table - run update-edhrec first")
            return []

        try:
            # Get all commanders that have deck data
            commanders_query = """
                SELECT DISTINCT c.commander_name, c.card_id, c.color_identity, c.total_decks,
                       c.popularity_rank, c.avg_deck_price, c.salt_score, c.power_level
                FROM commanders c
                INNER JOIN deck_card_inclusions d ON c.commander_name = d.commander_name
                WHERE 1=1
            """
            params = []

            # Apply color filter
            if color_preferences:
                color_str = "".join(sorted(color_preferences))
                commanders_query += " AND c.color_identity = ?"
                params.append(color_str)

            # Apply budget filter
            if budget_max:
                commanders_query += " AND c.avg_deck_price <= ?"
                params.append(budget_max)

            commanders_query += " ORDER BY c.popularity_rank"

            commander_results = self.fetch_all(commanders_query, tuple(params))

            recommendations = []

            for commander_row in commander_results:
                commander_name = commander_row[0]

                # Calculate buildability score
                buildability_score = self.calculate_buildability_score(
                    commander_name, user_id
                )

                # Skip if below minimum completion threshold
                if buildability_score < min_completion:
                    continue

                # Convert to Commander domain object
                commander = self._result_to_commander(commander_row)

                # Get missing card analysis
                missing_cards = self._get_missing_high_impact_cards(
                    commander_name, user_id
                )
                missing_value = sum(
                    card["price_usd"] for card in missing_cards if card["price_usd"]
                )

                # Get deck composition stats
                deck_cards = self.fetch_all(
                    "SELECT COUNT(*) FROM deck_card_inclusions WHERE commander_name = ?",
                    (commander_name,),
                )
                total_cards = deck_cards[0][0] if deck_cards else 0
                owned_cards = total_cards - len(missing_cards)

                # Create recommendation using the existing model structure
                recommendation = CommanderRecommendation(
                    commander_name=commander.name,
                    color_identity=commander.color_identity,
                    archetype="default",  # TODO: Get from deck data
                    budget_range="mid",  # TODO: Get from deck data
                    avg_deck_price=commander.avg_deck_price,
                    completion_percentage=buildability_score,  # 0-1 scale as per model
                    buildability_score=buildability_score
                    * 10,  # 0-10 scale as per model
                    owned_cards=owned_cards,
                    total_cards=total_cards,
                    missing_cards_value=missing_value,
                    popularity_rank=commander.popularity_rank,
                    popularity_count=commander.total_decks,
                    power_level=commander.power_level,
                    salt_score=commander.salt_score,
                    themes=[],  # TODO: Get from EDHREC data
                    collection_synergy_score=buildability_score,  # Use buildability as synergy proxy
                )

                recommendations.append(recommendation)

                # Stop if we have enough recommendations
                if len(recommendations) >= limit:
                    break

            # Sort by buildability score (highest first)
            recommendations.sort(key=lambda r: r.buildability_score, reverse=True)

            logger.info(
                f"Generated {len(recommendations)} recommendations for user {user_id}"
            )
            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Failed to get recommendations for user {user_id}: {e}")
            return []

    def calculate_buildability_score(
        self,
        commander_name: str,
        user_id: str,
    ) -> float:
        """Calculate buildability score for a commander based on user's collection.

        Args:
            commander_name: Name of the commander to analyze
            user_id: User identifier for collection lookup

        Returns:
            Buildability score from 0.0 to 1.0 (higher = more buildable)
        """
        if not self.db.table_exists("deck_card_inclusions"):
            logger.warning("No deck card inclusions table - run update-edhrec first")
            return 0.0

        if not self.db.table_exists("user_collections"):
            logger.warning("No user collections table - import collection first")
            return 0.0

        try:
            # Get deck composition for this commander
            deck_cards = self.fetch_all(
                """
                SELECT card_name, inclusion_rate, synergy_score, category, price_usd
                FROM deck_card_inclusions
                WHERE commander_name = ? AND archetype_id = 'default' AND budget_range = 'mid'
                ORDER BY inclusion_rate DESC
                """,
                (commander_name,),
            )

            if not deck_cards:
                logger.warning(f"No deck data found for commander: {commander_name}")
                return 0.0

            # Get user's collection
            user_cards = self.fetch_all(
                """
                SELECT card_name, quantity
                FROM user_collections
                WHERE user_id = ? AND quantity > 0
                """,
                (user_id,),
            )

            # Create set of owned cards for fast lookup
            owned_cards = {card[0].lower() for card in user_cards}

            # Calculate weighted buildability score
            total_weight = 0.0
            owned_weight = 0.0

            for (
                card_name,
                inclusion_rate,
                synergy_score,
                category,
                _price_usd,
            ) in deck_cards:
                # Calculate card weight based on inclusion rate and category
                base_weight = inclusion_rate

                # Category multipliers (more important cards have higher weight)
                category_multiplier = {
                    "signature": 2.0,  # Signature cards are essential
                    "high_synergy": 1.5,  # High synergy cards are very important
                    "staple": 1.2,  # Staples are important
                    "basic": 1.0,  # Basic cards have normal weight
                }.get(category, 1.0)

                # Synergy score bonus (higher synergy = more important)
                synergy_bonus = 1.0 + (synergy_score * 0.5)

                card_weight = base_weight * category_multiplier * synergy_bonus
                total_weight += card_weight

                # Check if user owns this card
                if card_name.lower() in owned_cards:
                    owned_weight += card_weight

            # Calculate final buildability score (0.0 to 1.0)
            buildability = owned_weight / total_weight if total_weight > 0 else 0.0

            logger.info(
                f"Buildability for {commander_name}: {buildability:.3f} "
                f"({len([c for c in deck_cards if c[0].lower() in owned_cards])}/{len(deck_cards)} cards owned)"
            )

            return buildability

        except Exception as e:
            logger.error(f"Failed to calculate buildability for {commander_name}: {e}")
            return 0.0

    def _get_missing_high_impact_cards(
        self, commander_name: str, user_id: str
    ) -> list[dict]:
        """Get missing high-impact cards for a commander deck.

        Args:
            commander_name: Name of the commander
            user_id: User identifier for collection lookup

        Returns:
            List of missing cards with impact analysis
        """
        try:
            # Get deck composition
            deck_cards = self.fetch_all(
                """
                SELECT card_name, inclusion_rate, synergy_score, category, price_usd
                FROM deck_card_inclusions
                WHERE commander_name = ? AND archetype_id = 'default' AND budget_range = 'mid'
                ORDER BY inclusion_rate DESC
                """,
                (commander_name,),
            )

            # Get owned cards
            owned_cards = {
                card[0].lower()
                for card in self.fetch_all(
                    "SELECT card_name FROM user_collections WHERE user_id = ? AND quantity > 0",
                    (user_id,),
                )
            }

            missing_cards = []

            for (
                card_name,
                inclusion_rate,
                synergy_score,
                category,
                _price_usd,
            ) in deck_cards:
                if card_name.lower() not in owned_cards:
                    # Calculate impact score (higher = more important to acquire)
                    impact_score = inclusion_rate

                    # Category impact multipliers
                    if category == "signature":
                        impact_score *= 2.0
                    elif category == "high_synergy":
                        impact_score *= 1.5
                    elif category == "staple":
                        impact_score *= 1.2

                    # Synergy bonus
                    impact_score *= 1.0 + synergy_score * 0.5

                    missing_cards.append(
                        {
                            "card_name": card_name,
                            "inclusion_rate": inclusion_rate,
                            "synergy_score": synergy_score,
                            "category": category,
                            "price_usd": _price_usd or 0.0,
                            "impact_score": impact_score,
                        }
                    )

            # Sort by impact score (highest impact first)
            missing_cards.sort(key=lambda x: x["impact_score"], reverse=True)

            return missing_cards

        except Exception as e:
            logger.error(f"Failed to get missing cards for {commander_name}: {e}")
            return []

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
