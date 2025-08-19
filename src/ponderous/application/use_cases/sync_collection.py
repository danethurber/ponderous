"""Collection synchronization use case."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import dlt
from dlt.pipeline import Pipeline

from ponderous.infrastructure.etl.moxfield_source import (
    moxfield_collection_source,
)
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

        if not self.source or not self.source.strip():
            raise ValueError("Source cannot be empty")

        self.username = self.username.strip()
        self.source = self.source.strip().lower()

        if self.source not in ["moxfield"]:
            raise ValueError(f"Unsupported source: {self.source}")


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

            # Don't re-raise, return the error response instead
            # This allows the caller to handle the error gracefully

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

        pipeline_name = f"moxfield_sync_{request.username}"
        pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination="duckdb",
            dataset_name="ponderous",
            progress="log",
        )

        try:
            collection_source = moxfield_collection_source(
                request.username,
                config=self.config.moxfield,
                include_profile=request.include_profile,
            )

            if request.include_profile:
                logger.info("Profile data inclusion requested")

            logger.info(f"Running dlt pipeline for {request.username}")
            run_response = pipeline.run(collection_source, table_name="collections")

            response.pipeline_run_id = getattr(
                run_response, "pipeline_run_id", "unknown"
            )

            try:
                jobs = getattr(run_response, "jobs", [])
                for job_info in jobs:
                    failed_jobs = getattr(job_info, "failed_jobs", [])
                    if failed_jobs:
                        # Pipeline had failures, collect error information
                        error_messages = []
                        for failed_job in failed_jobs:
                            exception = getattr(failed_job, "exception", None)
                            if exception:
                                error_messages.append(str(exception))

                        error_msg = (
                            "; ".join(error_messages)
                            if error_messages
                            else "Pipeline execution failed"
                        )
                        raise PonderousError(f"Pipeline failed: {error_msg}")
            except PonderousError:
                raise
            except Exception as e:
                logger.warning(f"Could not check pipeline failures: {e}")

            try:
                metrics = getattr(run_response, "metrics", None)
                if metrics and isinstance(metrics, dict):
                    for _table_name, table_metrics in metrics.items():
                        if isinstance(table_metrics, dict):
                            # Look for load metrics (items successfully loaded)
                            if "items_count" in table_metrics:
                                response.items_processed += table_metrics["items_count"]
                                response.items_successful = response.items_processed
                            elif "rows_count" in table_metrics:
                                response.items_processed += table_metrics["rows_count"]
                                response.items_successful = response.items_processed

                # Fallback: extract from load_info if direct metrics aren't available
                if response.items_processed == 0:
                    load_info = getattr(run_response, "load_info", None)
                    if load_info and hasattr(load_info, "tables"):
                        tables = getattr(load_info, "tables", {})
                        if isinstance(tables, dict):
                            for _table_name, table_info in tables.items():
                                rows_count = getattr(table_info, "rows_count", 0)
                                if rows_count:
                                    response.items_processed += rows_count
                                    response.items_successful = response.items_processed
            except Exception as e:
                logger.warning(f"Could not extract pipeline metrics: {e}")

            try:
                await self._extract_collection_stats(
                    pipeline, request.username, response, request.include_profile
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
        include_profile: bool,
    ) -> None:
        """Extract collection statistics from pipeline results."""
        try:
            with pipeline.sql_client() as client:
                # Get collection metadata from dlt collections table
                result = client.execute_sql(
                    """
                    SELECT COUNT(*) as unique_cards, SUM(total_quantity) as total_cards
                    FROM collections
                    WHERE username = ?
                    """,
                    username,
                )

                if result:
                    row = result[0] if isinstance(result, list) else result
                    if hasattr(row, "get"):
                        response.unique_cards = row.get("unique_cards", 0) or 0
                        response.total_cards = row.get("total_cards", 0) or 0
                    else:
                        # Handle tuple or other row format
                        if isinstance(row, tuple | list) and len(row) >= 2:
                            response.unique_cards = row[0] or 0
                            response.total_cards = row[1] or 0
                        else:
                            response.total_cards = 0
                            response.unique_cards = 0

                    # Set items_processed to unique_cards + 1 (profile) if not already set
                    if response.items_processed == 0:
                        response.items_processed = response.unique_cards + (
                            1 if include_profile else 0
                        )
                        response.items_successful = response.items_processed

                    logger.info(
                        f"Extracted stats: {response.unique_cards} unique, {response.total_cards} total, {response.items_processed} processed"
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
                        username as user_id,
                        'moxfield' as source_id,
                        SUM(total_quantity) as total_cards,
                        COUNT(*) as unique_cards,
                        MAX(extracted_at) as extracted_at,
                        FALSE as force_refresh
                    FROM collections
                    WHERE username = ?
                    GROUP BY username
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
