# Quantitative Trading Research Platform

A research-grade infrastructure for studying algorithmic trading strategies, market microstructure, and AI-driven decision systems.

## Honest Disclaimers

1. **No Holy Grail**: This is a research platform, not a money printer. Markets are adversarial, adaptive, and full of smarter players.
2. **Past Performance ≠ Future Results**: Every backtest is an optimistic estimate due to survivorship bias, lookahead bias, and regime changes.
3. **Execution Reality**: Slippage, latency, and market impact will degrade any theoretical edge.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      RESEARCH LAYER (Python)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Backtesting  │  │   Feature    │  │   Strategy   │           │
│  │   Engine     │  │  Engineering │  │   Research   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI/ML LAYER (Python/PyTorch)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ LSTM+Attn    │  │     RL       │  │   Ensemble   │           │
│  │ Time Series  │  │    Agent     │  │   Decision   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER (Rust/C++)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    Order     │  │    Risk      │  │   Market     │           │
│  │   Router     │  │   Manager    │  │   Gateway    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (TimescaleDB)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Tick Data   │  │  Order Book  │  │  Alternative │           │
│  │   Storage    │  │   Snapshots  │  │     Data     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/
├── core/
│   ├── math/           # Stochastic models, Kelly criterion, Monte Carlo
│   ├── signals/        # Signal processing (Fourier, Wavelets, Kalman)
│   └── models/         # Statistical models (GARCH, regime detection)
├── ai/
│   ├── networks/       # Neural architectures (LSTM, Transformer, etc.)
│   ├── agents/         # Reinforcement learning agents (PPO, SAC)
│   └── features/       # Feature engineering and selection
├── infrastructure/
│   ├── execution/      # Order management and routing
│   ├── data/           # Data ingestion and storage
│   └── risk/           # Risk management and kill switches
└── research/
    ├── backtesting/    # Historical simulation engine
    └── analysis/       # Performance analytics

config/                 # Configuration files
tests/                  # Unit and integration tests
docs/                   # Extended documentation
```

## Core Concepts

### Why Markets Move: A First-Principles View

Markets are not random walks. They are **adversarial games** where:
- **Information asymmetry** creates short-term predictability
- **Behavioral biases** create systematic mispricings
- **Liquidity dynamics** create mechanical price pressure
- **Algorithmic herding** creates momentum and mean-reversion regimes

The edge lies in understanding **why** other participants will buy or sell, not in detecting patterns after they've formed.

## Requirements

- Python 3.11+
- PyTorch 2.0+
- Rust 1.70+ (for execution layer)
- TimescaleDB 2.0+
- Redis (for real-time state)

## License

Research and educational use only. Not financial advice.
