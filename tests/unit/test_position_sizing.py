"""
Unit Tests for Position Sizing

Tests:
- Kelly Criterion
- Fractional Kelly
- Fixed fraction
- Volatility-adjusted sizing
- Risk-based sizing
"""

import pytest
import numpy as np
from core.math.position_sizing import (
    FractionalKelly,
    FixedFraction,
    VolatilityAdjusted,
    RiskParity
)


class TestFractionalKelly:
    """Tests for Fractional Kelly position sizing"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_initialization(self):
        """Test Kelly initialization"""
        kelly = FractionalKelly(fraction=0.25)
        assert kelly.fraction == 0.25

    @pytest.mark.unit
    @pytest.mark.fast
    def test_positive_edge(self):
        """Test Kelly with positive edge"""
        kelly = FractionalKelly(fraction=0.5)

        # Win rate 60%, risk-reward 1:1
        win_rate = 0.6
        win_loss_ratio = 1.0

        fraction = kelly.calculate(win_rate=win_rate, win_loss_ratio=win_loss_ratio)

        # Kelly = (p * (b+1) - 1) / b = (0.6 * 2 - 1) / 1 = 0.2
        # Fractional Kelly = 0.2 * 0.5 = 0.1
        expected = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio * 0.5
        assert abs(fraction - expected) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_no_edge(self):
        """Test Kelly with no edge (should return 0)"""
        kelly = FractionalKelly(fraction=1.0)

        # Win rate 50%, risk-reward 1:1 (fair coin flip)
        fraction = kelly.calculate(win_rate=0.5, win_loss_ratio=1.0)

        assert abs(fraction) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_negative_edge(self):
        """Test Kelly with negative edge (should return 0)"""
        kelly = FractionalKelly(fraction=1.0)

        # Win rate 40%, risk-reward 1:1 (negative expectancy)
        fraction = kelly.calculate(win_rate=0.4, win_loss_ratio=1.0)

        # Should not bet on negative expectancy
        assert fraction <= 0

    @pytest.mark.unit
    @pytest.mark.fast
    def test_fractional_kelly_reduces_size(self):
        """Test that fractional Kelly reduces position size"""
        full_kelly = FractionalKelly(fraction=1.0)
        half_kelly = FractionalKelly(fraction=0.5)

        full_size = full_kelly.calculate(win_rate=0.6, win_loss_ratio=1.0)
        half_size = half_kelly.calculate(win_rate=0.6, win_loss_ratio=1.0)

        assert abs(half_size - full_size / 2) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_high_win_loss_ratio(self):
        """Test Kelly with high win/loss ratio"""
        kelly = FractionalKelly(fraction=0.25)

        # Win rate 40%, but 3:1 risk-reward
        fraction = kelly.calculate(win_rate=0.4, win_loss_ratio=3.0)

        # Should still size position (positive expectancy)
        assert fraction > 0

    @pytest.mark.unit
    @pytest.mark.fast
    def test_fraction_bounds(self):
        """Test that Kelly fraction respects max bound"""
        kelly = FractionalKelly(fraction=0.25, max_fraction=0.05)

        # Even with high edge, should not exceed max
        fraction = kelly.calculate(win_rate=0.8, win_loss_ratio=2.0)

        assert fraction <= 0.05 + 1e-6


class TestFixedFraction:
    """Tests for fixed fraction position sizing"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_fixed_fraction(self):
        """Test fixed fraction sizing"""
        sizer = FixedFraction(fraction=0.1)

        capital = 100000
        size = sizer.calculate(capital=capital)

        assert abs(size - 10000) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_different_fractions(self):
        """Test different fixed fractions"""
        capital = 50000

        for fraction in [0.01, 0.05, 0.1, 0.2]:
            sizer = FixedFraction(fraction=fraction)
            size = sizer.calculate(capital=capital)
            assert abs(size - capital * fraction) < 1e-6


class TestVolatilityAdjusted:
    """Tests for volatility-adjusted position sizing"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_volatility_adjusted(self):
        """Test volatility-adjusted sizing"""
        sizer = VolatilityAdjusted(target_volatility=0.15)

        capital = 100000
        current_volatility = 0.20

        size = sizer.calculate(capital=capital, volatility=current_volatility)

        # Higher volatility = smaller position
        # size = capital * (target_vol / current_vol)
        expected = capital * (0.15 / 0.20)
        assert abs(size - expected) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_low_volatility_increases_size(self):
        """Test that low volatility increases position size"""
        sizer = VolatilityAdjusted(target_volatility=0.15)

        capital = 100000

        high_vol_size = sizer.calculate(capital=capital, volatility=0.30)
        low_vol_size = sizer.calculate(capital=capital, volatility=0.10)

        assert low_vol_size > high_vol_size

    @pytest.mark.unit
    @pytest.mark.fast
    def test_max_leverage_constraint(self):
        """Test maximum leverage constraint"""
        sizer = VolatilityAdjusted(target_volatility=0.15, max_leverage=2.0)

        capital = 100000
        very_low_volatility = 0.01  # Would imply 15x leverage

        size = sizer.calculate(capital=capital, volatility=very_low_volatility)

        # Should be capped at 2x capital
        assert size <= capital * 2.0 + 1e-6


class TestRiskParity:
    """Tests for risk parity position sizing"""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_risk_parity_equal_vol(self):
        """Test risk parity with equal volatilities"""
        sizer = RiskParity()

        volatilities = np.array([0.20, 0.20, 0.20])
        sizes = sizer.calculate(volatilities=volatilities)

        # Equal volatilities should give equal sizes
        assert abs(sizes[0] - sizes[1]) < 1e-6
        assert abs(sizes[1] - sizes[2]) < 1e-6

        # Should sum to 1 (100% allocated)
        assert abs(np.sum(sizes) - 1.0) < 1e-6

    @pytest.mark.unit
    @pytest.mark.fast
    def test_risk_parity_different_vol(self):
        """Test risk parity with different volatilities"""
        sizer = RiskParity()

        volatilities = np.array([0.10, 0.20, 0.40])
        sizes = sizer.calculate(volatilities=volatilities)

        # Lower volatility assets should have larger sizes
        assert sizes[0] > sizes[1]
        assert sizes[1] > sizes[2]

        # Sizes should be inversely proportional to volatilities
        # size[i] * vol[i] should be equal for all i
        risk_contributions = sizes * volatilities
        assert abs(risk_contributions[0] - risk_contributions[1]) < 1e-2
        assert abs(risk_contributions[1] - risk_contributions[2]) < 1e-2

    @pytest.mark.unit
    @pytest.mark.fast
    def test_risk_parity_sums_to_one(self):
        """Test that risk parity weights sum to 1"""
        sizer = RiskParity()

        for _ in range(10):
            n = np.random.randint(2, 10)
            volatilities = np.random.uniform(0.05, 0.50, n)
            sizes = sizer.calculate(volatilities=volatilities)

            assert abs(np.sum(sizes) - 1.0) < 1e-6


@pytest.mark.unit
@pytest.mark.fast
def test_all_position_sizers_exist():
    """Test that all position sizers can be imported"""
    from core.math.position_sizing import (
        FractionalKelly,
        FixedFraction,
        VolatilityAdjusted,
        RiskParity
    )
    assert FractionalKelly is not None
    assert FixedFraction is not None
    assert VolatilityAdjusted is not None
    assert RiskParity is not None
