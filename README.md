# Quantitative Trading Research Platform

A comprehensive research-grade infrastructure for studying algorithmic trading strategies, market microstructure, and AI-driven decision systems.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full demo to see all components
python run_demo.py

# Or run specific component demos
python run_demo.py math       # Mathematical models
python run_demo.py hft        # HFT components
python run_demo.py portfolio  # Portfolio optimization
python run_demo.py execution  # Execution algorithms
python run_demo.py backtest   # Backtesting engine
python run_demo.py monitor    # Monitoring & alerts
python run_demo.py engine     # Trading engine
```

## ⚠️ Honest Disclaimers

1. **No Holy Grail**: This is a research platform, not a money printer. Markets are adversarial, adaptive, and full of smarter players.
2. **Past Performance ≠ Future Results**: Every backtest is an optimistic estimate due to survivorship bias, lookahead bias, and regime changes.
3. **Execution Reality**: Slippage, latency, and market impact will degrade any theoretical edge.

## 📊 What's Included

### Mathematical Models (`src/core/models/`)
- **GARCH Family**: GARCH(1,1), EGARCH, Component GARCH for volatility forecasting
- **Regime Switching**: Markov models with Hamilton filter for market regime detection
- **Copulas**: Gaussian, Student-t, Clayton, Gumbel for dependency modeling

### Signal Processing (`src/core/signals/`)
- **Fourier Analysis**: Spectral decomposition for cycle detection
- **Wavelet Transform**: Multi-resolution analysis and denoising
- **Kalman Filter**: State estimation and signal extraction

### AI/ML Models (`src/ai/`)
- **Neural Networks**: LSTM, Transformer, Temporal Fusion Networks
- **Ensemble Methods**: Mixture of Experts, Stacking, Boosting
- **Reinforcement Learning**: PPO agent for trading decisions

### High-Frequency Trading (`src/hft/`)
- **Order Book Analysis**: Imbalance signals, depth analysis
- **Microstructure**: Kyle lambda, price impact estimation
- **Market Making**: Avellaneda-Stoikov framework
- **Latency Monitoring**: μs-level performance tracking

### Portfolio Optimization (`src/portfolio/`)
- **Mean-Variance**: Classic Markowitz with constraints
- **Risk Parity**: Equal risk contribution
- **Black-Litterman**: Bayesian view incorporation

### Execution (`src/execution/`)
- **Smart Order Router**: Multi-venue routing optimization
- **Market Impact**: Almgren-Chriss, transient impact models
- **Algorithms**: TWAP, VWAP, Implementation Shortfall, POV
- **TCA**: Transaction cost analysis and attribution

### Alternative Data (`src/alternative_data/`)
- **Sentiment Analysis**: News, social media, SEC filings
- **Financial NLP**: Entity extraction, event detection
- **Macro Indicators**: Economic calendar, cross-asset signals

### Research (`src/research/`)
- **Backtesting**: Event-driven engine with realistic costs
- **Walk-Forward**: Out-of-sample optimization
- **Cross-Validation**: Purged K-fold for time series

### Monitoring (`src/monitoring/`)
- **Dashboard**: Real-time P&L, positions, risk
- **Alerts**: Configurable rules and notifications
- **Health Checks**: System component monitoring

### Trading Engine (`src/api/`)
- **Event-Driven**: Pub/sub architecture
- **Strategy Framework**: Base classes for strategy development
- **Orchestration**: Full system coordination

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      STRATEGY LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Momentum    │  │ Mean Revert  │  │   ML-Based   │           │
│  │  Strategy    │  │   Strategy   │  │   Strategy   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI/ML LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ LSTM+Attn    │  │     RL       │  │   Ensemble   │           │
│  │ Time Series  │  │    Agent     │  │   Decision   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    Smart     │  │    TWAP/     │  │   Market     │           │
│  │   Router     │  │    VWAP      │  │   Impact     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RISK & MONITORING                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    Risk      │  │    Kill      │  │   Real-time  │           │
│  │   Manager    │  │   Switch     │  │  Dashboard   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Directory Structure

```
src/
├── core/
│   ├── math/           # Stochastic models, Kelly criterion, Monte Carlo
│   ├── signals/        # Signal processing (Fourier, Wavelets, Kalman)
│   └── models/         # GARCH, Regime Switching, Copulas
├── ai/
│   ├── networks/       # Neural architectures (LSTM, Transformer, Ensemble)
│   ├── agents/         # Reinforcement learning (PPO)
│   └── features/       # Feature engineering
├── hft/
│   ├── orderbook.py    # Order book analysis
│   ├── microstructure.py # Market microstructure signals
│   ├── market_making.py  # Avellaneda-Stoikov
│   └── latency.py      # Latency monitoring
├── portfolio/
│   └── optimization.py # Mean-Variance, Risk Parity, Black-Litterman
├── execution/
│   ├── smart_router.py # Smart order routing
│   ├── algorithms.py   # TWAP, VWAP, IS
│   ├── market_impact.py # Almgren-Chriss
│   └── tca.py          # Transaction cost analysis
├── alternative_data/
│   ├── sentiment.py    # Sentiment analysis
│   ├── nlp.py          # Financial NLP
│   └── macro.py        # Macro indicators
├── monitoring/
│   ├── dashboard.py    # Trading dashboard
│   ├── alerts.py       # Alert management
│   └── health.py       # System health
├── research/
│   └── backtesting/    # Backtesting engine
├── datastore/
│   ├── schemas.py      # Database schemas
│   ├── pipeline.py     # Data pipelines
│   └── store.py        # Time-series & feature stores
├── api/
│   ├── strategy.py     # Strategy framework
│   ├── events.py       # Event system
│   └── engine.py       # Trading engine
└── infrastructure/
    ├── execution/      # Order management
    ├── data/           # Market data
    └── risk/           # Risk management, kill switch

examples/               # Demo scripts
config/                 # Configuration files
docs/                   # Documentation
```

## 💡 Usage Examples

### 1. Volatility Forecasting with GARCH

```python
from src.core.models.garch import GARCH, EGARCH

# Fit GARCH model
garch = GARCH(p=1, q=1)
garch.fit(returns)

# Forecast volatility
vol_forecast = garch.forecast(horizon=10)
print(f"10-day volatility forecast: {vol_forecast[-1]:.2%}")
```

### 2. Portfolio Optimization

```python
from src.portfolio.optimization import MeanVarianceOptimizer, RiskParityOptimizer

# Mean-Variance
mv = MeanVarianceOptimizer(expected_returns, covariance, symbols)
max_sharpe_weights = mv.maximum_sharpe(risk_free_rate=0.03)

# Risk Parity
rp = RiskParityOptimizer(covariance, symbols)
rp_weights = rp.optimize()
```

### 3. Smart Order Routing

```python
from src.execution.smart_router import SmartOrderRouter, RoutingStrategy

router = SmartOrderRouter(venues)
decision = router.route_order(
    symbol='AAPL',
    side='buy',
    quantity=5000,
    strategy=RoutingStrategy.MINIMIZE_COST
)
```

### 4. Backtesting

```python
from src.research.backtesting.engine import BacktestEngine, BacktestConfig

config = BacktestConfig(
    initial_capital=1_000_000,
    commission_rate=0.001,
    slippage_rate=0.0005
)

engine = BacktestEngine(config)
engine.load_data(dates, prices, volumes)
results = engine.run(my_strategy)

print(f"Sharpe: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.1%}")
```

### 5. Creating a Strategy

```python
from src.api.strategy import Strategy, StrategyConfig, Signal

class MyStrategy(Strategy):
    def on_data(self, context):
        signals = []
        for symbol in self.symbols:
            price = context.get_price(symbol)
            # Your logic here
            if should_buy:
                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=0.8,
                    confidence=0.7
                ))
        return signals
```

## 🔧 Requirements

- Python 3.10+
- PyTorch 2.0+
- NumPy, SciPy, Pandas
- See `requirements.txt` for full list

## 📖 Core Concepts

### Why Markets Move: A First-Principles View

Markets are not random walks. They are **adversarial games** where:
- **Information asymmetry** creates short-term predictability
- **Behavioral biases** create systematic mispricings
- **Liquidity dynamics** create mechanical price pressure
- **Algorithmic herding** creates momentum and mean-reversion regimes

The edge lies in understanding **why** other participants will buy or sell, not in detecting patterns after they've formed.

## ⚠️ Risk Warning

This software is for research and educational purposes only. Trading financial instruments carries significant risk:

- You can lose more than your initial investment
- Past performance does not guarantee future results
- Backtests are always optimistic due to various biases
- Markets are adaptive and edges decay

**Never trade with money you cannot afford to lose.**

## 📄 License

Research and educational use only. Not financial advice.
