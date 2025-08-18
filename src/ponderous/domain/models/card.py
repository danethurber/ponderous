"""Card domain models."""

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Card:
    """Immutable card entity representing a Magic: The Gathering card.

    Represents a Magic: The Gathering card with core attributes.
    """

    name: str
    card_id: str
    mana_cost: str | None = None
    cmc: int | None = None
    color_identity: list[str] | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    rarity: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    image_url: str | None = None
    price_usd: float | None = None
    price_eur: float | None = None

    def __post_init__(self) -> None:
        """Validate card data after initialization."""
        if not self.name.strip():
            raise ValueError("Card name cannot be empty")
        if not self.card_id.strip():
            raise ValueError("Card ID cannot be empty")

    @property
    def is_commander_legal(self) -> bool:
        """Check if card can be a commander."""
        if not self.type_line:
            return False
        return "Legendary" in self.type_line and "Creature" in self.type_line

    @property
    def color_identity_str(self) -> str:
        """Get color identity as a string."""
        if not self.color_identity:
            return "C"  # Colorless
        return "".join(sorted(self.color_identity))


class CardData(BaseModel):
    """Card data with inclusion and synergy information for deck analysis."""

    name: str = Field(..., description="Card name")
    card_id: str = Field(..., description="Unique card identifier")
    inclusion_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Inclusion rate in decks (0-1)"
    )
    synergy_score: float = Field(
        default=0.0, description="Synergy score with commander"
    )
    category: str = Field(
        default="staple",
        description="Card category (signature, high_synergy, staple, basic)",
    )
    price_usd: float | None = Field(default=None, ge=0.0, description="Price in USD")
    is_basic_land: bool = Field(
        default=False, description="Whether card is a basic land"
    )
    cmc: int | None = Field(default=None, ge=0, description="Converted mana cost")
    color_identity: list[str] | None = Field(default=None, description="Color identity")

    class Config:
        """Pydantic configuration."""

        frozen = True

    @property
    def impact_score(self) -> float:
        """Calculate impact score based on inclusion rate, synergy, and category."""
        category_weights = {
            "signature": 3.0,
            "high_synergy": 2.0,
            "staple": 1.5,
            "basic": 1.0,
        }
        base_weight = category_weights.get(self.category, 1.0)
        return self.inclusion_rate * base_weight * (1.0 + self.synergy_score)

    @property
    def is_high_impact(self) -> bool:
        """Check if card has high impact on deck functionality."""
        return self.impact_score >= 2.0 or self.category in [
            "signature",
            "high_synergy",
        ]


@dataclass(frozen=True)
class MissingCard:
    """Represents a missing card with its impact analysis."""

    card_data: CardData
    estimated_cost: float
    priority_level: str  # "critical", "high", "medium", "low"
    alternatives: list[str]  # Alternative card names

    def __post_init__(self) -> None:
        """Validate missing card data."""
        valid_priorities = {"critical", "high", "medium", "low"}
        if self.priority_level not in valid_priorities:
            raise ValueError(f"Invalid priority level: {self.priority_level}")
        if self.estimated_cost < 0:
            raise ValueError("Estimated cost cannot be negative")

    @property
    def impact_score(self) -> float:
        """Get the impact score from the card data."""
        return self.card_data.impact_score

    @classmethod
    def from_card_data(
        cls,
        card_data: CardData,
        estimated_cost: float | None = None,
        alternatives: list[str] | None = None,
    ) -> "MissingCard":
        """Create missing card from card data with priority calculation."""
        cost = estimated_cost or card_data.price_usd or 0.0

        # Calculate priority based on impact score and cost
        impact = card_data.impact_score
        if impact >= 3.0:
            priority = "critical"
        elif impact >= 2.0:
            priority = "high"
        elif impact >= 1.0:
            priority = "medium"
        else:
            priority = "low"

        return cls(
            card_data=card_data,
            estimated_cost=cost,
            priority_level=priority,
            alternatives=alternatives or [],
        )
