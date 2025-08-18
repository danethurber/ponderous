"""User domain models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """User entity representing a collection owner."""

    user_id: str
    username: str
    display_name: str | None = None
    created_at: datetime | None = None
    last_sync: datetime | None = None
    total_cards: int = 0
    total_value: float = 0.0

    def __post_init__(self) -> None:
        """Validate user data after initialization."""
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")
        if not self.username.strip():
            raise ValueError("Username cannot be empty")
        if self.total_cards < 0:
            raise ValueError("Total cards cannot be negative")
        if self.total_value < 0:
            raise ValueError("Total value cannot be negative")

    @property
    def effective_display_name(self) -> str:
        """Get effective display name, falling back to username."""
        return self.display_name or self.username

    @property
    def average_card_value(self) -> float:
        """Calculate average value per card."""
        return self.total_value / self.total_cards if self.total_cards > 0 else 0.0

    def is_collection_stale(self, stale_threshold_hours: int = 24) -> bool:
        """Check if collection data is stale."""
        if not self.last_sync:
            return True

        time_since_sync = datetime.utcnow() - self.last_sync
        return time_since_sync.total_seconds() > (stale_threshold_hours * 3600)
