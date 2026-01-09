"""
Unit Tests for Portfolio Optimization

Tests:
- Mean-Variance optimization
- Risk Parity
- Black-Litterman
- Constraints handling
- Edge cases
"""

import pytest
import numpy as np
from portfolio.optimization import (
    MeanVarianceOptimizer,
    RiskParityOptimizer,
    BlackLittermanOptimizer
)


class TestMeanVarianceOptimizer:
    """Tests for Mean-Variance optimization"""

    @pytest.fixture
    def sample_data(self):
        """Sample expected returns and covariance matrix"""
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']
        expected_returns = np.array([0.12, 0.15, 0.10, 0.18])

        # Create a positive definite covariance matrix
        correlation = np.array([
            [1.0, 0.6, 0.7, 0.5],
            [0.6, 1.0, 0.5, 0.6],
            [0.7, 0.5, 1.0, 0.6],
            [0.5, 0.6, 0.6, 1.0]
        ])
        volatilities = np.array([0.20, 0.25, 0.18, 0.30])
        covariance = np.outer(volatilities, volatilities) * correlation

        return expected_returns, covariance, symbols

    @pytest.mark.unit
    @pytest.mark.fast
    def test_initialization(self, sample_data):
        """Test optimizer initialization"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        assert optimizer is not None
        assert len(optimizer.symbols) == 4

    @pytest.mark.unit
    def test_maximum_sharpe(self, sample_data):
        """Test maximum Sharpe ratio portfolio"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        weights = optimizer.maximum_sharpe(risk_free_rate=0.02)

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # All weights should be between 0 and 1 (long-only)
        assert all(w >= -1e-6 for w in weights)
        assert all(w <= 1.0 + 1e-6 for w in weights)

    @pytest.mark.unit
    def test_minimum_variance(self, sample_data):
        """Test minimum variance portfolio"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        weights = optimizer.minimum_variance()

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # Calculate portfolio variance
        portfolio_variance = weights @ covariance @ weights

        # Should be minimal among all possible portfolios
        assert portfolio_variance > 0

    @pytest.mark.unit
    def test_efficient_return(self, sample_data):
        """Test efficient portfolio for target return"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        target_return = 0.12
        weights = optimizer.efficient_return(target_return)

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # Portfolio return should match target
        portfolio_return = weights @ expected_returns
        assert abs(portfolio_return - target_return) < 1e-4

    @pytest.mark.unit
    def test_efficient_risk(self, sample_data):
        """Test efficient portfolio for target risk"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        target_volatility = 0.15
        weights = optimizer.efficient_risk(target_volatility)

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # Portfolio volatility should match target
        portfolio_variance = weights @ covariance @ weights
        portfolio_volatility = np.sqrt(portfolio_variance)
        assert abs(portfolio_volatility - target_volatility) < 1e-3

    @pytest.mark.unit
    def test_long_short_constraints(self, sample_data):
        """Test with long-short constraints"""
        expected_returns, covariance, symbols = sample_data
        optimizer = MeanVarianceOptimizer(expected_returns, covariance, symbols)

        weights = optimizer.maximum_sharpe(
            risk_free_rate=0.02,
            weight_bounds=(-0.5, 1.5)  # Allow some shorting
        )

        assert abs(np.sum(weights) - 1.0) < 1e-6
        assert all(w >= -0.5 - 1e-6 for w in weights)
        assert all(w <= 1.5 + 1e-6 for w in weights)


class TestRiskParityOptimizer:
    """Tests for Risk Parity optimization"""

    @pytest.fixture
    def sample_covariance(self):
        """Sample covariance matrix"""
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']
        correlation = np.array([
            [1.0, 0.6, 0.7, 0.5],
            [0.6, 1.0, 0.5, 0.6],
            [0.7, 0.5, 1.0, 0.6],
            [0.5, 0.6, 0.6, 1.0]
        ])
        volatilities = np.array([0.20, 0.25, 0.18, 0.30])
        covariance = np.outer(volatilities, volatilities) * correlation

        return covariance, symbols

    @pytest.mark.unit
    def test_risk_parity_optimization(self, sample_covariance):
        """Test risk parity optimization"""
        covariance, symbols = sample_covariance
        optimizer = RiskParityOptimizer(covariance, symbols)

        weights = optimizer.optimize()

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # All weights should be positive
        assert all(w > -1e-6 for w in weights)

        # Calculate risk contributions
        portfolio_volatility = np.sqrt(weights @ covariance @ weights)
        marginal_risk = covariance @ weights / portfolio_volatility
        risk_contributions = weights * marginal_risk

        # Risk contributions should be approximately equal
        expected_contribution = portfolio_volatility / len(weights)
        for rc in risk_contributions:
            assert abs(rc - expected_contribution) < 0.05  # Allow some tolerance

    @pytest.mark.unit
    def test_risk_parity_diversification(self, sample_covariance):
        """Test that risk parity achieves diversification"""
        covariance, symbols = sample_covariance
        optimizer = RiskParityOptimizer(covariance, symbols)

        weights = optimizer.optimize()

        # Risk parity should not put all weight in one asset
        assert all(w < 0.9 for w in weights)

        # Should have meaningful allocation to multiple assets
        significant_weights = sum(1 for w in weights if w > 0.1)
        assert significant_weights >= 2


class TestBlackLittermanOptimizer:
    """Tests for Black-Litterman optimization"""

    @pytest.fixture
    def sample_bl_data(self):
        """Sample data for Black-Litterman"""
        symbols = ['AAPL', 'GOOGL', 'MSFT']

        # Market equilibrium returns
        market_weights = np.array([0.4, 0.3, 0.3])

        # Covariance
        correlation = np.array([
            [1.0, 0.6, 0.7],
            [0.6, 1.0, 0.5],
            [0.7, 0.5, 1.0]
        ])
        volatilities = np.array([0.20, 0.25, 0.18])
        covariance = np.outer(volatilities, volatilities) * correlation

        # Investor views
        P = np.array([[1, 0, -1]])  # AAPL will outperform MSFT
        Q = np.array([0.05])  # By 5%

        return market_weights, covariance, P, Q, symbols

    @pytest.mark.unit
    @pytest.mark.slow
    def test_black_litterman_with_views(self, sample_bl_data):
        """Test Black-Litterman with investor views"""
        market_weights, covariance, P, Q, symbols = sample_bl_data

        optimizer = BlackLittermanOptimizer(
            market_weights=market_weights,
            covariance=covariance,
            P=P,
            Q=Q,
            symbols=symbols
        )

        weights = optimizer.optimize()

        # Weights should sum to 1
        assert abs(np.sum(weights) - 1.0) < 1e-6

        # All weights should be reasonable
        assert all(w >= -1e-6 for w in weights)
        assert all(w <= 1.0 + 1e-6 for w in weights)

    @pytest.mark.unit
    def test_black_litterman_no_views(self, sample_bl_data):
        """Test Black-Litterman without views (should return market weights)"""
        market_weights, covariance, P, Q, symbols = sample_bl_data

        # No views
        optimizer = BlackLittermanOptimizer(
            market_weights=market_weights,
            covariance=covariance,
            P=np.array([[]]),
            Q=np.array([]),
            symbols=symbols
        )

        weights = optimizer.optimize()

        # Should be close to market weights
        for w_bl, w_market in zip(weights, market_weights):
            assert abs(w_bl - w_market) < 0.1


@pytest.mark.unit
def test_all_optimizers_exist():
    """Test that all optimizers can be imported"""
    from portfolio.optimization import (
        MeanVarianceOptimizer,
        RiskParityOptimizer,
        BlackLittermanOptimizer
    )
    assert MeanVarianceOptimizer is not None
    assert RiskParityOptimizer is not None
    assert BlackLittermanOptimizer is not None
