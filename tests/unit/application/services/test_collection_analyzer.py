"""Tests for CollectionAnalyzer service."""

from unittest.mock import Mock

import pytest

from ponderous.application.services import CollectionAnalyzer
from ponderous.domain.models import CollectionAnalysis, CollectionItem
from ponderous.infrastructure.database import (
    CollectionRepository,
    CommanderRepositoryImpl,
)


class TestCollectionAnalyzer:
    """Test suite for CollectionAnalyzer service."""

    @pytest.fixture
    def mock_collection_repo(self):
        """Create mock collection repository."""
        return Mock(spec=CollectionRepository)

    @pytest.fixture
    def mock_commander_repo(self):
        """Create mock commander repository."""
        return Mock(spec=CommanderRepositoryImpl)

    @pytest.fixture
    def analyzer(self, mock_collection_repo, mock_commander_repo):
        """Create CollectionAnalyzer with mocked dependencies."""
        return CollectionAnalyzer(mock_collection_repo, mock_commander_repo)

    @pytest.fixture
    def sample_collection_items(self):
        """Create sample collection items for testing."""
        return [
            CollectionItem(
                user_id="testuser",
                source_id="moxfield",
                card_id="sol-ring",
                card_name="Sol Ring",
                quantity=1,
            ),
            CollectionItem(
                user_id="testuser",
                source_id="moxfield",
                card_id="lightning-bolt",
                card_name="Lightning Bolt",
                quantity=4,
            ),
            CollectionItem(
                user_id="testuser",
                source_id="moxfield",
                card_id="counterspell",
                card_name="Counterspell",
                quantity=2,
            ),
        ]

    def test_analyze_collection_success(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should perform comprehensive collection analysis."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        analysis = analyzer.analyze_collection("testuser")

        # Assert
        assert isinstance(analysis, CollectionAnalysis)
        assert analysis.total_cards == 7  # 1 + 4 + 2
        assert analysis.unique_cards == 3
        assert analysis.total_value >= 0.0
        assert isinstance(analysis.color_distribution, dict)
        assert isinstance(analysis.strongest_colors, list)
        assert isinstance(analysis.archetype_affinity, dict)
        assert isinstance(analysis.theme_support, dict)
        assert isinstance(analysis.mana_curve_profile, dict)
        assert isinstance(analysis.missing_staples, list)
        assert 1.0 <= analysis.collection_power_level <= 10.0

        # Verify repository was called correctly
        mock_collection_repo.get_collection_by_user.assert_called_once_with("testuser")

    def test_analyze_collection_empty_collection(self, analyzer, mock_collection_repo):
        """Should raise ValueError for empty collection."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = []

        # Act & Assert
        with pytest.raises(ValueError, match="No collection found for user testuser"):
            analyzer.analyze_collection("testuser")

    def test_calculate_collection_value_success(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should calculate collection value metrics."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        value_metrics = analyzer.calculate_collection_value("testuser")

        # Assert
        assert isinstance(value_metrics, dict)
        assert "total_value" in value_metrics
        assert "average_value" in value_metrics
        assert "median_value" in value_metrics
        assert "total_cards" in value_metrics
        assert "unique_cards" in value_metrics

        assert value_metrics["total_cards"] == 7
        assert value_metrics["unique_cards"] == 3
        assert value_metrics["total_value"] >= 0.0
        assert value_metrics["average_value"] >= 0.0

    def test_calculate_collection_value_empty_collection(
        self, analyzer, mock_collection_repo
    ):
        """Should handle empty collection gracefully."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = []

        # Act
        value_metrics = analyzer.calculate_collection_value("testuser")

        # Assert
        assert value_metrics["total_value"] == 0.0
        assert value_metrics["average_value"] == 0.0
        assert value_metrics["median_value"] == 0.0

    def test_identify_most_valuable_cards(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should identify most valuable cards in collection."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        valuable_cards = analyzer.identify_most_valuable_cards("testuser", limit=5)

        # Assert
        assert isinstance(valuable_cards, list)
        assert len(valuable_cards) <= 5

        for card in valuable_cards:
            assert "card_name" in card
            assert "quantity" in card
            assert "estimated_value" in card
            assert "total_value" in card
            assert isinstance(card["quantity"], int)
            assert card["quantity"] > 0

    def test_find_synergy_overlaps(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should find synergy overlaps across potential decks."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        synergy_groups = analyzer.find_synergy_overlaps("testuser")

        # Assert
        assert isinstance(synergy_groups, list)

        for group in synergy_groups:
            assert "theme" in group
            assert "cards" in group
            assert "commander_overlap" in group
            assert "synergy_score" in group
            assert isinstance(group["cards"], list)
            assert isinstance(group["commander_overlap"], int)
            assert isinstance(group["synergy_score"], int | float)
            assert 0.0 <= group["synergy_score"] <= 1.0

    def test_recommend_card_purchases(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should recommend card purchases within budget."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )
        budget = 50.0

        # Act
        recommendations = analyzer.recommend_card_purchases("testuser", budget)

        # Assert
        assert isinstance(recommendations, list)

        total_cost = 0.0
        for rec in recommendations:
            assert "card_name" in rec
            assert "estimated_price" in rec
            assert "impact_score" in rec
            assert "reason" in rec
            assert isinstance(rec["estimated_price"], int | float)
            assert isinstance(rec["impact_score"], int | float)
            assert rec["estimated_price"] > 0
            assert 0.0 <= rec["impact_score"] <= 10.0
            total_cost += rec["estimated_price"]

        # Should not exceed budget
        assert total_cost <= budget

    def test_identify_collection_gaps(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should identify strategic gaps in collection."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        gaps = analyzer.identify_collection_gaps("testuser")

        # Assert
        assert isinstance(gaps, list)

        for gap in gaps:
            assert "gap_type" in gap
            assert "description" in gap
            assert "suggestion" in gap
            assert "priority" in gap
            assert gap["priority"] in ["low", "medium", "high"]

    def test_color_distribution_analysis(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should analyze color distribution correctly."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        analysis = analyzer.analyze_collection("testuser")

        # Assert
        color_dist = analysis.color_distribution
        assert isinstance(color_dist, dict)

        # Should have all color categories
        expected_colors = ["White", "Blue", "Black", "Red", "Green", "Colorless"]
        for color in expected_colors:
            assert color in color_dist
            assert isinstance(color_dist[color], int)
            assert color_dist[color] >= 0

        # Total cards should match
        total_colored_cards = sum(color_dist.values())
        assert total_colored_cards == analysis.total_cards

    def test_strongest_colors_identification(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should identify strongest colors based on distribution."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        analysis = analyzer.analyze_collection("testuser")

        # Assert
        strongest_colors = analysis.strongest_colors
        assert isinstance(strongest_colors, list)
        assert len(strongest_colors) <= 3

        # Should be ordered by strength (most to least)
        if len(strongest_colors) > 1:
            color_dist = analysis.color_distribution
            for i in range(len(strongest_colors) - 1):
                curr_color = strongest_colors[i]
                next_color = strongest_colors[i + 1]
                # Current should have >= cards than next (allowing ties)
                assert color_dist.get(curr_color, 0) >= color_dist.get(next_color, 0)

    def test_archetype_affinity_calculation(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should calculate archetype affinities based on card analysis."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        analysis = analyzer.analyze_collection("testuser")

        # Assert
        archetype_affinity = analysis.archetype_affinity
        assert isinstance(archetype_affinity, dict)

        # Should have common archetypes
        expected_archetypes = ["Aggro", "Control", "Combo", "Midrange"]
        for archetype in expected_archetypes:
            if archetype in archetype_affinity:
                score = archetype_affinity[archetype]
                assert isinstance(score, int | float)
                assert 0.0 <= score <= 1.0

    def test_missing_staples_identification(
        self, analyzer, mock_collection_repo, sample_collection_items
    ):
        """Should identify missing EDH staples."""
        # Arrange
        mock_collection_repo.get_collection_by_user.return_value = (
            sample_collection_items
        )

        # Act
        analysis = analyzer.analyze_collection("testuser")

        # Assert
        missing_staples = analysis.missing_staples
        assert isinstance(missing_staples, list)

        # Should not include cards we own
        owned_cards = {"Sol Ring", "Lightning Bolt", "Counterspell"}
        for staple in missing_staples:
            assert staple not in owned_cards
            assert isinstance(staple, str)
            assert len(staple) > 0
