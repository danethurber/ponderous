"""dlt source for Moxfield collection data extraction."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import dlt

from ponderous.infrastructure.moxfield import MoxfieldClient
from ponderous.shared.config import MoxfieldConfig, get_config

logger = logging.getLogger(__name__)


async def moxfield_user_profile_source(
    username: str, config: MoxfieldConfig | None = None
) -> AsyncGenerator[dict[str, Any], None]:
    """Extract user profile data from Moxfield API.

    Args:
        username: Moxfield username
        config: Optional Moxfield configuration

    Yields:
        User profile data

    Raises:
        MoxfieldAPIError: When API request fails
        ValueError: When username is empty
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    username = username.strip()
    logger.info(f"Starting Moxfield profile extraction for user: {username}")

    if config is None:
        config = get_config().moxfield

    async with MoxfieldClient(config) as client:
        profile = await client.get_user_profile(username)

        yield {
            "username": profile.username,
            "display_name": profile.display_name,
            "public_profile": profile.public_profile,
            "collection_count": profile.collection_count,
            "deck_count": profile.deck_count,
            "extracted_at": datetime.now(UTC),
        }


async def moxfield_collection_items(
    username: str, config: MoxfieldConfig | None = None
) -> AsyncGenerator[dict[str, Any], None]:
    """Extract collection items from Moxfield API.

    Args:
        username: Moxfield username
        config: Optional Moxfield configuration

    Yields:
        Collection item data

    Raises:
        MoxfieldAPIError: When API request fails
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    username = username.strip()
    logger.info(f"Starting Moxfield collection extraction for user: {username}")

    if config is None:
        config = get_config().moxfield

    async with MoxfieldClient(config) as client:
        collection_response = await client.get_collection(username)

        for _card_key, card_data in collection_response.collection.items():
            # Transform the MoxfieldCardData to match test expectations
            # Calculate total value with foil pricing fallback
            foil_price = card_data.price_usd_foil or card_data.price_usd or 0.0
            total_value = (card_data.quantity * (card_data.price_usd or 0.0)) + (
                card_data.foil_quantity * foil_price
            )

            yield {
                "card_id": card_data.id,
                "name": card_data.name,
                "quantity": card_data.quantity,
                "foil_quantity": card_data.foil_quantity,
                "price_usd": card_data.price_usd,
                "price_usd_foil": card_data.price_usd_foil,
                "total_quantity": card_data.total_quantity,
                "total_value": total_value,
                "set_code": card_data.set_code,
                "rarity": card_data.rarity,
                "mana_cost": card_data.cmc,
                "color_identity": card_data.color_identity,
                "type_line": card_data.type_line,
                "oracle_text": card_data.oracle_text,
                "username": username,
                "extracted_at": datetime.now(UTC),
            }


@dlt.source(name="moxfield_collection")
def moxfield_collection_source(
    username: str, config: MoxfieldConfig | None = None, include_profile: bool = True
) -> list[Any]:
    """dlt source that combines user profile and collection data.

    Args:
        username: Moxfield username
        config: Optional Moxfield configuration
        include_profile: Whether to include user profile data

    Returns:
        dlt source with user_profile and collection_items resources
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    resources = []

    if include_profile:

        @dlt.resource(name="user_profile")
        def user_profile() -> Any:
            import asyncio

            async def _run_async() -> list[dict[str, Any]]:
                items = []
                async for item in moxfield_user_profile_source(username, config=config):
                    items.append(item)
                return items

            # Handle both existing event loop and no event loop scenarios
            try:
                # Try to get existing event loop
                asyncio.get_running_loop()
                # If we're in an event loop, create a task and run it
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run_async())
                    items = future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                items = asyncio.run(_run_async())

            yield from items

        resources.append(user_profile())

    @dlt.resource(name="collection_items")
    def collection_items() -> Any:
        import asyncio

        async def _run_async() -> list[dict[str, Any]]:
            items = []
            async for item in moxfield_collection_items(username, config=config):
                items.append(item)
            return items

        # Handle both existing event loop and no event loop scenarios
        try:
            # Try to get existing event loop
            asyncio.get_running_loop()
            # If we're in an event loop, create a task and run it
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _run_async())
                items = future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            items = asyncio.run(_run_async())
        yield from items

    resources.append(collection_items())
    return resources
