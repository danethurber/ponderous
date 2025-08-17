"""Collection domain models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class CollectionItem:
    """Represents a card in a user's collection."""

    user_id: str
    source_id: str
    card_id: str
    card_name: str
    quantity: int
    foil_quantity: int = 0
    last_updated: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate collection item data."""
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")
        if not self.card_name.strip():
            raise ValueError("Card name cannot be empty")
        if self.quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if self.foil_quantity < 0:
            raise ValueError("Foil quantity cannot be negative")

    @property
    def total_quantity(self) -> int:
        """Get total quantity including foils."""
        return self.quantity + self.foil_quantity

    def has_card(self, required_quantity: int = 1) -> bool:
        """Check if collection has sufficient quantity of this card."""
        return self.total_quantity >= required_quantity


@dataclass(frozen=True)
class Collection:
    """Represents a user's complete card collection."""

    user_id: str
    items: List[CollectionItem]
    total_cards: int
    unique_cards: int
    total_value: float
    last_updated: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate collection data."""
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")
        if self.total_cards < 0:
            raise ValueError("Total cards cannot be negative")
        if self.unique_cards < 0:
            raise ValueError("Unique cards cannot be negative")
        if self.total_value < 0:
            raise ValueError("Total value cannot be negative")

    @property
    def card_names(self) -> Set[str]:
        """Get set of all card names in collection."""
        return {item.card_name for item in self.items}

    @property
    def average_card_value(self) -> float:
        """Calculate average value per card."""
        return self.total_value / self.total_cards if self.total_cards > 0 else 0.0

    def get_card_quantity(self, card_name: str) -> int:
        """Get total quantity of a specific card."""
        for item in self.items:
            if item.card_name.lower() == card_name.lower():
                return item.total_quantity
        return 0

    def has_card(self, card_name: str, required_quantity: int = 1) -> bool:
        """Check if collection contains sufficient quantity of a card."""
        return self.get_card_quantity(card_name) >= required_quantity

    def has_cards(self, card_names: List[str]) -> Dict[str, bool]:
        """Check availability of multiple cards."""
        return {name: self.has_card(name) for name in card_names}

    @classmethod
    def from_items(cls, user_id: str, items: List[CollectionItem]) -> "Collection":
        """Create collection from list of items."""
        total_cards = sum(item.total_quantity for item in items)
        unique_cards = len(items)
        # For now, total value is 0 - this would be calculated based on card prices
        total_value = 0.0
        last_updated = max(
            (item.last_updated for item in items if item.last_updated), default=None
        )

        return cls(
            user_id=user_id,
            items=items,
            total_cards=total_cards,
            unique_cards=unique_cards,
            total_value=total_value,
            last_updated=last_updated,
        )


class CollectionAnalysis(BaseModel):
    """Analysis of collection strengths and characteristics."""

    total_cards: int = Field(..., ge=0, description="Total number of cards")
    total_value: float = Field(..., ge=0.0, description="Total collection value")
    unique_cards: int = Field(..., ge=0, description="Number of unique cards")

    color_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Card counts by color"
    )
    strongest_colors: List[str] = Field(
        default_factory=list, description="Colors with most support"
    )

    archetype_affinity: Dict[str, float] = Field(
        default_factory=dict, description="Scores for each archetype"
    )
    theme_support: Dict[str, float] = Field(
        default_factory=dict, description="Theme compatibility scores"
    )

    mana_curve_profile: Dict[int, int] = Field(
        default_factory=dict, description="CMC distribution"
    )
    missing_staples: List[str] = Field(
        default_factory=list, description="Key missing cards"
    )

    collection_power_level: float = Field(
        default=5.0, ge=1.0, le=10.0, description="Overall power assessment"
    )

    @property
    def average_card_value(self) -> float:
        """Calculate average value per card."""
        return self.total_value / self.total_cards if self.total_cards > 0 else 0.0

    @property
    def primary_colors(self) -> List[str]:
        """Get primary colors (top 3) from distribution."""
        sorted_colors = sorted(
            self.color_distribution.items(), key=lambda x: x[1], reverse=True
        )
        return [color for color, _ in sorted_colors[:3]]

    @property
    def best_archetypes(self) -> List[str]:
        """Get best supported archetypes (top 3)."""
        sorted_archetypes = sorted(
            self.archetype_affinity.items(), key=lambda x: x[1], reverse=True
        )
        return [archetype for archetype, _ in sorted_archetypes[:3]]

    def get_color_strength(self, color: str) -> float:
        """Get relative strength of a color (0-1)."""
        if not self.color_distribution:
            return 0.0

        color_count = self.color_distribution.get(color, 0)
        max_count = (
            max(self.color_distribution.values()) if self.color_distribution else 1
        )
        return color_count / max_count if max_count > 0 else 0.0
