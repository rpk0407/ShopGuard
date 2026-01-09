# TITAN Trading Strategy Architecture

> **Core Philosophy**: "Don't be exit liquidity!"

## System Overview

TITAN is a sophisticated crypto trading system that combines technical analysis with external alpha sources to generate high-conviction trading signals while protecting against manipulation and market traps.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         TITAN TRADING SYSTEM ARCHITECTURE                        ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                  ║
║   EXTERNAL ALPHA LAYER (Smart Money Edition)                                    ║
║   ┌────────────────────────────────────────────────────────────────────────┐    ║
║   │  Smart Money Tracker → Whale Manipulation Detector → Signal Quality    │    ║
║   │  Sentiment Extremes → Liquidity Trap Detector → News Filter           │    ║
║   │  Polymarket Scanner → Social Sentiment → News Sentiment               │    ║
║   └──────────────────────────────┬─────────────────────────────────────────┘    ║
║                                  │                                               ║
║   TECHNICAL ANALYSIS LAYER       ▼                                               ║
║   ┌────────────────────────────────────────────────────────────────────────┐    ║
║   │  CVD Engine (Micro-Check) ──────────────────────────┐                  │    ║
║   │  Entropy Filter (Bio-Check) ────────────────────────┼──→ Signal       │    ║
║   │  Hurst Exponent (Physics-Check) ────────────────────┤    Combiner     │    ║
║   │  Regime Detector ───────────────────────────────────┘                  │    ║
║   └──────────────────────────────┬─────────────────────────────────────────┘    ║
║                                  │                                               ║
║   DECISION LAYER                 ▼                                               ║
║   ┌────────────────────────────────────────────────────────────────────────┐    ║
║   │                         TITAN BRAIN                                    │    ║
║   │              Three-Pillar Convergence Strategy                         │    ║
║   │         BIO + PHYSICS + MICRO = GO/NO-GO Decision                     │    ║
║   └──────────────────────────────┬─────────────────────────────────────────┘    ║
║                                  │                                               ║
║   RISK LAYER                     ▼                                               ║
║   ┌────────────────────────────────────────────────────────────────────────┐    ║
║   │  Dynamic Risk Engine (ATR-Based)                                       │    ║
║   │  - Stops that breathe with volatility                                  │    ║
║   │  - Position sizing by regime                                           │    ║
║   └──────────────────────────────┬─────────────────────────────────────────┘    ║
║                                  │                                               ║
║   EXECUTION LAYER                ▼                                               ║
║   ┌────────────────────────────────────────────────────────────────────────┐    ║
║   │  Hyperliquid Broker + Funding Rate Arbitrage                          │    ║
║   └────────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Layer 1: External Alpha Sources (Smart Money Edition)

### Philosophy
- Don't follow retail (dumb money) - they panic sell at bottoms and FOMO buy at tops
- Don't blindly follow whales - they manipulate copy traders
- Require multiple independent sources to agree
- When in doubt, stay out

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Smart Money Tracker | `signals/external/smart_money.py` | Track whale vs retail divergence |
| Whale Manipulation Detector | `signals/external/whale_manipulation.py` | Detect fake whale activity |
| Sentiment Extremes | `signals/external/sentiment_extremes.py` | Fear & Greed contrarian signals |
| Liquidity Trap Detector | `signals/external/liquidity_trap.py` | Detect FOMO/PANIC traps |
| News Filter | `signals/external/news_filter.py` | Filter 90% noise from news |
| Signal Quality Analyzer | `signals/external/signal_quality.py` | Cross-validate all signals |
| Signal Aggregator | `signals/external/aggregator.py` | Combine all external signals |

### Key Rules

#### Smart Money Tracking
```
When whales BUY + retail SELLS = BUY SIGNAL
When whales SELL + retail BUYS = SELL SIGNAL (don't be exit liquidity!)
```

#### Whale Manipulation Detection
```
Single whale, visible, instant trade = SUSPICIOUS (likely pump/dump)
Multiple whales, stealth, gradual accumulation = TRUSTWORTHY
```

#### Sentiment Extremes (Fear & Greed)
```
F&G < 20 (Extreme Fear) = CONTRARIAN BUY
F&G > 80 (Extreme Greed) = CONTRARIAN SELL
```

#### Liquidity Trap Detection
```
Retail FOMO (buying) + Whale Distribution (selling) = FOMO TRAP → DON'T BUY
Retail PANIC (selling) + Whale Accumulation (buying) = PANIC TRAP → BUY
```

#### Signal Quality Gate
```
EXCELLENT (4+ sources agree) = 100% position
GOOD (3+ sources agree) = 70% position
MODERATE (2+ sources agree) = 40% position
LOW (1 source) = 10% or skip
UNRELIABLE (conflicts) = BLOCKED
```

---

## Layer 2: Technical Analysis (Three-Pillar Convergence)

### Pillar 1: BIO-CHECK (Shannon Entropy)
**File**: `titan_mvp/signals/entropy_filter.py`

Measures market order vs chaos using information theory.

| Regime | Entropy | Action |
|--------|---------|--------|
| CRYSTAL | < 0.6 | TRADE - Market is ordered |
| LIQUID | 0.6-0.8 | CAUTION - Normal conditions |
| GAS | > 0.8 | NO TRADE - Chaotic, random |

### Pillar 2: PHYSICS-CHECK (Hurst Exponent)
**File**: `titan_mvp/signals/entropy_filter.py`

Measures trend persistence vs mean reversion.

| Hurst (H) | Meaning | Strategy |
|-----------|---------|----------|
| H > 0.65 | Trending | Follow the trend |
| H = 0.5 | Random walk | Stay out |
| H < 0.45 | Mean-reverting | Counter-trade |

### Pillar 3: MICRO-CHECK (CVD Divergence)
**File**: `titan_mvp/signals/cvd_engine.py`

Detects order flow divergences between price and Cumulative Volume Delta.

```
BULLISH DIVERGENCE:
  Price makes Lower Low + CVD makes Higher Low
  → Sellers exhausted, buyers absorbing → BUY

BEARISH DIVERGENCE:
  Price makes Higher High + CVD makes Lower High
  → Buyers exhausted, selling into strength → SELL
```

---

## Layer 3: Decision Engine (TitanBrain)

**File**: `shopguard_platform/src/core/titan_brain.py`

### Three-Pillar Convergence Logic

```python
bio_check = entropy < 2.5          # Market is ordered
physics_check = hurst > 0.55        # Trend is persistent
micro_check = viral_k > 1.1         # Momentum is self-sustaining
cvd_check = cvd > threshold         # Order flow confirms

pillars_aligned = sum([bio_check, physics_check, micro_check, cvd_check])

if pillars_aligned >= 3 and conviction >= 0.7:
    signal = STRONG_BUY
elif pillars_aligned >= 2 and conviction >= 0.5:
    signal = BUY
else:
    signal = HOLD
```

### Signal Types
- `STRONG_BUY` - 3+ pillars aligned, high conviction
- `BUY` - 2+ pillars aligned, good conviction
- `HOLD` - Insufficient alignment
- `SELL` - Bearish conditions
- `EXIT` - Emergency exit (crash/high CVD selling)

---

## Layer 4: Risk Management (Dynamic ATR-Based)

**File**: `shopguard_platform/src/core/risk_math.py`

### Key Principles
1. **Stops breathe with volatility** - ATR-based, not fixed percentage
2. **Position sizing adjusts** - Smaller in high volatility
3. **Minimum 2:1 risk/reward** - Never take bad R:R trades

### Volatility Regime Adjustments

| Regime | ATR % | Stop Multiple | Position Size |
|--------|-------|---------------|---------------|
| Ultra Low | < 0.5% | 1.0x ATR | 100% |
| Low | 0.5-1% | 1.2x ATR | 100% |
| Normal | 1-2% | 1.5x ATR | 80% |
| Elevated | 2-3% | 1.8x ATR | 60% |
| High | 3-5% | 2.0x ATR | 40% |
| Extreme | > 5% | 2.5x ATR | 20% or AVOID |

---

## Layer 5: Market Regime Detection

**File**: `shopguard_platform/src/core/regime.py`

### Market States

| Regime | ADX | Strategy | Size Multiplier |
|--------|-----|----------|-----------------|
| TRENDING_UP | > 30, +DI > -DI | Trend Following | 1.2x |
| TRENDING_DOWN | > 30, -DI > +DI | Short Trend | 1.0x |
| RANGING | < 20 | Mean Reversion | 0.8x |
| VOLATILE | High ATR | Reduce Exposure | 0.3x |
| BREAKOUT | Range expansion | Breakout | 1.0x |
| ACCUMULATION | Low vol, up | Scale In | 1.5x |
| DISTRIBUTION | High vol, down | Scale Out | 0.5x |

---

## Layer 6: Execution (Hyperliquid)

**File**: `shopguard_platform/brokers/trading_engine.py`

### Features
- Real-time WebSocket for CVD and trades
- ATR-based stop loss and take profit
- Position monitoring loop
- Funding rate arbitrage (passive income)

### Signal Flow
```
Hyperliquid WS → CVD State → TitanBrain → Risk Check → Execute
        ↑                         ↓
External Alpha ──────────→ Signal Enhancement
```

---

## Data Sources

### Primary (Technical)
- **Hyperliquid WebSocket**: Real-time trades, CVD calculation
- **Price History**: For entropy, Hurst, ATR calculations

### Secondary (External Alpha)
- **Polymarket**: Prediction market probabilities
- **Twitter/Reddit**: Social sentiment
- **News RSS**: CoinDesk, CoinTelegraph, Reuters

---

## Signal Priority Weights

```
1. Smart Money Flow      40% - What whales are doing
2. Liquidity Trap        25% - Avoid being exit liquidity
3. Sentiment Extremes    20% - Contrarian F&G signals
4. Filtered News         10% - Only real market-moving events
5. Prediction Markets     5% - Probability-based signals
```

---

## Quick Start

### Running the Demo
```bash
python -m shopguard_platform.signals.external.demo
```

### Using the Trading Engine
```python
from shopguard_platform.brokers.trading_engine import TitanTradingEngine, EngineConfig

config = EngineConfig(
    testnet=True,
    assets=["BTC", "ETH"],
    enable_external_signals=True,
    enable_funding_arbitrage=True
)

engine = TitanTradingEngine(config)
await engine.start()
```

---

## Summary: The TITAN Edge

1. **Technical Edge** (Entropy + Hurst + CVD):
   - Only trade in ordered markets (low entropy)
   - Only trade trending conditions (high Hurst)
   - Only enter on order flow divergence (CVD confirms)

2. **Smart Money Edge** (External Alpha):
   - Follow smart money, not retail
   - But verify whales aren't manipulating
   - Be contrarian at sentiment extremes

3. **Quality Gate**:
   - Never trade on single-source signals
   - Require multiple independent confirmations
   - Block conflicting signals

4. **Risk Management**:
   - ATR-based stops that breathe
   - Position sizing by volatility regime
   - Minimum 2:1 risk/reward

**Result**: A system that protects you from being exit liquidity while capturing genuine market moves.
