"""Commander domain models."""

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Commander:
    """Commander entity representing a legendary creature that can lead a deck."""

    name: str
    card_id: str
    color_identity: List[str]
    total_decks: int
    popularity_rank: int
    avg_deck_price: float
    salt_score: float
    power_level: float

    def __post_init__(self) -> None:
        """Validate commander data after initialization."""
        if not self.name.strip():
            raise ValueError("Commander name cannot be empty")
        if not self.card_id.strip():
            raise ValueError("Commander card ID cannot be empty")
        if self.total_decks < 0:
            raise ValueError("Total decks cannot be negative")
        if self.popularity_rank < 1:
            raise ValueError("Popularity rank must be at least 1")
        if self.avg_deck_price < 0:
            raise ValueError("Average deck price cannot be negative")
        if not (0.0 <= self.salt_score <= 5.0):
            raise ValueError("Salt score must be between 0 and 5")
        if not (1.0 <= self.power_level <= 10.0):
            raise ValueError("Power level must be between 1 and 10")

    @property
    def color_identity_str(self) -> str:
        """Get color identity as a string."""
        if not self.color_identity:
            return "C"  # Colorless
        return "".join(sorted(self.color_identity))

    @property
    def is_popular(self) -> bool:
        """Check if commander is popular (top 100)."""
        return self.popularity_rank <= 100

    @property
    def is_high_power(self) -> bool:
        """Check if commander is high power level (8+)."""
        return self.power_level >= 8.0

    @property
    def is_low_salt(self) -> bool:
        """Check if commander has low salt score (<2.0)."""
        return self.salt_score < 2.0


class CommanderRecommendation(BaseModel):
    """Recommendation for a commander based on collection analysis."""

    commander_name: str = Field(..., description="Commander name")
    color_identity: List[str] = Field(..., description="Commander color identity")
    archetype: str = Field(..., description="Primary deck archetype")
    budget_range: str = Field(..., description="Budget range (budget/mid/high/cedh)")
    avg_deck_price: float = Field(..., ge=0.0, description="Average deck price")
    completion_percentage: float = Field(
        ..., ge=0.0, le=1.0, description="Collection completion (0-1)"
    )
    buildability_score: float = Field(
        ..., ge=0.0, le=10.0, description="Buildability score (0-10)"
    )
    owned_cards: int = Field(..., ge=0, description="Number of owned cards")
    total_cards: int = Field(..., ge=0, description="Total cards in deck")
    missing_cards_value: float = Field(
        ..., ge=0.0, description="Value of missing cards"
    )
    popularity_rank: int = Field(..., ge=1, description="EDHREC popularity rank")
    popularity_count: int = Field(..., ge=0, description="Number of decks on EDHREC")
    power_level: float = Field(..., ge=1.0, le=10.0, description="Power level (1-10)")
    salt_score: float = Field(..., ge=0.0, le=5.0, description="Salt score (0-5)")
    win_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Win rate if available"
    )
    themes: List[str] = Field(default_factory=list, description="Deck themes")
    collection_synergy_score: float = Field(
        default=0.0, ge=0.0, description="Collection synergy score"
    )

    class Config:
        """Pydantic configuration."""

        frozen = True

    @property
    def color_identity_str(self) -> str:
        """Get color identity as a string."""
        if not self.color_identity:
            return "C"  # Colorless
        return "".join(sorted(self.color_identity))

    @property
    def completion_percentage_display(self) -> str:
        """Get completion percentage as display string."""
        return f"{self.completion_percentage:.1%}"

    @property
    def is_highly_buildable(self) -> bool:
        """Check if deck is highly buildable (>80% completion, >7.0 score)."""
        return self.completion_percentage >= 0.8 and self.buildability_score >= 7.0

    @property
    def missing_cards_count(self) -> int:
        """Calculate number of missing cards."""
        return self.total_cards - self.owned_cards

    @property
    def budget_category(self) -> str:
        """Get budget category based on price."""
        if self.avg_deck_price < 150:
            return "budget"
        elif self.avg_deck_price < 500:
            return "mid"
        elif self.avg_deck_price < 1000:
            return "high"
        else:
            return "cedh"
