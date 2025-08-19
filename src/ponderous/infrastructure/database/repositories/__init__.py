"""Repository interfaces for data access."""

from .base import BaseRepository
from .collection_repository import CollectionRepository

__all__ = [
    "BaseRepository",
    "CollectionRepository",
]
