"""Commander recommendation service."""

import logging
from typing import Any, Protocol

from ponderous.domain.models.commander import CommanderRecommendation
from ponderous.domain.repositories.card_repository import CardRepository
from ponderous.domain.repositories.commander_repository import CommanderRepository
from ponderous.infrastructure.database.repositories.collection_repository import (
    CollectionRepository,
)


class EDHRECCard(Protocol):
    """Protocol for EDHREC card data."""

    name: str
    inclusion_rate: float  # 0.0 to 1.0
    category: str  # "signature", "high_synergy", "staple", "basic"
    synergy_score: float  # 0.0 to 1.0


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

    def calculate_buildability_score(
        self, owned_cards: set[str], deck_cards: list[EDHRECCard]
    ) -> float:
        """Calculate weighted buildability score based on owned cards and EDHREC data.

        Uses sophisticated algorithm that weights cards by category and synergy:
        - Signature cards (commanders, key pieces): 3.0x weight
        - High synergy cards: 2.0x weight + synergy bonus
        - Staple cards: 1.5x weight
        - Basic lands: 0.5x weight

        Args:
            owned_cards: Set of card names owned by user
            deck_cards: List of EDHREC cards with inclusion rates and categories

        Returns:
            Buildability score from 0.0 to 10.0
        """
        if not deck_cards:
            return 0.0

        # Category weights for scoring impact
        category_weights = {
            "signature": 3.0,
            "high_synergy": 2.0,
            "staple": 1.5,
            "basic": 0.5,
        }

        total_weighted_value = 0.0
        owned_weighted_value = 0.0

        for card in deck_cards:
            # Get base weight for card category
            base_weight = category_weights.get(card.category, 1.0)

            # Add synergy bonus for high synergy cards
            synergy_bonus = 0.0
            if card.category == "high_synergy":
                synergy_bonus = card.synergy_score * 0.5  # Up to 0.5 bonus

            # Calculate final weight with inclusion rate influence
            card_weight = (
                base_weight * (0.5 + 0.5 * card.inclusion_rate) + synergy_bonus
            )

            total_weighted_value += card_weight

            if card.name in owned_cards:
                owned_weighted_value += card_weight

        # Calculate percentage and scale to 0-10
        if total_weighted_value == 0:
            return 0.0

        completion_ratio = owned_weighted_value / total_weighted_value
        return min(completion_ratio * 10.0, 10.0)

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

            # Get user's collection cards for analysis
            user_collection = self.collection_repo.get_collection_by_user(
                user_id, limit=2000
            )
            owned_card_names = {entry.get("card_name", "") for entry in user_collection}

            # Create EDHREC-based recommendations for owned commanders
            recommendations = []
            for card in commanders_from_cards:
                try:
                    # Get EDHREC data for this commander
                    commander_entity = self.commander_repo.get_by_name(card.name)
                    if not commander_entity:
                        # Skip commanders without EDHREC data
                        continue

                    # Convert commander entity to data dict for analysis
                    commander_data = {
                        "total_decks": commander_entity.total_decks,
                        "popularity_rank": commander_entity.popularity_rank,
                        "avg_deck_price": commander_entity.avg_deck_price,
                        "power_level": commander_entity.power_level,
                        "salt_score": commander_entity.salt_score,
                        "archetype_distribution": getattr(
                            commander_entity,
                            "archetype_distribution",
                            {"midrange": 1.0},
                        ),
                    }

                    # Get deck composition from EDHREC for buildability analysis
                    deck_cards = self._get_mock_edhrec_deck_cards(
                        card.name, commander_data
                    )

                    # Calculate real buildability using our new algorithm
                    buildability_score = self.calculate_buildability_score(
                        owned_card_names, deck_cards
                    )
                    completion_percentage = (
                        buildability_score / 10.0
                    )  # Convert back to percentage

                    # Skip low-completion commanders based on threshold
                    if completion_percentage < min_completion:
                        continue

                    # Calculate owned vs total cards
                    owned_cards = sum(
                        1 for dc in deck_cards if dc.name in owned_card_names
                    )
                    total_cards = len(deck_cards)

                    # Estimate missing cards value based on EDHREC data
                    missing_cards_value = self._estimate_missing_cards_cost(
                        owned_card_names,
                        deck_cards,
                        commander_data.get("avg_deck_price", 300.0),
                    )

                    # Determine archetype based on EDHREC data
                    archetype = self._determine_primary_archetype(commander_data)

                    # Determine budget range based on deck price
                    budget_range = self._determine_budget_range(
                        commander_data.get("avg_deck_price", 300.0)
                    )

                    recommendation = CommanderRecommendation(
                        commander_name=card.name,
                        color_identity=card.color_identity or [],
                        archetype=archetype,
                        budget_range=budget_range,
                        avg_deck_price=commander_data.get("avg_deck_price", 300.0),
                        completion_percentage=completion_percentage,
                        buildability_score=buildability_score,
                        owned_cards=owned_cards,
                        total_cards=total_cards,
                        missing_cards_value=missing_cards_value,
                        popularity_rank=commander_data.get("popularity_rank", 500),
                        popularity_count=commander_data.get("total_decks", 100),
                        power_level=commander_data.get("power_level", 7.0),
                        salt_score=commander_data.get("salt_score", 2.0),
                        themes=self._extract_themes(commander_data),
                    )
                    recommendations.append(recommendation)

                except Exception as e:
                    logger.warning(f"Failed to analyze commander {card.name}: {e}")
                    continue

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

            # Count cards by theme/strategy for more sophisticated analysis
            total_cards = len(collection_entries)

            # Define theme-based card detection
            graveyard_cards = sum(
                1
                for entry in collection_entries
                if any(
                    word in entry.get("card_name", "").lower()
                    for word in [
                        "entomb",
                        "reanimate",
                        "buried",
                        "necromancy",
                        "animate",
                        "exhume",
                    ]
                )
            )

            artifact_cards = sum(
                1
                for entry in collection_entries
                if "artifact" in entry.get("card_name", "").lower()
            )

            token_cards = sum(
                1
                for entry in collection_entries
                if any(
                    word in entry.get("card_name", "").lower()
                    for word in [
                        "token",
                        "populate",
                        "doubling",
                        "parallel",
                        "anointed",
                    ]
                )
            )

            combo_cards = sum(
                1
                for entry in collection_entries
                if any(
                    word in entry.get("card_name", "").lower()
                    for word in ["tutor", "storm", "ritual", "combo", "infinite"]
                )
            )

            # Sophisticated synergy calculation based on commander themes
            synergy_score = 0.1  # Base synergy
            theme_cards = 0

            if "meren" in commander_name.lower():
                # Graveyard synergy for Meren
                theme_cards = graveyard_cards
                synergy_score = (
                    (graveyard_cards / total_cards) if total_cards > 0 else 0.0
                )
            elif "artifact" in commander_name.lower():
                theme_cards = artifact_cards
                synergy_score = (
                    (artifact_cards / total_cards) if total_cards > 0 else 0.0
                )
            elif any(word in commander_name.lower() for word in ["token", "populate"]):
                theme_cards = token_cards
                synergy_score = (token_cards / total_cards) if total_cards > 0 else 0.0
            elif any(word in commander_name.lower() for word in ["combo", "storm"]):
                theme_cards = combo_cards
                synergy_score = (combo_cards / total_cards) if total_cards > 0 else 0.0

            return {
                "commander_name": commander_name,
                "total_collection_cards": total_cards,
                "synergy_score": min(synergy_score, 1.0),
                "graveyard_cards": graveyard_cards,
                "artifact_cards": artifact_cards,
                "token_cards": token_cards,
                "combo_cards": combo_cards,
                "theme_cards": theme_cards,
                "synergy_category": (
                    "High"
                    if synergy_score > 0.5
                    else "Medium"
                    if synergy_score > 0.2
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

    def _get_mock_edhrec_deck_cards(
        self, commander_name: str, _commander_data: dict[str, Any]
    ) -> list[EDHRECCard]:
        """Get mock EDHREC deck cards for analysis.

        TODO: Replace with real EDHREC deck composition data from scraper.
        For now, generates representative deck based on commander data.

        Args:
            commander_name: Name of the commander
            commander_data: EDHREC data for the commander

        Returns:
            List of mock EDHREC cards representing typical deck composition
        """
        # Generate representative deck based on commander characteristics
        deck_cards = []

        # Add essential staples (every deck has these)
        staples = [
            MockEDHRECCard("Sol Ring", 0.85, "staple", 0.0),
            MockEDHRECCard("Command Tower", 0.70, "staple", 0.0),
            MockEDHRECCard("Arcane Signet", 0.75, "staple", 0.0),
            MockEDHRECCard("Swords to Plowshares", 0.60, "staple", 0.0),  # If white
            MockEDHRECCard("Counterspell", 0.55, "staple", 0.0),  # If blue
            MockEDHRECCard("Lightning Bolt", 0.50, "staple", 0.0),  # If red
            MockEDHRECCard("Beast Within", 0.45, "staple", 0.0),  # If green
            MockEDHRECCard("Vampiric Tutor", 0.40, "staple", 0.0),  # If black
        ]
        deck_cards.extend(staples)

        # Add signature cards based on commander
        if "artifact" in commander_name.lower():
            signature_cards = [
                MockEDHRECCard("Foundry Inspector", 0.65, "signature", 0.8),
                MockEDHRECCard("Etherium Sculptor", 0.60, "signature", 0.7),
                MockEDHRECCard("Chief Engineer", 0.55, "signature", 0.6),
            ]
        elif "token" in commander_name.lower() or "populate" in commander_name.lower():
            signature_cards = [
                MockEDHRECCard("Anointed Procession", 0.70, "signature", 0.9),
                MockEDHRECCard("Parallel Lives", 0.65, "signature", 0.8),
                MockEDHRECCard("Doubling Season", 0.60, "signature", 0.9),
            ]
        else:
            # Generic high-value cards
            signature_cards = [
                MockEDHRECCard("Rhystic Study", 0.75, "signature", 0.7),
                MockEDHRECCard("Demonic Tutor", 0.60, "signature", 0.8),
                MockEDHRECCard("Smothering Tithe", 0.65, "signature", 0.6),
            ]
        deck_cards.extend(signature_cards)

        # Add high synergy cards (theme-specific)
        synergy_cards = [
            MockEDHRECCard("Skullclamp", 0.55, "high_synergy", 0.5),
            MockEDHRECCard("Sensei's Divining Top", 0.45, "high_synergy", 0.4),
            MockEDHRECCard("Scroll Rack", 0.40, "high_synergy", 0.3),
        ]
        deck_cards.extend(synergy_cards)

        # Add basic lands and fixing
        lands = [
            MockEDHRECCard("Island", 0.90, "basic", 0.0),
            MockEDHRECCard("Plains", 0.85, "basic", 0.0),
            MockEDHRECCard("Swamp", 0.80, "basic", 0.0),
            MockEDHRECCard("Mountain", 0.75, "basic", 0.0),
            MockEDHRECCard("Forest", 0.70, "basic", 0.0),
        ]
        deck_cards.extend(lands[:5])  # Add 5 basics

        return deck_cards

    def _estimate_missing_cards_cost(
        self, owned_cards: set[str], deck_cards: list[EDHRECCard], avg_deck_price: float
    ) -> float:
        """Estimate cost of missing cards based on deck composition and avg price.

        Args:
            owned_cards: Cards owned by user
            deck_cards: EDHREC deck composition
            avg_deck_price: Average deck price from EDHREC

        Returns:
            Estimated cost of missing cards
        """
        total_cards = len(deck_cards)

        if total_cards == 0:
            return 0.0

        # Estimate based on proportion of missing cards and their importance
        missing_weight = 0.0
        total_weight = 0.0

        for card in deck_cards:
            weight = {
                "signature": 3.0,
                "high_synergy": 2.0,
                "staple": 1.5,
                "basic": 0.1,  # Basics are cheap
            }.get(card.category, 1.0)

            total_weight += weight
            if card.name not in owned_cards:
                missing_weight += weight

        if total_weight == 0:
            return 0.0

        missing_ratio = missing_weight / total_weight
        return avg_deck_price * missing_ratio

    def _determine_primary_archetype(self, commander_data: dict[str, Any]) -> str:
        """Determine primary archetype from EDHREC data.

        Args:
            commander_data: EDHREC commander data

        Returns:
            Primary archetype name
        """
        archetype_dist = commander_data.get("archetype_distribution", {})
        if not archetype_dist:
            return "Midrange"  # Default

        # Return the most popular archetype
        return max(archetype_dist.keys(), key=lambda k: archetype_dist[k])

    def _determine_budget_range(self, avg_price: float) -> str:
        """Determine budget range based on average deck price.

        Args:
            avg_price: Average deck price

        Returns:
            Budget range category
        """
        if avg_price < 150:
            return "budget"
        elif avg_price < 500:
            return "mid"
        elif avg_price < 1000:
            return "high"
        else:
            return "cedh"

    def _extract_themes(self, commander_data: dict[str, Any]) -> list[str]:
        """Extract themes from EDHREC commander data.

        Args:
            commander_data: EDHREC commander data

        Returns:
            List of theme names
        """
        # TODO: Extract real themes from EDHREC data
        # For now, return some common themes based on archetype
        archetype = self._determine_primary_archetype(commander_data)

        theme_map = {
            "combo": ["Combo", "Synergy"],
            "control": ["Control", "Value"],
            "aggro": ["Aggro", "Combat"],
            "midrange": ["Value", "Midrange"],
        }

        return theme_map.get(archetype.lower(), ["Value", "Synergy"])


class MockEDHRECCard:
    """Mock EDHREC card for testing and development."""

    def __init__(
        self, name: str, inclusion_rate: float, category: str, synergy_score: float
    ):
        self.name = name
        self.inclusion_rate = inclusion_rate
        self.category = category
        self.synergy_score = synergy_score
