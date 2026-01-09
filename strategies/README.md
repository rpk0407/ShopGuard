# Trading Strategies Library

Pre-built, research-backed trading strategies ready to deploy.

## Available Strategies

### 1. Momentum Strategies (`momentum.py`)

#### MomentumStrategy
- **Type**: Trend Following
- **Logic**: Buy winners, sell losers based on past returns
- **Parameters**:
  - `lookback_period`: Days to measure momentum (default: 20)
  - `num_positions`: Max concurrent positions (default: 5)
  - `momentum_threshold`: Minimum momentum to trade (default: 2%)
- **Academic Basis**: Jegadeesh & Titman (1993)
- **Best For**: Trending markets, medium-term horizons

#### DualMomentumStrategy
- **Type**: Absolute + Relative Momentum
- **Logic**: Combines trend-following with cross-sectional ranking
- **Parameters**:
  - `lookback_period`: Momentum calculation period
  - `rebalance_frequency`: Days between rebalancing
- **Academic Basis**: Antonacci (2014)
- **Best For**: Systematic trend following, risk management

### 2. Mean Reversion Strategies (`mean_reversion.py`)

#### MeanReversionStrategy
- **Type**: Statistical Arbitrage
- **Logic**: Buy oversold, sell overbought based on moving average
- **Parameters**:
  - `lookback_period`: MA calculation period (default: 20)
  - `entry_threshold`: Standard deviations for entry (default: 2.0)
  - `exit_threshold`: Standard deviations for exit (default: 0.5)
- **Academic Basis**: Poterba & Summers (1988)
- **Best For**: Range-bound markets, short holding periods

#### PairsTradingStrategy
- **Type**: Statistical Arbitrage
- **Logic**: Trade spread between cointegrated pairs
- **Parameters**:
  - `correlation_threshold`: Minimum correlation (default: 0.7)
  - `entry_threshold`: Z-score for entry (default: 2.0)
- **Academic Basis**: Gatev, Goetzmann & Rouwenhorst (2006)
- **Best For**: Market-neutral returns, lower volatility

### 3. Machine Learning Strategies (`ml_strategy.py`)

#### MLPredictionStrategy
- **Type**: Predictive ML
- **Logic**: Use trained neural network for return predictions
- **Models**: LSTM, Transformer, Ensemble
- **Parameters**:
  - `prediction_horizon`: Days ahead to predict (default: 5)
  - `confidence_threshold`: Minimum confidence to trade (default: 0.6)
  - `model_path`: Path to saved model
- **Best For**: Complex patterns, multi-factor analysis

#### EnsembleMLStrategy
- **Type**: Multi-Model Ensemble
- **Logic**: Combine predictions from multiple ML models
- **Models**: TFT, LSTM, Random Forest, GBM
- **Parameters**:
  - Same as MLPredictionStrategy
- **Best For**: Robustness, reducing model risk

### 4. Trend Following Strategies (`trend_following.py`)

#### TrendFollowingStrategy
- **Type**: Moving Average Crossover
- **Logic**: Golden cross (buy) / Death cross (sell)
- **Parameters**:
  - `fast_period`: Fast MA period (default: 10)
  - `slow_period`: Slow MA period (default: 50)
  - `atr_period`: ATR for position sizing (default: 14)
- **Academic Basis**: Faber (2007)
- **Best For**: Simple, robust trend capture

#### BreakoutStrategy
- **Type**: Channel Breakout
- **Logic**: Donchian channel breakouts with volume confirmation
- **Parameters**:
  - `lookback_period`: Channel period (default: 20)
  - `volume_threshold`: Volume confirmation multiplier (default: 1.5)
- **Academic Basis**: Turtle Traders, Richard Donchian
- **Best For**: Capturing strong momentum moves

## Usage Examples

### Quick Start

```python
from strategies import MomentumStrategy, MeanReversionStrategy
from api.strategy import StrategyConfig

# Create configuration
config = StrategyConfig(
    name="MyMomentumStrategy",
    symbols=['AAPL', 'GOOGL', 'MSFT', 'NVDA'],
    max_position_pct=0.2
)

# Initialize strategy
strategy = MomentumStrategy(config)

# Start trading
strategy.start()
```

### Custom Configuration

```python
from strategies.momentum import MomentumConfig, MomentumStrategy

config = MomentumConfig(
    name="AggressiveMomentum",
    symbols=['AAPL', 'GOOGL', 'MSFT'],
    lookback_period=10,  # Shorter lookback
    holding_period=3,     # Faster turnover
    num_positions=10,     # More positions
    momentum_threshold=0.01  # Lower threshold
)

strategy = MomentumStrategy(config)
strategy.start()
```

### Pairs Trading

```python
from strategies.mean_reversion import PairsTradingConfig, PairsTradingStrategy

config = PairsTradingConfig(
    name="PairsTrading",
    symbols=['XOM', 'CVX', 'BP', 'SHEL'],  # Energy stocks
    lookback_period=60,
    entry_threshold=2.0,
    correlation_threshold=0.75
)

strategy = PairsTradingStrategy(config)
strategy.start()
```

### ML Strategy with Custom Model

```python
from strategies.ml_strategy import MLStrategyConfig, MLPredictionStrategy

config = MLStrategyConfig(
    name="MLStrategy",
    symbols=['SPY', 'QQQ', 'IWM'],
    prediction_horizon=5,
    confidence_threshold=0.65,
    model_path='models/my_trained_model.pt'
)

strategy = MLPredictionStrategy(config)
strategy.start()
```

## Strategy Comparison

| Strategy | Type | Risk | Return Potential | Complexity | Best Market |
|----------|------|------|------------------|------------|-------------|
| Momentum | Directional | Medium | High | Low | Trending |
| Mean Reversion | Directional | Medium | Medium | Low | Range-bound |
| Pairs Trading | Market-Neutral | Low | Low-Medium | Medium | Any |
| Trend Following | Directional | Medium | High | Low | Trending |
| Breakout | Directional | High | High | Medium | Volatile |
| ML Prediction | Directional | Varies | High | High | Any |

## Combining Strategies

### Portfolio Approach

```python
from api.engine import TradingEngine
from strategies import *

# Create multiple strategies
momentum = MomentumStrategy(momentum_config)
mean_rev = MeanReversionStrategy(mean_rev_config)
pairs = PairsTradingStrategy(pairs_config)

# Add to engine
engine = TradingEngine()
engine.add_strategy(momentum, weight=0.4)
engine.add_strategy(mean_rev, weight=0.3)
engine.add_strategy(pairs, weight=0.3)

# Run combined portfolio
engine.start()
```

## Backtesting

```python
from research.backtesting.engine import BacktestEngine, BacktestConfig
from strategies import MomentumStrategy

# Configure backtest
backtest_config = BacktestConfig(
    initial_capital=100000,
    commission_rate=0.001,
    slippage_rate=0.0005,
    start_date='2020-01-01',
    end_date='2023-12-31'
)

# Create strategy
strategy = MomentumStrategy(strategy_config)

# Run backtest
engine = BacktestEngine(backtest_config)
results = engine.run(strategy)

# Analyze results
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.1%}")
print(f"Total Return: {results['total_return']:.1%}")
```

## Performance Monitoring

All strategies include built-in logging and metrics:

```python
strategy = MomentumStrategy(config)

# Access strategy metrics
print(f"Total trades: {strategy.metrics.total_trades}")
print(f"Win rate: {strategy.metrics.win_rate:.1%}")
print(f"Sharpe ratio: {strategy.metrics.sharpe_ratio:.2f}")
print(f"Current positions: {strategy.metrics.num_positions}")
```

## Risk Management

Strategies respect global risk limits:

```python
from api.strategy import StrategyConfig

config = StrategyConfig(
    name="SafeStrategy",
    symbols=['AAPL', 'MSFT'],
    max_position_pct=0.1,      # Max 10% per position
    max_order_pct=0.05,         # Max 5% per order
    cooldown_seconds=300        # 5 min between signals
)
```

## Best Practices

1. **Diversification**: Use multiple uncorrelated strategies
2. **Position Sizing**: Start small, scale up gradually
3. **Risk Management**: Always set position limits
4. **Backtesting**: Test thoroughly before live trading
5. **Monitoring**: Track performance metrics daily
6. **Adaptation**: Rebalance and retrain regularly

## Adding Custom Strategies

```python
from api.strategy import Strategy, Signal, StrategyContext

class MyCustomStrategy(Strategy):
    def on_start(self):
        self.log("Custom strategy started")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        signals = []

        # Your logic here
        for symbol in self.symbols:
            price = context.get_price(symbol)
            # ... analyze and generate signals

        return signals

    def on_stop(self):
        self.log("Custom strategy stopped")
```

## References

### Academic Papers
- Jegadeesh & Titman (1993) - Momentum
- Antonacci (2014) - Dual Momentum
- Poterba & Summers (1988) - Mean Reversion
- Gatev et al. (2006) - Pairs Trading
- Faber (2007) - Trend Following

### Books
- "Quantitative Trading" by Ernest Chan
- "Algorithmic Trading" by Ernest Chan
- "Advances in Financial Machine Learning" by Marcos Lopez de Prado
- "Systematic Trading" by Robert Carver

## Support

For questions and issues:
- Documentation: See main README.md
- Examples: Check `examples/` directory
- Tests: Run `pytest tests/`
