"""EDHREC data models for scraping and analysis."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EDHRECCard:
    """Represents a card with EDHREC-specific data."""

    name: str
    url_slug: str
    inclusion_rate: float  # 0.0 to 1.0
    synergy_score: float  # -1.0 to 1.0
    category: str  # "signature", "high_synergy", "staple", "basic"
    total_decks: int
    price_usd: float | None = None

    def __post_init__(self) -> None:
        """Validate EDHREC card data."""
        if not (0.0 <= self.inclusion_rate <= 1.0):
            raise ValueError("Inclusion rate must be between 0 and 1")
        if not (-1.0 <= self.synergy_score <= 1.0):
            raise ValueError("Synergy score must be between -1 and 1")
        if self.total_decks < 0:
            raise ValueError("Total decks cannot be negative")


@dataclass(frozen=True)
class EDHRECCommander:
    """Represents commander data from EDHREC."""

    name: str
    url_slug: str
    color_identity: str  # e.g., "RWB", "U", "C"
    total_decks: int
    popularity_rank: int
    avg_deck_price: float
    salt_score: float  # 0.0 to 5.0
    power_level: float  # 1.0 to 10.0
    archetype: str | None = None
    themes: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate commander data."""
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


@dataclass(frozen=True)
class EDHRECDeck:
    """Represents a deck archetype from EDHREC."""

    commander_name: str
    commander_url: str
    archetype: str
    theme: str
    total_decks: int
    avg_price: float
    card_list: list[EDHRECCard]
    budget_range: str  # "budget", "mid", "high", "cedh"

    def __post_init__(self) -> None:
        """Validate deck data."""
        if self.total_decks < 0:
            raise ValueError("Total decks cannot be negative")
        if self.avg_price < 0:
            raise ValueError("Average price cannot be negative")
        if not self.card_list:
            raise ValueError("Deck must have at least one card")

    @property
    def deck_size(self) -> int:
        """Get total number of cards in deck."""
        return len(self.card_list)

    @property
    def signature_cards(self) -> list[EDHRECCard]:
        """Get signature cards for this deck."""
        return [card for card in self.card_list if card.category == "signature"]

    @property
    def high_synergy_cards(self) -> list[EDHRECCard]:
        """Get high synergy cards for this deck."""
        return [card for card in self.card_list if card.category == "high_synergy"]

    @property
    def staple_cards(self) -> list[EDHRECCard]:
        """Get staple cards for this deck."""
        return [card for card in self.card_list if card.category == "staple"]


@dataclass
class EDHRECScrapingResult:
    """Result of an EDHREC scraping operation."""

    success: bool
    commanders_found: int
    decks_found: int
    cards_found: int
    processing_time_seconds: float
    scraped_at: datetime
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if scraping had errors."""
        return len(self.errors) > 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate based on found items."""
        if not self.success:
            return 0.0
        total_items = self.commanders_found + self.decks_found
        return 1.0 if total_items > 0 else 0.0
