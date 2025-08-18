"""dlt source for Moxfield collection data extraction."""

import logging
from collections.abc import AsyncGenerator, Iterator
from datetime import datetime
from typing import Any

import dlt

from ponderous.infrastructure.moxfield import MoxfieldClient
from ponderous.infrastructure.moxfield.exceptions import MoxfieldAPIError
from ponderous.shared.config import get_config

logger = logging.getLogger(__name__)


@dlt.source
def moxfield_collection_source(
    username: str, force_refresh: bool = False
) -> Iterator[dict[str, Any]]:
    """Extract collection data from Moxfield API.

    This is a dlt source that provides collection data for a specific user
    from the Moxfield API with proper error handling and data validation.

    Args:
        username: Moxfield username to extract collection for
        force_refresh: If True, bypasses any caching and forces fresh data

    Yields:
        Collection items with standardized schema

    Raises:
        MoxfieldAPIError: When API request fails
        ValueError: When username is invalid
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    username = username.strip()
    logger.info(f"Starting Moxfield collection extraction for user: {username}")

    config = get_config()

    async def _extract_collection() -> AsyncGenerator[dict[str, Any], None]:
        """Async extraction function."""
        async with MoxfieldClient(config.moxfield) as client:
            try:
                # First verify the user exists
                await client.verify_username(username)
                logger.info(f"Verified user {username} exists")

                # Get the collection data
                collection_response = await client.get_collection(username)
                logger.info(
                    f"Retrieved {collection_response.unique_cards} unique cards for {username}"
                )

                # Yield metadata first
                yield {
                    "extraction_type": "collection_metadata",
                    "username": username,
                    "total_cards": collection_response.total_cards,
                    "unique_cards": collection_response.unique_cards,
                    "last_updated": collection_response.last_updated,
                    "extracted_at": datetime.now(),
                    "force_refresh": force_refresh,
                }

                # Yield individual cards
                for card in collection_response.card_items:
                    yield {
                        "extraction_type": "collection_item",
                        "username": username,
                        "card_id": card.id,
                        "card_name": card.name,
                        "quantity": card.quantity,
                        "foil_quantity": card.foil_quantity,
                        "etched_quantity": card.etched_quantity,
                        "total_quantity": card.total_quantity,
                        # Card metadata
                        "mana_cost": card.mana_cost,
                        "cmc": card.cmc,
                        "type_line": card.type_line,
                        "oracle_text": card.oracle_text,
                        # Price information
                        "price_usd": card.price_usd,
                        "price_eur": card.price_eur,
                        "price_tix": card.price_tix,
                        # Set information
                        "set_code": card.set_code,
                        "set_name": card.set_name,
                        "collector_number": card.collector_number,
                        "rarity": card.rarity,
                        # Additional metadata
                        "colors": card.colors,
                        "color_identity": card.color_identity,
                        "reserved_list": card.reserved_list,
                        "last_updated": card.last_updated,
                        "extracted_at": datetime.now(),
                    }

            except MoxfieldAPIError as e:
                logger.error(f"Failed to extract collection for {username}: {e}")
                # Yield error information for downstream handling
                yield {
                    "extraction_type": "error",
                    "username": username,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "status_code": getattr(e, "status_code", None),
                    "extracted_at": datetime.now(),
                }
                raise

    # Use dlt's async helper to run the async extraction
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = _extract_collection()
        while True:
            try:
                item = loop.run_until_complete(async_gen.__anext__())
                yield item
            except StopAsyncIteration:
                break
    finally:
        loop.close()


@dlt.resource(name="collection_items")
def moxfield_collection_items(
    username: str, force_refresh: bool = False
) -> Iterator[dict[str, Any]]:
    """dlt resource for collection items only.

    Filters the full source to return only collection items,
    excluding metadata and error records.

    Args:
        username: Moxfield username
        force_refresh: Force fresh data extraction

    Yields:
        Collection item records only
    """
    source_data = moxfield_collection_source(username, force_refresh)

    for item in source_data:
        if item.get("extraction_type") == "collection_item":
            yield item


@dlt.resource(name="collection_metadata")
def moxfield_collection_metadata(
    username: str, force_refresh: bool = False
) -> Iterator[dict[str, Any]]:
    """dlt resource for collection metadata only.

    Filters the full source to return only metadata records,
    excluding individual card items.

    Args:
        username: Moxfield username
        force_refresh: Force fresh data extraction

    Yields:
        Collection metadata records only
    """
    source_data = moxfield_collection_source(username, force_refresh)

    for item in source_data:
        if item.get("extraction_type") == "collection_metadata":
            yield item


@dlt.source
def moxfield_user_profile_source(username: str) -> Iterator[dict[str, Any]]:
    """Extract user profile data from Moxfield API.

    Args:
        username: Moxfield username

    Yields:
        User profile data

    Raises:
        MoxfieldAPIError: When API request fails
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    username = username.strip()
    logger.info(f"Starting Moxfield profile extraction for user: {username}")

    config = get_config()

    async def _extract_profile() -> AsyncGenerator[dict[str, Any], None]:
        """Async profile extraction."""
        async with MoxfieldClient(config.moxfield) as client:
            try:
                profile = await client.get_user_profile(username)

                yield {
                    "username": profile.username,
                    "display_name": profile.display_name,
                    "avatar_url": profile.avatar_url,
                    "created_at": profile.created_at,
                    "public_profile": profile.public_profile,
                    "collection_count": profile.collection_count,
                    "deck_count": profile.deck_count,
                    "extracted_at": datetime.now(),
                }

            except MoxfieldAPIError as e:
                logger.error(f"Failed to extract profile for {username}: {e}")
                yield {
                    "extraction_type": "error",
                    "username": username,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "status_code": getattr(e, "status_code", None),
                    "extracted_at": datetime.now(),
                }
                raise

    # Use dlt's async helper to run the async extraction
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = _extract_profile()
        while True:
            try:
                item = loop.run_until_complete(async_gen.__anext__())
                yield item
            except StopAsyncIteration:
                break
    finally:
        loop.close()
