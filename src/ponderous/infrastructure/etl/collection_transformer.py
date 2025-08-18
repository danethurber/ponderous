"""Data transformation utilities for collection data."""

import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import dlt

from ponderous.domain.models.collection import CollectionItem as DomainCollectionItem

logger = logging.getLogger(__name__)


@dlt.transformer
def normalize_collection_data(
    items: Iterator[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Transform raw collection data to standard domain format.

    Normalizes collection items from Moxfield format to our domain model format,
    handles data validation, and provides consistent field mapping.

    Args:
        items: Raw collection items from Moxfield source

    Yields:
        Normalized collection records in domain model format
    """
    logger.info("Starting collection data normalization")
    processed_count = 0
    error_count = 0

    for item in items:
        try:
            # Skip non-collection items
            if item.get("extraction_type") != "collection_item":
                continue

            # Create normalized record
            normalized = {
                # Primary identifiers
                "user_id": item["username"],
                "source_id": "moxfield",
                "card_id": item["card_id"],
                "card_name": _normalize_card_name(item["card_name"]),
                # Quantities
                "quantity": _validate_quantity(item.get("quantity", 0)),
                "foil_quantity": _validate_quantity(
                    item.get("foil_quantity", 0) + item.get("etched_quantity", 0)
                ),
                "total_quantity": _validate_quantity(item.get("total_quantity", 0)),
                # Timestamps
                "last_updated": _normalize_timestamp(item.get("last_updated")),
                "extracted_at": _normalize_timestamp(item.get("extracted_at")),
                # Card metadata (optional)
                "mana_cost": _normalize_string(item.get("mana_cost")),
                "cmc": _validate_cmc(item.get("cmc")),
                "type_line": _normalize_string(item.get("type_line")),
                "oracle_text": _normalize_string(item.get("oracle_text")),
                # Price information (optional)
                "price_usd": _validate_price(item.get("price_usd")),
                "price_eur": _validate_price(item.get("price_eur")),
                "price_tix": _validate_price(item.get("price_tix")),
                # Set information (optional)
                "set_code": _normalize_string(item.get("set_code")),
                "set_name": _normalize_string(item.get("set_name")),
                "collector_number": _normalize_string(item.get("collector_number")),
                "rarity": _normalize_string(item.get("rarity")),
                # Color information (optional)
                "colors": _normalize_color_list(item.get("colors", [])),
                "color_identity": _normalize_color_list(item.get("color_identity", [])),
                # Flags
                "reserved_list": bool(item.get("reserved_list", False)),
                # Data quality markers
                "data_source": "moxfield_api",
                "transformation_version": "1.0",
            }

            # Validate the record can be converted to domain model
            _validate_domain_compatibility(normalized)

            yield normalized
            processed_count += 1

            if processed_count % 100 == 0:
                logger.info(f"Processed {processed_count} collection items")

        except Exception as e:
            error_count += 1
            logger.error(
                f"Failed to normalize collection item {item.get('card_name', 'unknown')}: {e}"
            )

            # Yield error record for monitoring
            yield {
                "extraction_type": "transformation_error",
                "user_id": item.get("username", "unknown"),
                "card_name": item.get("card_name", "unknown"),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "original_data": item,
                "transformation_version": "1.0",
                "extracted_at": datetime.now(),
            }

    logger.info(
        f"Completed normalization: {processed_count} processed, {error_count} errors"
    )


def _normalize_card_name(name: str | None) -> str:
    """Normalize card name."""
    if not name:
        raise ValueError("Card name cannot be empty")

    # Basic normalization
    normalized = str(name).strip()
    if not normalized:
        raise ValueError("Card name cannot be empty after normalization")

    return normalized


def _validate_quantity(quantity: Any) -> int:
    """Validate and normalize quantity values."""
    if quantity is None:
        return 0

    try:
        qty = int(quantity)
        if qty < 0:
            raise ValueError(f"Quantity cannot be negative: {qty}")
        return qty
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid quantity value: {quantity}") from e


def _validate_cmc(cmc: Any) -> float | None:
    """Validate converted mana cost."""
    if cmc is None:
        return None

    try:
        converted = float(cmc)
        if converted < 0:
            raise ValueError(f"CMC cannot be negative: {converted}")
        return converted
    except (ValueError, TypeError):
        logger.warning(f"Invalid CMC value: {cmc}")
        return None


def _validate_price(price: Any) -> float | None:
    """Validate price values."""
    if price is None:
        return None

    try:
        converted = float(price)
        if converted < 0:
            logger.warning(f"Negative price value: {converted}")
            return None
        return converted
    except (ValueError, TypeError):
        logger.warning(f"Invalid price value: {price}")
        return None


def _normalize_string(value: Any) -> str | None:
    """Normalize string values."""
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized if normalized else None


def _normalize_color_list(colors: Any) -> list[str]:
    """Normalize color lists."""
    if not colors:
        return []

    if isinstance(colors, str):
        # Handle comma-separated string
        return [c.strip().upper() for c in colors.split(",") if c.strip()]

    if isinstance(colors, list | tuple):
        return [str(c).strip().upper() for c in colors if str(c).strip()]

    logger.warning(f"Unexpected color format: {colors}")
    return []


def _normalize_timestamp(timestamp: Any) -> datetime | None:
    """Normalize timestamp values."""
    if timestamp is None:
        return None

    if isinstance(timestamp, datetime):
        return timestamp

    if isinstance(timestamp, str):
        try:
            # Try parsing ISO format
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Could not parse timestamp: {timestamp}")
            return None

    logger.warning(f"Unexpected timestamp format: {timestamp}")
    return None


def _validate_domain_compatibility(record: dict[str, Any]) -> None:
    """Validate that a record can be converted to domain model."""
    try:
        # Test conversion to domain model
        domain_item = DomainCollectionItem(
            user_id=record["user_id"],
            source_id=record["source_id"],
            card_id=record["card_id"],
            card_name=record["card_name"],
            quantity=record["quantity"],
            foil_quantity=record["foil_quantity"],
            last_updated=record["last_updated"],
        )
        # If we get here, the record is valid
        logger.debug(f"Validated domain compatibility for {domain_item.card_name}")

    except Exception as e:
        raise ValueError(f"Record incompatible with domain model: {e}") from e


@dlt.transformer
def normalize_collection_metadata(
    items: Iterator[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Transform collection metadata to standard format.

    Args:
        items: Raw collection metadata from Moxfield source

    Yields:
        Normalized metadata records
    """
    logger.info("Starting collection metadata normalization")

    for item in items:
        try:
            # Skip non-metadata items
            if item.get("extraction_type") != "collection_metadata":
                continue

            normalized = {
                "user_id": item["username"],
                "source_id": "moxfield",
                "total_cards": _validate_quantity(item.get("total_cards", 0)),
                "unique_cards": _validate_quantity(item.get("unique_cards", 0)),
                "last_updated": _normalize_timestamp(item.get("last_updated")),
                "extracted_at": _normalize_timestamp(item.get("extracted_at")),
                "force_refresh": bool(item.get("force_refresh", False)),
                "data_source": "moxfield_api",
                "transformation_version": "1.0",
            }

            yield normalized
            logger.info(f"Normalized metadata for user {normalized['user_id']}")

        except Exception as e:
            logger.error(f"Failed to normalize metadata item: {e}")
            yield {
                "extraction_type": "transformation_error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "original_data": item,
                "transformation_version": "1.0",
                "extracted_at": datetime.now(),
            }
