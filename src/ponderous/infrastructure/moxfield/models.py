"""Moxfield API data models and DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ponderous.domain.models.collection import CollectionItem as DomainCollectionItem


class UserProfile(BaseModel):
    """Moxfield user profile data."""

    username: str = Field(..., min_length=1, description="Moxfield username")
    display_name: str | None = Field(None, description="User display name")
    avatar_url: str | None = Field(None, description="User avatar URL")
    created_at: datetime | None = Field(None, description="Account creation date")
    public_profile: bool = Field(default=True, description="Whether profile is public")
    collection_count: int | None = Field(
        None, ge=0, description="Number of cards in collection"
    )
    deck_count: int | None = Field(None, ge=0, description="Number of decks")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()


class MoxfieldCardData(BaseModel):
    """Individual card data from Moxfield API."""

    id: str = Field(..., description="Card ID")
    name: str = Field(..., description="Card name")
    quantity: int = Field(..., ge=0, description="Regular quantity")
    foil_quantity: int = Field(
        default=0, ge=0, description="Foil quantity", alias="foilQuantity"
    )
    etched_quantity: int = Field(
        default=0, ge=0, description="Etched quantity", alias="etchedQuantity"
    )

    # Card metadata
    mana_cost: str | None = Field(None, description="Mana cost", alias="manaCost")
    cmc: float | None = Field(None, ge=0, description="Converted mana cost")
    type_line: str | None = Field(None, description="Card type", alias="type")
    oracle_text: str | None = Field(None, description="Card text", alias="oracleText")

    # Price information
    price_usd: float | None = Field(
        None, ge=0, description="USD price", alias="priceUsd"
    )
    price_eur: float | None = Field(
        None, ge=0, description="EUR price", alias="priceEur"
    )
    price_tix: float | None = Field(
        None, ge=0, description="MTGO Tix price", alias="priceTix"
    )

    # Set information
    set_code: str | None = Field(None, description="Set code", alias="set")
    set_name: str | None = Field(None, description="Set name", alias="setName")
    collector_number: str | None = Field(
        None, description="Collector number", alias="collectorNumber"
    )
    rarity: str | None = Field(None, description="Card rarity")

    # Additional metadata
    colors: list[str] = Field(default_factory=list, description="Card colors")
    color_identity: list[str] = Field(
        default_factory=list, description="Color identity", alias="colorIdentity"
    )
    reserved_list: bool = Field(
        default=False, description="Reserved list status", alias="reservedList"
    )

    last_updated: datetime | None = Field(
        None, description="Last updated timestamp", alias="lastUpdated"
    )

    class Config:
        populate_by_name = True

    @property
    def total_quantity(self) -> int:
        """Get total quantity including all variants."""
        return self.quantity + self.foil_quantity + self.etched_quantity

    def to_domain_item(
        self, user_id: str, source_id: str = "moxfield"
    ) -> DomainCollectionItem:
        """Convert to domain collection item."""
        return DomainCollectionItem(
            user_id=user_id,
            source_id=source_id,
            card_id=self.id,
            card_name=self.name,
            quantity=self.quantity,
            foil_quantity=self.foil_quantity + self.etched_quantity,
            last_updated=self.last_updated,
        )


class CollectionResponse(BaseModel):
    """Moxfield collection API response."""

    username: str = Field(..., description="Collection owner username")
    collection: dict[str, MoxfieldCardData] = Field(
        default_factory=dict, description="Collection cards"
    )
    last_updated: datetime | None = Field(
        None, description="Collection last updated", alias="lastUpdated"
    )
    total_cards: int = Field(default=0, ge=0, description="Total number of cards")
    unique_cards: int = Field(default=0, ge=0, description="Number of unique cards")

    class Config:
        populate_by_name = True

    @field_validator("collection", mode="before")
    @classmethod
    def validate_collection(cls, v: Any) -> dict[str, MoxfieldCardData]:
        """Validate and convert collection data."""
        if not isinstance(v, dict):
            raise ValueError("Collection must be a dictionary")

        validated_collection = {}
        for card_id, card_data in v.items():
            if isinstance(card_data, dict):
                validated_collection[card_id] = MoxfieldCardData(**card_data)
            elif isinstance(card_data, MoxfieldCardData):
                validated_collection[card_id] = card_data
            else:
                raise ValueError(f"Invalid card data for {card_id}")

        return validated_collection

    @property
    def card_items(self) -> list[MoxfieldCardData]:
        """Get list of all card items."""
        return list(self.collection.values())

    def to_domain_items(self, user_id: str) -> list[DomainCollectionItem]:
        """Convert all cards to domain collection items."""
        return [card.to_domain_item(user_id) for card in self.card_items]

    def calculate_totals(self) -> tuple[int, int]:
        """Calculate total and unique card counts."""
        total_cards = sum(card.total_quantity for card in self.card_items)
        unique_cards = len(self.collection)
        return total_cards, unique_cards


class DeckResponse(BaseModel):
    """Moxfield deck API response."""

    id: str = Field(..., description="Deck ID")
    name: str = Field(..., description="Deck name")
    format: str = Field(..., description="Deck format")
    description: str | None = Field(None, description="Deck description")

    # Commander information
    commanders: list[MoxfieldCardData] = Field(
        default_factory=list, description="Commander cards"
    )
    companions: list[MoxfieldCardData] = Field(
        default_factory=list, description="Companion cards"
    )

    # Deck composition
    mainboard: dict[str, MoxfieldCardData] = Field(
        default_factory=dict, description="Mainboard cards"
    )
    sideboard: dict[str, MoxfieldCardData] = Field(
        default_factory=dict, description="Sideboard cards"
    )
    maybeboard: dict[str, MoxfieldCardData] = Field(
        default_factory=dict, description="Maybeboard cards"
    )

    # Deck metadata
    public: bool = Field(default=False, description="Whether deck is public")
    last_updated: datetime | None = Field(
        None, description="Last updated timestamp", alias="lastUpdated"
    )
    created_at: datetime | None = Field(
        None, description="Creation timestamp", alias="createdAt"
    )

    # Statistics
    card_count: int = Field(default=0, ge=0, description="Total card count")
    average_cmc: float | None = Field(
        None, ge=0, description="Average CMC", alias="avgCMC"
    )

    # Tags and categorization
    tags: list[str] = Field(default_factory=list, description="Deck tags")
    archetype: str | None = Field(None, description="Deck archetype")

    class Config:
        populate_by_name = True

    @property
    def commander_names(self) -> list[str]:
        """Get list of commander names."""
        return [commander.name for commander in self.commanders]

    @property
    def all_cards(self) -> list[MoxfieldCardData]:
        """Get all cards from all zones."""
        all_cards = []
        all_cards.extend(self.commanders)
        all_cards.extend(self.companions)
        all_cards.extend(self.mainboard.values())
        all_cards.extend(self.sideboard.values())
        all_cards.extend(self.maybeboard.values())
        return all_cards


class CollectionItem(BaseModel):
    """Simple collection item for API responses."""

    card_name: str = Field(..., description="Card name")
    quantity: int = Field(..., ge=0, description="Card quantity")
    foil_quantity: int = Field(default=0, ge=0, description="Foil quantity")
    price_usd: float | None = Field(None, ge=0, description="USD price")

    @property
    def total_quantity(self) -> int:
        """Get total quantity including foils."""
        return self.quantity + self.foil_quantity
