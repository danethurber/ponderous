"""Deck domain models."""

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class DeckVariant:
    """Represents a specific variant of a commander deck."""

    commander_name: str
    archetype: str
    theme: str
    budget_range: str
    avg_price: float
    total_decks: int
    win_rate: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate deck variant data."""
        if not self.commander_name.strip():
            raise ValueError("Commander name cannot be empty")
        if not self.archetype.strip():
            raise ValueError("Archetype cannot be empty")
        if self.avg_price < 0:
            raise ValueError("Average price cannot be negative")
        if self.total_decks < 0:
            raise ValueError("Total decks cannot be negative")
        if self.win_rate is not None and not (0.0 <= self.win_rate <= 1.0):
            raise ValueError("Win rate must be between 0 and 1")

    @property
    def is_budget_friendly(self) -> bool:
        """Check if deck is budget friendly (<$150)."""
        return self.avg_price < 150.0

    @property
    def is_competitive(self) -> bool:
        """Check if deck appears competitive based on price and win rate."""
        if self.win_rate and self.win_rate >= 0.5:
            return True
        return self.avg_price >= 500.0  # High price often indicates competitive cards


@dataclass(frozen=True)
class Deck:
    """Complete deck entity with card list and metadata."""

    commander_name: str
    variant: DeckVariant
    cards: List[str]  # Card names in the deck
    total_value: float
    power_level: float

    def __post_init__(self) -> None:
        """Validate deck data."""
        if not self.commander_name.strip():
            raise ValueError("Commander name cannot be empty")
        if len(self.cards) == 0:
            raise ValueError("Deck must have at least one card")
        if self.total_value < 0:
            raise ValueError("Total value cannot be negative")
        if not (1.0 <= self.power_level <= 10.0):
            raise ValueError("Power level must be between 1 and 10")

    @property
    def card_count(self) -> int:
        """Get total number of cards in deck."""
        return len(self.cards)

    @property
    def average_card_value(self) -> float:
        """Calculate average value per card."""
        return self.total_value / len(self.cards) if self.cards else 0.0

    def contains_card(self, card_name: str) -> bool:
        """Check if deck contains a specific card."""
        return card_name.lower() in [card.lower() for card in self.cards]


class DeckRecommendation(BaseModel):
    """Recommendation for a specific deck variant based on collection."""

    commander_name: str = Field(..., description="Commander name")
    archetype: str = Field(..., description="Deck archetype")
    theme: str = Field(..., description="Deck theme")
    budget_range: str = Field(..., description="Budget range")
    completion_percentage: float = Field(
        ..., ge=0.0, le=1.0, description="Completion percentage"
    )
    buildability_score: float = Field(
        ..., ge=0.0, le=10.0, description="Buildability score"
    )
    owned_cards: int = Field(..., ge=0, description="Number of owned cards")
    total_cards: int = Field(..., ge=0, description="Total cards needed")
    missing_cards_value: float = Field(
        ..., ge=0.0, description="Value of missing cards"
    )
    missing_high_impact_cards: int = Field(
        ..., ge=0, description="Number of missing high-impact cards"
    )

    class Config:
        """Pydantic configuration."""

        frozen = True

    @property
    def completion_percentage_display(self) -> str:
        """Get completion percentage as display string."""
        return f"{self.completion_percentage:.1%}"

    @property
    def buildability_score_display(self) -> str:
        """Get buildability score as display string."""
        return f"{self.buildability_score:.1f}/10"

    @property
    def missing_cards_count(self) -> int:
        """Calculate number of missing cards."""
        return self.total_cards - self.owned_cards

    @property
    def is_highly_buildable(self) -> bool:
        """Check if deck is highly buildable (>80% completion, >7.0 score)."""
        return self.completion_percentage >= 0.8 and self.buildability_score >= 7.0

    @property
    def affordability_rating(self) -> str:
        """Get affordability rating based on missing card value."""
        if self.missing_cards_value <= 25.0:
            return "very_affordable"
        elif self.missing_cards_value <= 75.0:
            return "affordable"
        elif self.missing_cards_value <= 150.0:
            return "moderate"
        elif self.missing_cards_value <= 300.0:
            return "expensive"
        else:
            return "very_expensive"

    @property
    def priority_score(self) -> float:
        """Calculate overall priority score for recommendation ranking."""
        # Higher completion and buildability = higher priority
        # Lower missing value = higher priority
        completion_factor = self.completion_percentage * 40
        buildability_factor = (self.buildability_score / 10) * 35
        affordability_factor = max(0, (200 - self.missing_cards_value) / 200) * 25

        return completion_factor + buildability_factor + affordability_factor
