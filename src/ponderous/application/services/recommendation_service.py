"""Commander recommendation service."""

import logging
from typing import Any

from ponderous.domain.models.commander import CommanderRecommendation
from ponderous.domain.repositories.card_repository import CardRepository
from ponderous.domain.repositories.commander_repository import CommanderRepository
from ponderous.infrastructure.database.repositories.collection_repository import (
    CollectionRepository,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating commander and deck recommendations."""

    def __init__(
        self,
        card_repo: CardRepository,
        commander_repo: CommanderRepository,
        collection_repo: CollectionRepository,
    ) -> None:
        """Initialize recommendation service.

        Args:
            card_repo: Card repository
            commander_repo: Commander repository
            collection_repo: Collection repository
        """
        self.card_repo = card_repo
        self.commander_repo = commander_repo
        self.collection_repo = collection_repo

    def get_commander_recommendations(
        self,
        user_id: str,
        color_preferences: list[str] | None = None,
        budget_max: float | None = None,  # noqa: ARG002
        min_completion: float = 0.6,  # noqa: ARG002
        limit: int = 20,
    ) -> list[CommanderRecommendation]:
        """Get commander recommendations for a user's collection.

        Args:
            user_id: User identifier
            color_preferences: Preferred color identity
            budget_max: Maximum budget for missing cards
            min_completion: Minimum completion percentage
            limit: Maximum number of recommendations

        Returns:
            List of commander recommendations
        """
        try:
            # Get user's collection summary
            collection_summary = self.collection_repo.get_user_collection_summary(
                user_id
            )
            if collection_summary["total_cards"] == 0:
                logger.warning(f"No collection found for user {user_id}")
                return []

            # Get available commanders from card database
            commanders_from_cards = self.card_repo.get_commanders(color_preferences)

            # Create simple recommendations based on owned commanders
            recommendations = []
            for card in commanders_from_cards:
                # Simple buildability calculation
                # For now, just base it on the fact that the user owns the commander
                completion_percentage = 0.15  # Base 15% for owning commander
                buildability_score = completion_percentage * 10

                # Estimate deck cost (placeholder)
                estimated_deck_price = 250.0
                if color_preferences and len(color_preferences) <= 2:
                    estimated_deck_price = 180.0  # Simpler mana base

                recommendation = CommanderRecommendation(
                    commander_name=card.name,
                    color_identity=card.color_identity or [],
                    archetype="General Value",  # Placeholder
                    budget_range="mid",
                    avg_deck_price=estimated_deck_price,
                    completion_percentage=completion_percentage,
                    buildability_score=buildability_score,
                    owned_cards=1,  # At least the commander
                    total_cards=99,  # Standard deck size
                    missing_cards_value=estimated_deck_price,
                    popularity_rank=500,  # Default rank
                    popularity_count=100,  # Default popularity
                    power_level=6.0,  # Default power level
                    salt_score=2.0,  # Default salt score
                    themes=["Value", "Midrange"],
                )
                recommendations.append(recommendation)

            # Sort by buildability score
            recommendations.sort(key=lambda r: r.buildability_score, reverse=True)

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Failed to generate commander recommendations: {e}")
            return []

    def calculate_collection_synergy(
        self, user_id: str, commander_name: str
    ) -> dict[str, Any]:
        """Calculate synergy between collection and a commander.

        Args:
            user_id: User identifier
            commander_name: Commander to analyze

        Returns:
            Dictionary with synergy analysis
        """
        try:
            # Get user's collection
            collection_entries = self.collection_repo.get_collection_by_user(
                user_id, limit=1000
            )

            # Count cards by type/category
            total_cards = len(collection_entries)
            artifact_count = sum(
                1
                for entry in collection_entries
                if "artifact" in entry.get("card_name", "").lower()
            )
            instant_sorcery_count = sum(
                1
                for entry in collection_entries
                if any(
                    word in entry.get("card_name", "").lower()
                    for word in ["lightning", "bolt", "spell", "instant"]
                )
            )

            # Simple synergy calculation
            synergy_score = 0.0
            if "artifact" in commander_name.lower():
                synergy_score = artifact_count / total_cards if total_cards > 0 else 0.0
            elif any(
                word in commander_name.lower()
                for word in ["spell", "instant", "wizard"]
            ):
                synergy_score = (
                    instant_sorcery_count / total_cards if total_cards > 0 else 0.0
                )
            else:
                synergy_score = 0.1  # Base synergy

            return {
                "commander_name": commander_name,
                "total_collection_cards": total_cards,
                "synergy_score": min(synergy_score, 1.0),
                "artifact_cards": artifact_count,
                "spell_cards": instant_sorcery_count,
                "synergy_category": (
                    "High"
                    if synergy_score > 0.3
                    else "Medium"
                    if synergy_score > 0.1
                    else "Low"
                ),
            }

        except Exception as e:
            logger.error(f"Failed to calculate collection synergy: {e}")
            return {
                "commander_name": commander_name,
                "total_collection_cards": 0,
                "synergy_score": 0.0,
                "synergy_category": "Unknown",
            }

    def get_buildable_commanders(
        self, user_id: str, min_buildability: float = 5.0, limit: int = 10
    ) -> list[CommanderRecommendation]:
        """Get most buildable commanders for a user.

        Args:
            user_id: User identifier
            min_buildability: Minimum buildability score
            limit: Maximum number of commanders

        Returns:
            List of buildable commander recommendations
        """
        recommendations = self.get_commander_recommendations(user_id, limit=limit * 2)

        # Filter by buildability and return top results
        buildable = [
            r for r in recommendations if r.buildability_score >= min_buildability
        ]
        return buildable[:limit]
