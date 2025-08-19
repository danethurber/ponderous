"""Collection management application service."""

import logging
from typing import Any

from ponderous.application.use_cases.sync_collection import (
    SyncCollectionRequest,
    SyncCollectionResponse,
    SyncCollectionUseCase,
)
from ponderous.shared.exceptions import PonderousError

logger = logging.getLogger(__name__)


class CollectionService:
    """Application service for collection management operations."""

    def __init__(self) -> None:
        """Initialize collection service."""
        self.sync_use_case = SyncCollectionUseCase()
        logger.info("Initialized CollectionService")

    async def sync_user_collection(
        self,
        username: str,
        source: str = "moxfield",
        force_refresh: bool = False,
        include_profile: bool = True,
    ) -> SyncCollectionResponse:
        """Sync collection data for a user from external source.

        Args:
            username: Username to sync collection for
            source: External source platform
            force_refresh: Whether to force refresh even if recently synced
            include_profile: Whether to include user profile data

        Returns:
            Sync operation result

        Raises:
            PonderousError: If sync operation fails
        """
        if not username or not username.strip():
            raise PonderousError("Username cannot be empty")

        if not self.validate_username_format(username.strip(), source):
            raise PonderousError(f"Invalid username format for {source}: {username}")

        logger.info(f"Starting collection sync for user {username} from {source}")

        try:
            request = SyncCollectionRequest(
                username=username.strip(),
                source=source,
                force_refresh=force_refresh,
                include_profile=include_profile,
            )

            response = await self.sync_use_case.execute(request)

            if response.success:
                logger.info(f"Collection sync successful: {response.sync_summary}")
            else:
                logger.error(f"Collection sync failed: {response.error_message}")

            return response

        except Exception as e:
            logger.error(f"Collection sync failed for {username}: {e}")
            if not isinstance(e, PonderousError):
                raise PonderousError(f"Collection sync failed: {e}") from e
            raise

    def get_sync_history(
        self,
        username: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get sync history for a user.

        Args:
            username: Username to get history for
            limit: Maximum number of records to return

        Returns:
            List of sync history records
        """
        if not username or not username.strip():
            raise PonderousError("Username cannot be empty")

        if limit <= 0:
            raise PonderousError("Limit must be positive")

        logger.info(f"Getting sync history for {username}, limit {limit}")

        try:
            return self.sync_use_case.get_recent_syncs(username.strip(), limit)
        except Exception as e:
            logger.error(f"Failed to get sync history for {username}: {e}")
            raise PonderousError(f"Failed to get sync history: {e}") from e

    def cleanup_old_sync_data(
        self,
        username: str,
        keep_recent: int = 5,
    ) -> bool:
        """Clean up old sync data for a user.

        Args:
            username: Username to clean up data for
            keep_recent: Number of recent syncs to keep

        Returns:
            True if cleanup was successful
        """
        if not username or not username.strip():
            raise PonderousError("Username cannot be empty")

        if keep_recent <= 0:
            raise PonderousError("keep_recent must be positive")

        logger.info(
            f"Cleaning up old sync data for {username}, keeping {keep_recent} recent"
        )

        try:
            success = self.sync_use_case.cleanup_old_data(username.strip(), keep_recent)
            if success:
                logger.info(f"Successfully cleaned up old data for {username}")
            else:
                logger.warning(f"Cleanup may have partially failed for {username}")
            return success
        except Exception as e:
            logger.error(f"Failed to cleanup old data for {username}: {e}")
            raise PonderousError(f"Failed to cleanup old data: {e}") from e

    async def verify_source_connectivity(self, source: str = "moxfield") -> bool:
        """Verify connectivity to external source.

        Args:
            source: Source to verify connectivity for

        Returns:
            True if source is accessible
        """
        logger.info(f"Verifying connectivity to {source}")

        if source.lower() == "moxfield":
            try:
                # Test with a known public user to verify API access
                test_request = SyncCollectionRequest(
                    username="test_connectivity_user",
                    source=source,
                    force_refresh=False,
                    include_profile=False,
                )

                # This will fail for the test user, but should give us API connectivity info
                try:
                    await self.sync_use_case.execute(test_request)
                except Exception as e:
                    # Check if error is about user not found vs API connectivity
                    error_msg = str(e).lower()
                    if "not found" in error_msg or "404" in error_msg:
                        # API is accessible but user doesn't exist - this is good
                        logger.info(f"API connectivity verified for {source}")
                        return True
                    else:
                        # Actual API connectivity issue
                        logger.error(f"API connectivity failed for {source}: {e}")
                        return False

                # If we get here without exception, API is working
                return True

            except Exception as e:
                logger.error(f"Failed to verify connectivity to {source}: {e}")
                return False
        else:
            raise PonderousError(f"Unsupported source: {source}")

    def get_supported_sources(self) -> list[str]:
        """Get list of supported collection sources.

        Returns:
            List of supported source names
        """
        return ["moxfield"]

    def validate_username_format(self, username: str, source: str = "moxfield") -> bool:
        """Validate username format for a specific source.

        Args:
            username: Username to validate
            source: Source platform to validate for

        Returns:
            True if username format is valid
        """
        if not username or not username.strip():
            return False

        username = username.strip()

        if source.lower() == "moxfield":
            # Moxfield username validation
            if len(username) < 2 or len(username) > 30:
                return False

            # Check for basic character requirements
            if not username.replace("_", "").replace("-", "").isalnum():
                return False

            # Can't start or end with special characters
            return not (
                username.startswith(("_", "-")) or username.endswith(("_", "-"))
            )
        else:
            raise PonderousError(f"Unsupported source: {source}")
