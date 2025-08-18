"""Tests for SyncCollectionUseCase."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from ponderous.application.use_cases.sync_collection import (
    SyncCollectionRequest,
    SyncCollectionResponse,
    SyncCollectionUseCase,
)


class TestSyncCollectionRequest:
    """Test suite for SyncCollectionRequest."""

    def test_sync_collection_request_valid(self) -> None:
        """Test SyncCollectionRequest creation with valid data."""
        request = SyncCollectionRequest(
            username="testuser",
            source="moxfield",
            force_refresh=True,
            include_profile=False,
        )

        assert request.username == "testuser"
        assert request.source == "moxfield"
        assert request.force_refresh is True
        assert request.include_profile is False

    def test_sync_collection_request_defaults(self) -> None:
        """Test SyncCollectionRequest with default values."""
        request = SyncCollectionRequest(
            username="testuser",
            source="moxfield",
        )

        assert request.username == "testuser"
        assert request.source == "moxfield"
        assert request.force_refresh is False
        assert request.include_profile is True

    def test_sync_collection_request_empty_username(self) -> None:
        """Test SyncCollectionRequest validation with empty username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            SyncCollectionRequest(
                username="",
                source="moxfield",
            )

    def test_sync_collection_request_empty_source(self) -> None:
        """Test SyncCollectionRequest validation with empty source."""
        with pytest.raises(ValueError, match="Source cannot be empty"):
            SyncCollectionRequest(
                username="testuser",
                source="",
            )

    def test_sync_collection_request_whitespace_handling(self) -> None:
        """Test SyncCollectionRequest handles whitespace correctly."""
        request = SyncCollectionRequest(
            username="  testuser  ",
            source="  moxfield  ",
        )

        assert request.username == "testuser"
        assert request.source == "moxfield"


class TestSyncCollectionResponse:
    """Test suite for SyncCollectionResponse."""

    def test_sync_collection_response_success(self) -> None:
        """Test SyncCollectionResponse for successful sync."""
        response = SyncCollectionResponse(
            success=True,
            username="testuser",
            source="moxfield",
            unique_cards=500,
            total_cards=1200,
            items_processed=500,
            sync_duration_seconds=45.7,
        )

        assert response.success is True
        assert response.username == "testuser"
        assert response.source == "moxfield"
        assert response.unique_cards == 500
        assert response.total_cards == 1200
        assert response.items_processed == 500
        assert response.sync_duration_seconds == 45.7
        assert response.error_message is None
        assert "500 unique cards" in response.sync_summary

    def test_sync_collection_response_failure(self) -> None:
        """Test SyncCollectionResponse for failed sync."""
        response = SyncCollectionResponse(
            success=False,
            username="testuser",
            source="moxfield",
            error_message="API connection failed",
        )

        assert response.success is False
        assert response.username == "testuser"
        assert response.source == "moxfield"
        assert response.unique_cards == 0
        assert response.total_cards == 0
        assert response.items_processed == 0
        assert response.sync_duration_seconds is None
        assert response.error_message == "API connection failed"
        assert "failed" in response.sync_summary.lower()

    def test_sync_collection_response_summary_formatting(self) -> None:
        """Test sync summary formatting."""
        response = SyncCollectionResponse(
            success=True,
            username="testuser",
            source="moxfield",
            unique_cards=1234,
            total_cards=5678,
            items_processed=1234,
            sync_duration_seconds=123.45,
        )

        summary = response.sync_summary
        assert "1234 unique cards" in summary
        assert "5678 total" in summary
        assert "123.5s" in summary or "123.45s" in summary


class TestSyncCollectionUseCase:
    """Test suite for SyncCollectionUseCase."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def use_case(self, temp_db_path: Path) -> SyncCollectionUseCase:
        """Create SyncCollectionUseCase instance for testing."""
        with patch(
            "ponderous.application.use_cases.sync_collection.get_config"
        ) as mock_config:
            # Mock the config to use temp database
            mock_config.return_value.database.path = str(temp_db_path)
            mock_config.return_value.database.memory = False
            return SyncCollectionUseCase()

    @pytest.fixture
    def sample_request(self) -> SyncCollectionRequest:
        """Create sample sync request."""
        return SyncCollectionRequest(
            username="testuser",
            source="moxfield",
            force_refresh=False,
            include_profile=True,
        )

    @pytest.mark.asyncio
    async def test_execute_success(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test successful use case execution."""
        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            # Mock dlt pipeline
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []
            mock_run_result.jobs[0].completed_jobs = [Mock()]
            mock_run_result.jobs[0].completed_jobs[0].metrics = {
                "user_profile": {"items_count": 1},
                "collection_items": {"items_count": 500},
            }

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                response = await use_case.execute(sample_request)

                # Verify response
                assert response.success is True
                assert response.username == "testuser"
                assert response.source == "moxfield"
                assert response.items_processed == 501  # 1 profile + 500 items
                assert response.sync_duration_seconds is not None
                assert response.sync_duration_seconds > 0

                # Verify mocks were called correctly
                mock_source.assert_called_once_with("testuser", config=None)
                mock_pipeline.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_config(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test use case execution with custom config."""
        with (
            patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt,
            patch(
                "ponderous.application.use_cases.sync_collection.get_config"
            ) as mock_get_config,
        ):
            # Setup mocks
            mock_config = Mock()
            mock_config.moxfield = Mock()
            mock_get_config.return_value = mock_config

            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []
            mock_run_result.jobs[0].completed_jobs = [Mock()]
            mock_run_result.jobs[0].completed_jobs[0].metrics = {
                "collection_items": {"items_count": 100},
            }

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                await use_case.execute(sample_request)

                # Verify source was called with config
                mock_source.assert_called_once_with(
                    "testuser", config=mock_config.moxfield
                )

    @pytest.mark.asyncio
    async def test_execute_pipeline_failure(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test use case execution with pipeline failure."""
        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            # Mock failed pipeline
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_failed_job = Mock()
            mock_failed_job.exception = RuntimeError("Pipeline failed")
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = [mock_failed_job]
            mock_run_result.jobs[0].completed_jobs = []

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case - should return failure response
                response = await use_case.execute(sample_request)

                # Verify failure response
                assert response.success is False
                assert response.username == "testuser"
                assert response.source == "moxfield"
                assert response.items_processed == 0
                assert (
                    response.error_message is not None
                    and "Pipeline failed" in response.error_message
                )
                assert response.sync_duration_seconds is not None

    @pytest.mark.asyncio
    async def test_execute_source_creation_error(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test use case execution with source creation error."""
        with patch(
            "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
        ) as mock_source:
            # Mock source creation to raise exception
            mock_source.side_effect = RuntimeError("Source creation failed")

            # Execute the use case - should return failure response
            response = await use_case.execute(sample_request)

            # Verify failure response
            assert response.success is False
            assert (
                response.error_message is not None
                and "Source creation failed" in response.error_message
            )

    @pytest.mark.asyncio
    async def test_execute_unsupported_source(
        self, use_case: SyncCollectionUseCase
    ) -> None:
        """Test use case execution with unsupported source."""
        request = SyncCollectionRequest(
            username="testuser",
            source="unsupported_source",
        )

        # Execute the use case - should return failure response
        response = await use_case.execute(request)

        # Verify failure response
        assert response.success is False
        assert (
            response.error_message is not None
            and "Unsupported source" in response.error_message
        )

    @pytest.mark.asyncio
    async def test_execute_timing(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test that execution timing is recorded correctly."""
        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            # Mock successful pipeline with delay
            mock_pipeline = Mock()

            def slow_run(*args: Any, **kwargs: Any) -> Any:
                """Simulate slow pipeline execution."""
                import time

                time.sleep(0.1)  # 100ms delay
                result = Mock()
                result.jobs = [Mock()]
                result.jobs[0].failed_jobs = []
                result.jobs[0].completed_jobs = [Mock()]
                result.jobs[0].completed_jobs[0].metrics = {}
                return result

            mock_pipeline.run.side_effect = slow_run
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                response = await use_case.execute(sample_request)

                # Verify timing was recorded
                assert response.success is True
                assert response.sync_duration_seconds is not None
                assert response.sync_duration_seconds >= 0.1  # At least 100ms

    def test_get_recent_syncs_not_implemented(
        self, use_case: SyncCollectionUseCase
    ) -> None:
        """Test that get_recent_syncs is not yet implemented."""
        with pytest.raises(NotImplementedError):
            use_case.get_recent_syncs("testuser", 10)

    def test_cleanup_old_data_not_implemented(
        self, use_case: SyncCollectionUseCase
    ) -> None:
        """Test that cleanup_old_data is not yet implemented."""
        with pytest.raises(NotImplementedError):
            use_case.cleanup_old_data("testuser", 5)

    @pytest.mark.asyncio
    async def test_execute_metrics_parsing(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test that pipeline metrics are parsed correctly."""
        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            # Mock pipeline with detailed metrics
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []

            # Create mock completed job with metrics
            mock_job = Mock()
            mock_job.metrics = {
                "user_profile": {
                    "items_count": 1,
                    "unique_cards": 0,
                    "total_cards": 0,
                },
                "collection_items": {
                    "items_count": 750,
                    "unique_cards": 500,
                    "total_cards": 1200,
                },
            }
            mock_run_result.jobs[0].completed_jobs = [mock_job]

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                response = await use_case.execute(sample_request)

                # Verify metrics were parsed correctly
                assert response.success is True
                assert response.items_processed == 751  # 1 + 750
                assert response.unique_cards == 500
                assert response.total_cards == 1200

    @pytest.mark.asyncio
    async def test_execute_empty_metrics(
        self, use_case: SyncCollectionUseCase, sample_request: SyncCollectionRequest
    ) -> None:
        """Test use case execution with empty pipeline metrics."""
        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            # Mock pipeline with no metrics
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []
            mock_run_result.jobs[0].completed_jobs = [Mock()]
            mock_run_result.jobs[0].completed_jobs[0].metrics = {}

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                response = await use_case.execute(sample_request)

                # Verify response with empty metrics
                assert response.success is True
                assert response.items_processed == 0
                assert response.unique_cards == 0
                assert response.total_cards == 0

    @pytest.mark.asyncio
    async def test_execute_force_refresh_flag(
        self, use_case: SyncCollectionUseCase
    ) -> None:
        """Test that force_refresh flag is handled correctly."""
        request = SyncCollectionRequest(
            username="testuser",
            source="moxfield",
            force_refresh=True,
        )

        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []
            mock_run_result.jobs[0].completed_jobs = [Mock()]
            mock_run_result.jobs[0].completed_jobs[0].metrics = {}

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                await use_case.execute(request)

                # Verify source creation was called (force_refresh should be handled by dlt)
                mock_source.assert_called_once_with("testuser", config=None)

                # Pipeline should be called with refresh mode
                # Note: In the actual implementation, this might involve different dlt parameters
                mock_pipeline.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_include_profile_false(
        self, use_case: SyncCollectionUseCase
    ) -> None:
        """Test execution when include_profile is False."""
        request = SyncCollectionRequest(
            username="testuser",
            source="moxfield",
            include_profile=False,
        )

        with patch("ponderous.application.use_cases.sync_collection.dlt") as mock_dlt:
            mock_pipeline = Mock()
            mock_run_result = Mock()
            mock_run_result.jobs = [Mock()]
            mock_run_result.jobs[0].failed_jobs = []
            mock_run_result.jobs[0].completed_jobs = [Mock()]
            mock_run_result.jobs[0].completed_jobs[0].metrics = {
                "collection_items": {"items_count": 100},
            }

            mock_pipeline.run.return_value = mock_run_result
            mock_dlt.pipeline.return_value = mock_pipeline

            # Mock the dlt source
            with patch(
                "ponderous.application.use_cases.sync_collection.moxfield_collection_source"
            ) as mock_source:
                mock_source.return_value = Mock()

                # Execute the use case
                response = await use_case.execute(request)

                # Should still succeed (source handles profile inclusion internally)
                assert response.success is True
                assert response.items_processed == 100
