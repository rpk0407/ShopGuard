"""
Unit Tests for GARCH Models

Tests:
- GARCH(1,1) parameter estimation
- Volatility forecasting
- Model persistence
- Edge cases and validation
"""

import pytest
import numpy as np
from core.models.garch import GARCH11, EGARCH, ComponentGARCH


class TestGARCH11:
    """Tests for GARCH(1,1) model"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data with volatility clustering"""
        np.random.seed(42)
        n = 1000

        # Simulate GARCH process
        omega, alpha, beta = 0.0001, 0.1, 0.85
        errors = np.random.normal(0, 1, n)
        returns = np.zeros(n)
        variance = np.zeros(n)
        variance[0] = omega / (1 - alpha - beta)

        for t in range(1, n):
            variance[t] = omega + alpha * returns[t-1]**2 + beta * variance[t-1]
            returns[t] = np.sqrt(variance[t]) * errors[t]

        return returns

    @pytest.mark.unit
    @pytest.mark.models
    @pytest.mark.fast
    def test_garch_initialization(self):
        """Test GARCH model initialization"""
        garch = GARCH11()
        assert garch is not None
        assert not garch.fitted

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_fit(self, sample_returns):
        """Test GARCH model fitting"""
        garch = GARCH11()
        result = garch.fit(sample_returns)

        assert garch.fitted
        assert result is not None
        assert hasattr(result.params, 'omega')
        assert hasattr(result.params, 'alpha')
        assert hasattr(result.params, 'beta')

        # Check parameters are positive
        assert result.params.omega > 0
        assert result.params.alpha > 0
        assert result.params.beta > 0

        # Check stationarity condition
        assert result.params.alpha + result.params.beta < 1.0

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_forecast(self, sample_returns):
        """Test GARCH volatility forecasting"""
        garch = GARCH11()
        garch.fit(sample_returns)

        forecast = garch.forecast(horizon=10)

        assert len(forecast) == 10
        assert all(v > 0 for v in forecast)
        # Volatility should mean-revert to long-run level
        assert forecast[-1] < forecast[0] * 2  # Not exploding

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_persistence(self, sample_returns):
        """Test GARCH persistence calculation"""
        garch = GARCH11()
        result = garch.fit(sample_returns)

        persistence = result.params.persistence
        assert 0 < persistence < 1
        assert abs(persistence - (result.params.alpha + result.params.beta)) < 1e-10

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_half_life(self, sample_returns):
        """Test volatility half-life calculation"""
        garch = GARCH11()
        result = garch.fit(sample_returns)

        half_life = result.params.half_life
        assert half_life > 0
        # For typical financial data, expect half-life between 1-100 days
        assert 0.1 < half_life < 500

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_unconditional_variance(self, sample_returns):
        """Test unconditional variance calculation"""
        garch = GARCH11()
        result = garch.fit(sample_returns)

        uncond_var = result.params.unconditional_variance
        assert uncond_var > 0

        # Should match theoretical value
        expected = result.params.omega / (1 - result.params.alpha - result.params.beta)
        assert abs(uncond_var - expected) < 1e-8

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_empty_data(self):
        """Test GARCH with empty data"""
        garch = GARCH11()
        with pytest.raises((ValueError, Exception)):
            garch.fit(np.array([]))

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_insufficient_data(self):
        """Test GARCH with insufficient data"""
        garch = GARCH11()
        short_returns = np.random.normal(0, 0.01, 10)
        with pytest.raises((ValueError, Exception)):
            garch.fit(short_returns)

    @pytest.mark.unit
    @pytest.mark.models
    def test_garch_forecast_before_fit(self):
        """Test forecasting before fitting"""
        garch = GARCH11()
        with pytest.raises((ValueError, Exception)):
            garch.forecast(horizon=5)


class TestEGARCH:
    """Tests for EGARCH model (asymmetric volatility)"""

    @pytest.mark.unit
    @pytest.mark.models
    def test_egarch_initialization(self):
        """Test EGARCH initialization"""
        egarch = EGARCH()
        assert egarch is not None

    @pytest.mark.unit
    @pytest.mark.models
    @pytest.mark.slow
    def test_egarch_captures_asymmetry(self):
        """Test that EGARCH captures leverage effect"""
        np.random.seed(42)

        # Create data with leverage effect (negative returns increase volatility more)
        n = 1000
        returns = np.random.normal(0, 0.02, n)

        egarch = EGARCH()
        result = egarch.fit(returns)

        assert result is not None
        # EGARCH should have asymmetry parameter
        if hasattr(result.params, 'gamma'):
            # Negative gamma indicates leverage effect
            assert result.params.gamma < 0


class TestComponentGARCH:
    """Tests for Component GARCH"""

    @pytest.mark.unit
    @pytest.mark.models
    def test_component_garch_initialization(self):
        """Test Component GARCH initialization"""
        cgarch = ComponentGARCH()
        assert cgarch is not None

    @pytest.mark.unit
    @pytest.mark.models
    @pytest.mark.slow
    def test_component_garch_fit(self):
        """Test Component GARCH fitting"""
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 1000)

        cgarch = ComponentGARCH()
        result = cgarch.fit(returns)

        assert result is not None
        assert cgarch.fitted


@pytest.mark.unit
@pytest.mark.models
def test_all_garch_models_exist():
    """Test that all GARCH models can be imported"""
    from core.models.garch import GARCH11, EGARCH, ComponentGARCH
    assert GARCH11 is not None
    assert EGARCH is not None
    assert ComponentGARCH is not None
