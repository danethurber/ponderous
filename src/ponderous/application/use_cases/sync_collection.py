"""Collection synchronization use case."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import dlt
from dlt.pipeline import Pipeline

from ponderous.infrastructure.etl.collection_transformer import (
    normalize_collection_data,
    normalize_collection_metadata,
)
from ponderous.infrastructure.etl.moxfield_source import (
    moxfield_collection_source,
)
from ponderous.infrastructure.moxfield.exceptions import MoxfieldAPIError
from ponderous.shared.config import get_config
from ponderous.shared.exceptions import PonderousError

logger = logging.getLogger(__name__)


@dataclass
class SyncCollectionRequest:
    """Request for collection synchronization."""

    username: str
    source: str = "moxfield"
    force_refresh: bool = False
    include_profile: bool = True

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.username or not self.username.strip():
            raise ValueError("Username cannot be empty")

        if self.source.lower() not in ["moxfield"]:
            raise ValueError(f"Unsupported source: {self.source}")

        self.username = self.username.strip()
        self.source = self.source.lower()


@dataclass
class SyncCollectionResponse:
    """Response from collection synchronization."""

    success: bool
    username: str
    source: str

    # Collection statistics
    total_cards: int = 0
    unique_cards: int = 0

    # Sync metadata
    sync_started_at: datetime | None = None
    sync_completed_at: datetime | None = None
    sync_duration_seconds: float | None = None

    # Processing results
    items_processed: int = 0
    items_successful: int = 0
    items_failed: int = 0

    # Error information
    error_message: str | None = None
    error_type: str | None = None

    # Additional metadata
    force_refresh: bool = False
    pipeline_run_id: str | None = None

    @property
    def sync_summary(self) -> str:
        """Get a human-readable sync summary."""
        if not self.success:
            return f"Sync failed for {self.username}: {self.error_message}"

        duration = (
            f" in {self.sync_duration_seconds:.1f}s"
            if self.sync_duration_seconds
            else ""
        )
        return f"Successfully synced {self.unique_cards} unique cards ({self.total_cards} total) for {self.username}{duration}"


class SyncCollectionUseCase:
    """Use case for synchronizing collection data from external sources."""

    def __init__(self) -> None:
        """Initialize the sync collection use case."""
        self.config = get_config()
        logger.info("Initialized SyncCollectionUseCase")

    async def execute(self, request: SyncCollectionRequest) -> SyncCollectionResponse:
        """Execute collection synchronization.

        Args:
            request: Sync collection request

        Returns:
            Sync collection response with results

        Raises:
            PonderousError: If sync fails
        """
        logger.info(
            f"Starting collection sync for {request.username} from {request.source}"
        )

        response = SyncCollectionResponse(
            success=False,
            username=request.username,
            source=request.source,
            force_refresh=request.force_refresh,
            sync_started_at=datetime.now(),
        )

        try:
            if request.source == "moxfield":
                await self._sync_moxfield_collection(request, response)
            else:
                raise ValueError(f"Unsupported source: {request.source}")

            response.success = True
            logger.info(
                f"Collection sync completed successfully: {response.sync_summary}"
            )

        except Exception as e:
            response.error_message = str(e)
            response.error_type = type(e).__name__
            logger.error(f"Collection sync failed for {request.username}: {e}")

            if not isinstance(e, MoxfieldAPIError | PonderousError):
                raise PonderousError(f"Collection sync failed: {e}") from e
            raise

        finally:
            response.sync_completed_at = datetime.now()
            if response.sync_started_at and response.sync_completed_at:
                response.sync_duration_seconds = (
                    response.sync_completed_at - response.sync_started_at
                ).total_seconds()

        return response

    async def _sync_moxfield_collection(
        self, request: SyncCollectionRequest, response: SyncCollectionResponse
    ) -> None:
        """Sync collection from Moxfield API using dlt pipeline."""
        logger.info(f"Starting Moxfield sync for {request.username}")

        # Create dlt pipeline
        pipeline_name = f"moxfield_sync_{request.username}"
        pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination="duckdb",
            dataset_name="ponderous",
            progress="log",
        )

        try:
            # Prepare data sources
            collection_source = moxfield_collection_source(
                request.username, request.force_refresh
            )

            sources = [
                normalize_collection_data,
                normalize_collection_metadata,
            ]

            if request.include_profile:
                # Profile data will be included via collection source
                logger.info("Profile data inclusion requested")

            # Run the pipeline
            logger.info(f"Running dlt pipeline for {request.username}")
            run_response = pipeline.run(
                collection_source, *sources, table_name="collections"
            )

            # Store pipeline run information
            response.pipeline_run_id = getattr(
                run_response, "pipeline_run_id", "unknown"
            )

            # Extract metrics from pipeline run
            # Use getattr to safely access dlt attributes that may not be typed
            try:
                jobs = getattr(run_response, "jobs", [])
                for job_info in jobs:
                    completed_jobs = getattr(job_info, "completed_jobs", [])
                    for job in completed_jobs:
                        metrics = getattr(job, "metrics", {})
                        for _table_name, table_metrics in metrics.items():
                            if (
                                isinstance(table_metrics, dict)
                                and "items_count" in table_metrics
                            ):
                                response.items_processed += table_metrics["items_count"]
                                response.items_successful = response.items_processed
            except Exception as e:
                logger.warning(f"Could not extract pipeline metrics: {e}")

            # Get collection statistics from the pipeline
            # Extract collection statistics
            try:
                await self._extract_collection_stats(
                    pipeline, request.username, response
                )
            except Exception as e:
                logger.warning(f"Could not extract collection stats: {e}")

            logger.info(
                f"dlt pipeline completed for {request.username}: {response.items_processed} items processed"
            )

        except Exception as e:
            logger.error(f"dlt pipeline failed for {request.username}: {e}")
            raise PonderousError(f"ETL pipeline failed: {e}") from e

    async def _extract_collection_stats(
        self,
        pipeline: Pipeline,
        username: str,
        response: SyncCollectionResponse,
    ) -> None:
        """Extract collection statistics from pipeline results."""
        try:
            # Query the pipeline's destination to get stats
            with pipeline.sql_client() as client:
                # Get collection metadata
                result = client.execute_sql(
                    """
                    SELECT total_cards, unique_cards
                    FROM collections
                    WHERE extraction_type = 'collection_metadata'
                    AND user_id = ?
                    ORDER BY extracted_at DESC
                    LIMIT 1
                    """,
                    username,
                )

                if result:
                    row = result[0] if isinstance(result, list) else result
                    if hasattr(row, "get"):
                        response.total_cards = row.get("total_cards", 0)
                        response.unique_cards = row.get("unique_cards", 0)
                    else:
                        # Handle tuple or other row format
                        response.total_cards = 0
                        response.unique_cards = 0
                    logger.info(
                        f"Extracted stats: {response.unique_cards} unique, {response.total_cards} total"
                    )
                else:
                    logger.warning(f"No collection metadata found for {username}")

        except Exception as e:
            logger.warning(f"Failed to extract collection stats for {username}: {e}")
            # Don't fail the entire sync for stats extraction issues

    def get_recent_syncs(self, username: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent sync history for a user.

        Args:
            username: Username to get sync history for
            limit: Maximum number of records to return

        Returns:
            List of recent sync records
        """
        try:
            pipeline = dlt.pipeline(
                pipeline_name=f"moxfield_sync_{username}",
                destination="duckdb",
                dataset_name="ponderous",
            )

            with pipeline.sql_client() as client:
                result = client.execute_sql(
                    """
                    SELECT
                        user_id,
                        source_id,
                        total_cards,
                        unique_cards,
                        extracted_at,
                        force_refresh
                    FROM collections
                    WHERE extraction_type = 'collection_metadata'
                    AND user_id = ?
                    ORDER BY extracted_at DESC
                    LIMIT ?
                    """,
                    username,
                    limit,
                )

                return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(f"Failed to get sync history for {username}: {e}")
            return []

    def cleanup_old_data(self, username: str, keep_recent: int = 5) -> bool:
        """Clean up old sync data, keeping only recent records.

        Args:
            username: Username to clean up data for
            keep_recent: Number of recent syncs to keep

        Returns:
            True if cleanup was successful
        """
        try:
            pipeline = dlt.pipeline(
                pipeline_name=f"moxfield_sync_{username}",
                destination="duckdb",
                dataset_name="ponderous",
            )

            with pipeline.sql_client() as client:
                # Delete old records, keeping the most recent ones
                client.execute_sql(
                    """
                    DELETE FROM collections
                    WHERE user_id = ?
                    AND extracted_at NOT IN (
                        SELECT extracted_at
                        FROM collections
                        WHERE user_id = ?
                        ORDER BY extracted_at DESC
                        LIMIT ?
                    )
                    """,
                    username,
                    username,
                    keep_recent,
                )

                logger.info(
                    f"Cleaned up old sync data for {username}, kept {keep_recent} recent syncs"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to cleanup old data for {username}: {e}")
            return False
