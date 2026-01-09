"""
Unit Tests for Strategy Framework

Tests:
- Strategy base class
- Signal generation
- Strategy lifecycle
- Context management
- Configuration
"""

import pytest
import numpy as np
from datetime import datetime
from api.strategy import (
    Strategy,
    StrategyConfig,
    Signal,
    StrategyContext,
    StrategyState
)


class TestSignal:
    """Tests for Signal class"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_signal_creation(self):
        """Test signal creation"""
        signal = Signal(
            symbol='AAPL',
            direction=1.0,
            strength=0.8,
            confidence=0.7
        )

        assert signal.symbol == 'AAPL'
        assert signal.direction == 1.0
        assert signal.strength == 0.8
        assert signal.confidence == 0.7

    @pytest.mark.unit
    @pytest.mark.fast
    def test_signal_target_position(self):
        """Test signal target position calculation"""
        signal = Signal(
            symbol='AAPL',
            direction=1.0,
            strength=0.8,
            confidence=0.9
        )

        # target = direction * strength * confidence
        expected = 1.0 * 0.8 * 0.9
        assert abs(signal.target_position - expected) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_signal_short_position(self):
        """Test short signal"""
        signal = Signal(
            symbol='AAPL',
            direction=-1.0,
            strength=0.6,
            confidence=0.8
        )

        # Should be negative for short
        assert signal.target_position < 0

    @pytest.mark.unit
    @pytest.mark.fast
    def test_signal_validity(self):
        """Test signal validity checking"""
        # Signal without expiry is always valid
        signal = Signal(
            symbol='AAPL',
            direction=1.0,
            strength=0.8,
            confidence=0.7
        )
        assert signal.is_valid

    @pytest.mark.unit
    @pytest.mark.fast
    def test_signal_with_metadata(self):
        """Test signal with metadata"""
        metadata = {
            'reason': 'momentum breakout',
            'indicators': {'rsi': 65, 'macd': 'bullish'}
        }

        signal = Signal(
            symbol='AAPL',
            direction=1.0,
            strength=0.8,
            confidence=0.7,
            metadata=metadata
        )

        assert signal.metadata['reason'] == 'momentum breakout'
        assert signal.metadata['indicators']['rsi'] == 65


class TestStrategyContext:
    """Tests for StrategyContext"""

    @pytest.fixture
    def sample_context(self):
        """Create sample strategy context"""
        return StrategyContext(
            timestamp=datetime.now(),
            prices={'AAPL': 150.0, 'GOOGL': 2800.0, 'MSFT': 300.0},
            positions={'AAPL': 100, 'GOOGL': 0, 'MSFT': -50},
            cash=50000.0,
            equity=100000.0,
            market_data={}
        )

    @pytest.mark.unit
    @pytest.mark.fast
    def test_context_get_price(self, sample_context):
        """Test getting price from context"""
        assert sample_context.get_price('AAPL') == 150.0
        assert sample_context.get_price('GOOGL') == 2800.0
        assert sample_context.get_price('TSLA') is None  # Not in prices

    @pytest.mark.unit
    @pytest.mark.fast
    def test_context_get_position(self, sample_context):
        """Test getting position from context"""
        assert sample_context.get_position('AAPL') == 100
        assert sample_context.get_position('GOOGL') == 0
        assert sample_context.get_position('MSFT') == -50
        assert sample_context.get_position('TSLA') == 0  # No position

    @pytest.mark.unit
    @pytest.mark.fast
    def test_context_get_exposure(self, sample_context):
        """Test getting exposure from context"""
        # AAPL: 100 shares * $150 = $15,000
        exposure_aapl = sample_context.get_exposure('AAPL')
        assert abs(exposure_aapl - 15000.0) < 1e-6

        # GOOGL: 0 shares
        exposure_googl = sample_context.get_exposure('GOOGL')
        assert exposure_googl == 0.0

        # MSFT: 50 shares * $300 = $15,000 (abs value)
        exposure_msft = sample_context.get_exposure('MSFT')
        assert abs(exposure_msft - 15000.0) < 1e-6


class TestStrategyConfig:
    """Tests for StrategyConfig"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_config_creation(self):
        """Test strategy configuration"""
        config = StrategyConfig(
            name="MomentumStrategy",
            version="1.0",
            symbols=['AAPL', 'GOOGL', 'MSFT'],
            parameters={'lookback': 20, 'threshold': 0.02},
            max_position_pct=0.1,
            max_order_pct=0.05
        )

        assert config.name == "MomentumStrategy"
        assert len(config.symbols) == 3
        assert config.parameters['lookback'] == 20
        assert config.max_position_pct == 0.1

    @pytest.mark.unit
    @pytest.mark.fast
    def test_config_defaults(self):
        """Test strategy configuration defaults"""
        config = StrategyConfig(name="TestStrategy")

        assert config.version == "1.0"
        assert config.symbols == []
        assert config.parameters == {}
        assert config.max_position_pct == 0.1
        assert config.max_order_pct == 0.05
        assert config.cooldown_seconds == 0.0


class MockStrategy(Strategy):
    """Mock strategy for testing"""

    def on_start(self):
        """Called when strategy starts"""
        self.start_count = getattr(self, 'start_count', 0) + 1

    def on_data(self, context: StrategyContext):
        """Generate signals based on data"""
        signals = []

        # Simple logic: buy if we have cash, sell if we have position
        for symbol in self.symbols:
            position = context.get_position(symbol)
            if position == 0 and context.cash > 10000:
                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=0.5,
                    confidence=0.7
                ))
            elif position > 0:
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0,
                    strength=0.5,
                    confidence=0.7
                ))

        return signals

    def on_stop(self):
        """Called when strategy stops"""
        self.stop_count = getattr(self, 'stop_count', 0) + 1


class TestStrategy:
    """Tests for Strategy base class"""

    @pytest.fixture
    def sample_strategy(self):
        """Create sample strategy"""
        config = StrategyConfig(
            name="TestStrategy",
            symbols=['AAPL', 'GOOGL'],
            max_position_pct=0.2
        )
        return MockStrategy(config)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_strategy_initialization(self, sample_strategy):
        """Test strategy initialization"""
        assert sample_strategy.config.name == "TestStrategy"
        assert len(sample_strategy.symbols) == 2
        assert sample_strategy.state == StrategyState.CREATED

    @pytest.mark.unit
    @pytest.mark.fast
    def test_strategy_lifecycle(self, sample_strategy):
        """Test strategy lifecycle"""
        # Start strategy
        sample_strategy.start()
        assert sample_strategy.state == StrategyState.RUNNING
        assert sample_strategy.start_count == 1

        # Stop strategy
        sample_strategy.stop()
        assert sample_strategy.state == StrategyState.STOPPED
        assert sample_strategy.stop_count == 1

    @pytest.mark.unit
    @pytest.mark.fast
    def test_strategy_signal_generation(self, sample_strategy):
        """Test strategy signal generation"""
        context = StrategyContext(
            timestamp=datetime.now(),
            prices={'AAPL': 150.0, 'GOOGL': 2800.0},
            positions={'AAPL': 0, 'GOOGL': 0},
            cash=100000.0,
            equity=100000.0
        )

        signals = sample_strategy.on_data(context)

        # Should generate buy signals (we have cash, no positions)
        assert len(signals) == 2
        assert all(s.direction > 0 for s in signals)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_strategy_with_positions(self, sample_strategy):
        """Test strategy with existing positions"""
        context = StrategyContext(
            timestamp=datetime.now(),
            prices={'AAPL': 150.0, 'GOOGL': 2800.0},
            positions={'AAPL': 100, 'GOOGL': 50},
            cash=50000.0,
            equity=100000.0
        )

        signals = sample_strategy.on_data(context)

        # Should generate sell signals (we have positions)
        assert len(signals) == 2
        assert all(s.direction < 0 for s in signals)


@pytest.mark.unit
@pytest.mark.fast
def test_strategy_enums():
    """Test strategy enums"""
    assert StrategyState.CREATED
    assert StrategyState.RUNNING
    assert StrategyState.STOPPED
    assert StrategyState.ERROR
