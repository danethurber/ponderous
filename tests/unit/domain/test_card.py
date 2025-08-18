"""Unit tests for Card domain models."""

import pytest

from ponderous.domain.models.card import Card, CardData, MissingCard


class TestCard:
    """Test suite for Card entity."""

    def test_card_creation_with_minimal_data(self) -> None:
        """Should create card with only required fields."""
        card = Card(name="Sol Ring", card_id="sol_ring_001")

        assert card.name == "Sol Ring"
        assert card.card_id == "sol_ring_001"
        assert card.mana_cost is None
        assert card.cmc is None

    def test_card_creation_with_full_data(self) -> None:
        """Should create card with all fields populated."""
        card = Card(
            name="Meren of Clan Nel Toth",
            card_id="meren_001",
            mana_cost="{2}{B}{G}{G}",
            cmc=5,
            color_identity=["B", "G"],
            type_line="Legendary Creature — Human Shaman",
            oracle_text="Whenever another creature you control dies...",
            power="3",
            toughness="4",
            rarity="mythic",
            price_usd=15.50,
        )

        assert card.name == "Meren of Clan Nel Toth"
        assert card.cmc == 5
        assert card.color_identity == ["B", "G"]
        assert card.price_usd == 15.50

    def test_card_name_cannot_be_empty(self) -> None:
        """Should raise ValueError for empty card name."""
        with pytest.raises(ValueError, match="Card name cannot be empty"):
            Card(name="", card_id="test_001")

    def test_card_id_cannot_be_empty(self) -> None:
        """Should raise ValueError for empty card ID."""
        with pytest.raises(ValueError, match="Card ID cannot be empty"):
            Card(name="Test Card", card_id="")

    def test_card_name_with_whitespace_only_raises_error(self) -> None:
        """Should raise ValueError for whitespace-only card name."""
        with pytest.raises(ValueError, match="Card name cannot be empty"):
            Card(name="   ", card_id="test_001")

    def test_is_commander_legal_for_legendary_creature(self) -> None:
        """Should return True for legendary creatures."""
        card = Card(
            name="Meren of Clan Nel Toth",
            card_id="meren_001",
            type_line="Legendary Creature — Human Shaman",
        )

        assert card.is_commander_legal is True

    def test_is_commander_legal_for_non_legendary_creature(self) -> None:
        """Should return False for non-legendary creatures."""
        card = Card(
            name="Bears",
            card_id="bears_001",
            type_line="Creature — Bear",
        )

        assert card.is_commander_legal is False

    def test_is_commander_legal_for_legendary_non_creature(self) -> None:
        """Should return False for legendary non-creatures."""
        card = Card(
            name="Sol Ring",
            card_id="sol_ring_001",
            type_line="Legendary Artifact",
        )

        assert card.is_commander_legal is False

    def test_is_commander_legal_with_no_type_line(self) -> None:
        """Should return False when type_line is None."""
        card = Card(name="Test Card", card_id="test_001")

        assert card.is_commander_legal is False

    def test_color_identity_str_for_multicolor_card(self) -> None:
        """Should return sorted color identity string."""
        card = Card(
            name="Test Card",
            card_id="test_001",
            color_identity=["G", "B", "U"],
        )

        assert card.color_identity_str == "BGU"

    def test_color_identity_str_for_colorless_card(self) -> None:
        """Should return 'C' for colorless cards."""
        card = Card(
            name="Sol Ring",
            card_id="sol_ring_001",
            color_identity=[],
        )

        assert card.color_identity_str == "C"

    def test_color_identity_str_for_none_color_identity(self) -> None:
        """Should return 'C' when color_identity is None."""
        card = Card(name="Test Card", card_id="test_001")

        assert card.color_identity_str == "C"


class TestCardData:
    """Test suite for CardData model."""

    def test_card_data_creation_with_required_fields(self) -> None:
        """Should create CardData with required fields."""
        card_data = CardData(
            name="Sol Ring",
            card_id="sol_ring_001",
            inclusion_rate=0.95,
        )

        assert card_data.name == "Sol Ring"
        assert card_data.inclusion_rate == 0.95
        assert card_data.synergy_score == 0.0  # default
        assert card_data.category == "staple"  # default

    def test_card_data_inclusion_rate_validation(self) -> None:
        """Should validate inclusion_rate is between 0 and 1."""
        # Valid rates
        CardData(name="Test", card_id="test_001", inclusion_rate=0.0)
        CardData(name="Test", card_id="test_001", inclusion_rate=0.5)
        CardData(name="Test", card_id="test_001", inclusion_rate=1.0)

        # Invalid rates
        with pytest.raises(ValueError):
            CardData(name="Test", card_id="test_001", inclusion_rate=-0.1)

        with pytest.raises(ValueError):
            CardData(name="Test", card_id="test_001", inclusion_rate=1.1)

    def test_card_data_price_validation(self) -> None:
        """Should validate price_usd is non-negative."""
        # Valid prices
        CardData(name="Test", card_id="test_001", inclusion_rate=0.5, price_usd=0.0)
        CardData(name="Test", card_id="test_001", inclusion_rate=0.5, price_usd=10.50)

        # Invalid price
        with pytest.raises(ValueError):
            CardData(
                name="Test", card_id="test_001", inclusion_rate=0.5, price_usd=-1.0
            )

    def test_impact_score_calculation_signature_card(self) -> None:
        """Should calculate high impact score for signature cards."""
        card_data = CardData(
            name="Commander",
            card_id="cmd_001",
            inclusion_rate=1.0,
            synergy_score=3.0,
            category="signature",
        )

        # Impact = inclusion_rate * category_weight * (1 + synergy_score)
        # Impact = 1.0 * 3.0 * (1 + 3.0) = 12.0
        assert card_data.impact_score == 12.0

    def test_impact_score_calculation_staple_card(self) -> None:
        """Should calculate appropriate impact score for staple cards."""
        card_data = CardData(
            name="Sol Ring",
            card_id="sol_ring_001",
            inclusion_rate=0.95,
            synergy_score=0.5,
            category="staple",
        )

        # Impact = 0.95 * 1.5 * (1 + 0.5) = 2.1375
        expected_impact = 0.95 * 1.5 * 1.5
        assert abs(card_data.impact_score - expected_impact) < 0.001

    def test_is_high_impact_for_signature_card(self) -> None:
        """Should mark signature cards as high impact."""
        card_data = CardData(
            name="Commander",
            card_id="cmd_001",
            inclusion_rate=0.5,
            category="signature",
        )

        assert card_data.is_high_impact is True

    def test_is_high_impact_for_high_synergy_card(self) -> None:
        """Should mark high synergy cards as high impact."""
        card_data = CardData(
            name="Synergy Card",
            card_id="syn_001",
            inclusion_rate=0.5,
            category="high_synergy",
        )

        assert card_data.is_high_impact is True

    def test_is_high_impact_for_high_score_staple(self) -> None:
        """Should mark staples with high impact score as high impact."""
        card_data = CardData(
            name="High Impact Staple",
            card_id="staple_001",
            inclusion_rate=0.9,
            synergy_score=2.0,
            category="staple",
        )

        # Impact = 0.9 * 1.5 * 3.0 = 4.05 (> 2.0 threshold)
        assert card_data.is_high_impact is True

    def test_is_high_impact_for_low_impact_basic(self) -> None:
        """Should not mark low impact basic cards as high impact."""
        card_data = CardData(
            name="Basic Card",
            card_id="basic_001",
            inclusion_rate=0.3,
            synergy_score=0.0,
            category="basic",
        )

        # Impact = 0.3 * 1.0 * 1.0 = 0.3 (< 2.0 threshold)
        assert card_data.is_high_impact is False


class TestMissingCard:
    """Test suite for MissingCard model."""

    def test_missing_card_creation_from_card_data(self) -> None:
        """Should create MissingCard from CardData."""
        card_data = CardData(
            name="Eternal Witness",
            card_id="e_witness_001",
            inclusion_rate=0.78,
            synergy_score=2.5,
            category="high_synergy",
            price_usd=3.50,
        )

        missing_card = MissingCard.from_card_data(
            card_data=card_data,
            alternatives=["Regrowth", "Nature's Spiral"],
        )

        assert missing_card.card_data == card_data
        assert missing_card.estimated_cost == 3.50
        assert missing_card.alternatives == ["Regrowth", "Nature's Spiral"]

    def test_missing_card_priority_calculation_critical(self) -> None:
        """Should assign critical priority to high impact cards."""
        card_data = CardData(
            name="High Impact Card",
            card_id="high_001",
            inclusion_rate=1.0,
            synergy_score=3.0,
            category="signature",
        )

        missing_card = MissingCard.from_card_data(card_data)

        # Impact = 1.0 * 3.0 * 4.0 = 12.0 (>= 3.0 = critical)
        assert missing_card.priority_level == "critical"

    def test_missing_card_priority_calculation_critical_high_synergy(self) -> None:
        """Should assign critical priority to high synergy cards with good stats."""
        card_data = CardData(
            name="High Synergy Card",
            card_id="high_syn_001",
            inclusion_rate=0.8,
            synergy_score=1.5,
            category="high_synergy",
        )

        missing_card = MissingCard.from_card_data(card_data)

        # Impact = 0.8 * 2.0 * 2.5 = 4.0 (>= 3.0 = critical)
        assert missing_card.priority_level == "critical"

    def test_missing_card_priority_calculation_high(self) -> None:
        """Should assign high priority to medium-high impact cards."""
        card_data = CardData(
            name="Good Staple Card",
            card_id="good_staple_001",
            inclusion_rate=0.8,
            synergy_score=1.0,
            category="staple",
        )

        missing_card = MissingCard.from_card_data(card_data)

        # Impact = 0.8 * 1.5 * 2.0 = 2.4 (>= 2.0 = high)
        assert missing_card.priority_level == "high"

    def test_missing_card_priority_calculation_medium(self) -> None:
        """Should assign medium priority to moderate impact cards."""
        card_data = CardData(
            name="Decent Staple",
            card_id="staple_001",
            inclusion_rate=0.7,
            synergy_score=0.5,
            category="staple",
        )

        missing_card = MissingCard.from_card_data(card_data)

        # Impact = 0.7 * 1.5 * 1.5 = 1.575 (>= 1.0 = medium)
        assert missing_card.priority_level == "medium"

    def test_missing_card_priority_calculation_low(self) -> None:
        """Should assign low priority to low impact cards."""
        card_data = CardData(
            name="Basic Card",
            card_id="basic_001",
            inclusion_rate=0.3,
            synergy_score=0.0,
            category="basic",
        )

        missing_card = MissingCard.from_card_data(card_data)

        # Impact = 0.3 * 1.0 * 1.0 = 0.3 (< 1.0 = low)
        assert missing_card.priority_level == "low"

    def test_missing_card_invalid_priority_raises_error(self) -> None:
        """Should raise ValueError for invalid priority level."""
        card_data = CardData(
            name="Test Card",
            card_id="test_001",
            inclusion_rate=0.5,
        )

        with pytest.raises(ValueError, match="Invalid priority level"):
            MissingCard(
                card_data=card_data,
                estimated_cost=1.0,
                priority_level="invalid",
                alternatives=[],
            )

    def test_missing_card_negative_cost_raises_error(self) -> None:
        """Should raise ValueError for negative estimated cost."""
        card_data = CardData(
            name="Test Card",
            card_id="test_001",
            inclusion_rate=0.5,
        )

        with pytest.raises(ValueError, match="Estimated cost cannot be negative"):
            MissingCard(
                card_data=card_data,
                estimated_cost=-1.0,
                priority_level="low",
                alternatives=[],
            )

    def test_missing_card_impact_score_property(self) -> None:
        """Should return impact score from card data."""
        card_data = CardData(
            name="Test Card",
            card_id="test_001",
            inclusion_rate=0.8,
            synergy_score=1.0,
            category="staple",
        )

        missing_card = MissingCard.from_card_data(card_data)

        assert missing_card.impact_score == card_data.impact_score
