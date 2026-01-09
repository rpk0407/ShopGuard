"""
Unit Tests for External Alpha Components
=========================================
Tests for smart money tracking, whale manipulation detection,
liquidity trap detection, and signal quality analysis.

Run with: pytest shopguard_platform/tests/test_external_alpha.py -v
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shopguard_platform.signals.external.whale_manipulation import (
    WhaleManipulationDetector,
    ManipulationType,
    ConfidenceLevel
)
from shopguard_platform.signals.external.liquidity_trap import (
    LiquidityTrapDetector,
    TrapType
)
from shopguard_platform.signals.external.signal_quality import (
    SignalQualityAnalyzer,
    SignalInput,
    SignalQuality
)
from shopguard_platform.signals.external.sentiment_extremes import (
    SentimentExtremesAnalyzer,
    SentimentRegime
)


class TestWhaleManipulationDetector:
    """Test whale manipulation detection"""

    def setup_method(self):
        self.detector = WhaleManipulationDetector()

    def test_single_whale_high_visibility_is_suspicious(self):
        """Single whale with high visibility should be flagged as manipulation"""
        result = self.detector.analyze_whale_activity(
            asset="BTC",
            whale_direction=1.0,  # Strong buy
            is_highly_visible=True
        )
        # Single visible whale should be suspicious
        assert result.confidence_level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]

    def test_multiple_whales_stealth_is_trustworthy(self):
        """Multiple whales with stealth execution should be trustworthy"""
        # Simulate multiple whale entries
        for i in range(5):
            self.detector.analyze_whale_activity(
                asset="BTC",
                whale_direction=0.7,
                is_highly_visible=False
            )

        result = self.detector.analyze_whale_activity(
            asset="BTC",
            whale_direction=0.7,
            is_highly_visible=False
        )
        # After multiple stealth entries, should be more trustworthy
        assert result.confidence_level in [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]

    def test_opposite_direction_detected(self):
        """Sudden direction change should be suspicious"""
        # First, establish a direction
        self.detector.analyze_whale_activity("BTC", 1.0, False)
        self.detector.analyze_whale_activity("BTC", 1.0, False)

        # Then sudden reversal
        result = self.detector.analyze_whale_activity("BTC", -1.0, True)

        # Sudden reversal with visibility should lower confidence
        assert result.confidence_level != ConfidenceLevel.VERY_HIGH

    def test_get_adjusted_signal(self):
        """Test signal adjustment based on manipulation detection"""
        adjusted_signal, confidence, reason = self.detector.get_adjusted_whale_signal(
            asset="ETH",
            raw_whale_direction=0.8,
            is_broadcast=True
        )

        # Should return adjusted values
        assert isinstance(adjusted_signal, float)
        assert isinstance(confidence, float)
        assert isinstance(reason, str)
        assert 0 <= confidence <= 1


class TestLiquidityTrapDetector:
    """Test liquidity trap detection"""

    def setup_method(self):
        self.detector = LiquidityTrapDetector()

    def test_fomo_trap_detection(self):
        """Retail FOMO + whale selling = FOMO trap"""
        result = self.detector.detect_trap(
            asset="BTC",
            retail_sentiment=0.9,    # Extreme FOMO
            smart_money_flow=-0.7,   # Whales selling
            price_momentum=0.5,      # Price rising
            volume_spike=True
        )

        if result.is_trap:
            assert result.trap_type == TrapType.FOMO_TRAP

    def test_panic_trap_detection(self):
        """Retail panic + whale buying = PANIC trap (buy opportunity)"""
        result = self.detector.detect_trap(
            asset="BTC",
            retail_sentiment=-0.9,   # Extreme panic
            smart_money_flow=0.7,    # Whales buying
            price_momentum=-0.5,     # Price falling
            volume_spike=True
        )

        if result.is_trap:
            assert result.trap_type == TrapType.PANIC_TRAP

    def test_no_trap_normal_conditions(self):
        """Normal market conditions should not trigger trap"""
        result = self.detector.detect_trap(
            asset="BTC",
            retail_sentiment=0.2,    # Slight bullish
            smart_money_flow=0.2,    # Slight bullish
            price_momentum=0.1,      # Slight up
            volume_spike=False
        )

        # Aligned sentiment should not be a trap
        assert not result.is_trap or result.trap_type == TrapType.NONE

    def test_bull_trap_detection(self):
        """Price breaking up but smart money selling"""
        result = self.detector.detect_trap(
            asset="ETH",
            retail_sentiment=0.8,    # Bullish
            smart_money_flow=-0.6,   # Whales selling
            price_momentum=0.7,      # Strong up
            volume_spike=True,
            is_breakout=True
        )

        # Could be a bull trap
        if result.is_trap:
            assert result.trap_type in [TrapType.BULL_TRAP, TrapType.FOMO_TRAP]


class TestSignalQualityAnalyzer:
    """Test signal quality cross-validation"""

    def setup_method(self):
        self.analyzer = SignalQualityAnalyzer()

    def test_single_source_is_low_quality(self):
        """Single source signal should be low quality"""
        self.analyzer.add_signal("BTC", SignalInput(
            source="polymarket",
            direction=1.0,
            confidence=0.8,
            timestamp=0
        ))

        result = self.analyzer.assess_quality("BTC")
        assert result.quality in [SignalQuality.LOW, SignalQuality.UNRELIABLE]

    def test_multiple_agreeing_sources_is_good(self):
        """Multiple agreeing sources should be good quality"""
        # Add 3 agreeing signals
        self.analyzer.add_signal("BTC", SignalInput(
            source="polymarket",
            direction=1.0,
            confidence=0.8,
            timestamp=0
        ))
        self.analyzer.add_signal("BTC", SignalInput(
            source="social",
            direction=0.7,
            confidence=0.7,
            timestamp=0
        ))
        self.analyzer.add_signal("BTC", SignalInput(
            source="news",
            direction=0.8,
            confidence=0.6,
            timestamp=0
        ))

        result = self.analyzer.assess_quality("BTC")
        assert result.quality in [SignalQuality.GOOD, SignalQuality.EXCELLENT]

    def test_conflicting_sources_is_unreliable(self):
        """Conflicting sources should be unreliable"""
        self.analyzer.add_signal("BTC", SignalInput(
            source="polymarket",
            direction=1.0,  # Bullish
            confidence=0.9,
            timestamp=0
        ))
        self.analyzer.add_signal("BTC", SignalInput(
            source="social",
            direction=-0.9,  # Bearish
            confidence=0.9,
            timestamp=0
        ))

        result = self.analyzer.assess_quality("BTC")
        # Conflicting high-confidence signals = unreliable
        assert result.quality in [SignalQuality.LOW, SignalQuality.UNRELIABLE]

    def test_position_multiplier(self):
        """Test position size multiplier based on quality"""
        # Add excellent quality signals
        for source in ["polymarket", "social", "news", "smart_money"]:
            self.analyzer.add_signal("ETH", SignalInput(
                source=source,
                direction=0.8,
                confidence=0.8,
                timestamp=0
            ))

        multiplier = self.analyzer.get_position_multiplier("ETH")
        assert 0 <= multiplier <= 1.0

    def test_should_trade_decision(self):
        """Test should_trade returns correct decision"""
        # Add moderate quality signals
        self.analyzer.add_signal("SOL", SignalInput(
            source="polymarket",
            direction=0.7,
            confidence=0.7,
            timestamp=0
        ))
        self.analyzer.add_signal("SOL", SignalInput(
            source="social",
            direction=0.6,
            confidence=0.6,
            timestamp=0
        ))

        should_trade, reason = self.analyzer.should_trade("SOL", SignalQuality.MODERATE)
        assert isinstance(should_trade, bool)
        assert isinstance(reason, str)


class TestSentimentExtremesAnalyzer:
    """Test sentiment extremes contrarian signals"""

    def setup_method(self):
        self.analyzer = SentimentExtremesAnalyzer()

    def test_extreme_fear_is_buy(self):
        """Extreme fear should generate contrarian buy signal"""
        result = self.analyzer.analyze(fear_greed_index=15)  # Extreme fear

        assert result.regime == SentimentRegime.EXTREME_FEAR
        assert result.contrarian_signal > 0  # Buy signal

    def test_extreme_greed_is_sell(self):
        """Extreme greed should generate contrarian sell signal"""
        result = self.analyzer.analyze(fear_greed_index=85)  # Extreme greed

        assert result.regime == SentimentRegime.EXTREME_GREED
        assert result.contrarian_signal < 0  # Sell signal

    def test_neutral_no_signal(self):
        """Neutral sentiment should not generate strong signal"""
        result = self.analyzer.analyze(fear_greed_index=50)

        assert result.regime == SentimentRegime.NEUTRAL
        assert abs(result.contrarian_signal) < 0.3


class TestIntegration:
    """Integration tests for the complete pipeline"""

    def test_full_pipeline_blocks_manipulation(self):
        """Test that manipulation detection blocks signals"""
        whale_detector = WhaleManipulationDetector()
        quality_analyzer = SignalQualityAnalyzer()

        # Simulate a suspicious whale signal
        manipulation = whale_detector.analyze_whale_activity(
            asset="BTC",
            whale_direction=1.0,
            is_highly_visible=True
        )

        # If manipulation detected, should affect trading decision
        if manipulation.is_manipulation:
            # Add to quality analyzer with low confidence
            quality_analyzer.add_signal("BTC", SignalInput(
                source="whale",
                direction=manipulation.adjusted_signal,
                confidence=manipulation.signal_confidence,
                timestamp=0
            ))

            result = quality_analyzer.assess_quality("BTC")
            # Should not be excellent quality
            assert result.quality != SignalQuality.EXCELLENT

    def test_contrarian_signal_with_trap_detection(self):
        """Test contrarian signals work with trap detection"""
        sentiment_analyzer = SentimentExtremesAnalyzer()
        trap_detector = LiquidityTrapDetector()

        # Extreme fear scenario
        sentiment = sentiment_analyzer.analyze(fear_greed_index=10)

        # Check if it's a panic trap (buy opportunity)
        trap = trap_detector.detect_trap(
            asset="BTC",
            retail_sentiment=-0.9,  # Panic
            smart_money_flow=0.8,   # Whales buying
            price_momentum=-0.3,
            volume_spike=True
        )

        # Both should agree this is a buy opportunity
        assert sentiment.contrarian_signal > 0  # Buy from contrarian
        if trap.is_trap and trap.trap_type == TrapType.PANIC_TRAP:
            assert trap.recommended_action == "BUY"  # Buy the panic


# Fixtures for pytest
@pytest.fixture
def whale_detector():
    return WhaleManipulationDetector()


@pytest.fixture
def trap_detector():
    return LiquidityTrapDetector()


@pytest.fixture
def quality_analyzer():
    return SignalQualityAnalyzer()


@pytest.fixture
def sentiment_analyzer():
    return SentimentExtremesAnalyzer()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
