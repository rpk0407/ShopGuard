# ShopGuard - Crypto Trading Platform

**Automated crypto trading on Hyperliquid DEX with AI-powered strategies**

[![CI/CD](https://github.com/yourusername/ShopGuard/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/yourusername/ShopGuard/actions)
[![Docker](https://img.shields.io/docker/v/yourusername/shopguard?label=docker)](https://ghcr.io/yourusername/shopguard)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/yourusername/ShopGuard.git
cd ShopGuard
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Hyperliquid credentials

# Run
python crypto_quick_start.py
```

## 📊 What is ShopGuard?

ShopGuard is a **production-ready algorithmic trading platform** specifically designed for **crypto perpetual futures** on **Hyperliquid DEX**.

### Why Hyperliquid?

- ✅ **Decentralized** - Trade directly from your wallet
- ✅ **No KYC** - Start trading immediately
- ✅ **High Leverage** - Up to 50x on perpetuals
- ✅ **Low Fees** - Competitive maker/taker rates
- ✅ **Deep Liquidity** - Professional-grade order books
- ✅ **100+ Markets** - BTC, ETH, SOL, AVAX, and more

### Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Strategies** | Pre-built momentum, mean reversion, ML strategies |
| 📈 **Risk Management** | Position sizing, stop losses, leverage control |
| 🔔 **Notifications** | Telegram, Email, SMS alerts for trades |
| 📊 **Analytics** | Real-time P&L, performance metrics |
| 🐳 **Backtesting** | Test strategies on historical data |
| 🔌 **REST API** | Programmatic access via FastAPI |
| 🐳 **Docker** | One-command deployment |
| 🧪 **Testnet** | Risk-free testing environment |

## 🎯 Use Cases

### 1. Automated Trading Bot
```python
from trading.hyperliquid_adapter import HyperliquidAdapter
from strategies import MomentumStrategy

# Connect to Hyperliquid
hl = HyperliquidAdapter(testnet=False)
hl.connect()

# Configure strategy
strategy = MomentumStrategy(config)
strategy.start()  # Bot runs 24/7
```

### 2. Manual Trading with Alerts
```python
# Get notified of opportunities
from notifications import send_trade_notification

# When signal detected
if strong_buy_signal:
    send_trade_notification("BTC", "BUY", 0.1, 40000)
```

### 3. Portfolio Rebalancing
```python
# Automatically rebalance portfolio
from strategies import DualMomentumStrategy

strategy = DualMomentumStrategy(
    symbols=['BTC', 'ETH', 'SOL'],
    rebalance_frequency=7  # Weekly
)
```

## 📦 Installation

### Requirements
- Python 3.10+
- 2GB RAM minimum
- Internet connection for API access

### Method 1: Quick Install

```bash
# Install dependencies
pip install -r requirements.txt

# Test installation
python crypto_quick_start.py --test
```

### Method 2: Docker

```bash
# Build and run
docker-compose up -d

# Access dashboard
open http://localhost:5001
```

### Method 3: From Source

```bash
git clone https://github.com/yourusername/ShopGuard.git
cd ShopGuard
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 🔧 Configuration

### 1. Get Hyperliquid Credentials

**For Testnet** (recommended for beginners):
1. Visit https://app.hyperliquid.xyz/
2. Switch to testnet network
3. Request testnet USDC from faucet
4. Export your wallet's private key

**For Mainnet** (real trading):
1. Create dedicated API wallet in Hyperliquid app
2. Fund with limited capital
3. Use API wallet key (cannot withdraw)

### 2. Configure Environment

Edit `.env`:
```bash
# Hyperliquid Configuration
HYPERLIQUID_PRIVATE_KEY=0x1234...    # Your private key
HYPERLIQUID_TESTNET=true              # Start with testnet!
HYPERLIQUID_WALLET_ADDRESS=0xabc...   # Your wallet address

# Trading Settings
INITIAL_CAPITAL=10000  # Starting capital in USDC
DEFAULT_BROKER=hyperliquid

# Notifications (optional)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Verify Setup

```bash
python crypto_quick_start.py
```

Should show:
- ✓ Connected to Hyperliquid
- ✓ Account balance
- ✓ Available markets
- ✓ Current positions

## 📚 Documentation

- **[Hyperliquid Guide](docs/HYPERLIQUID_GUIDE.md)** - Complete trading guide
- **[Strategy Library](strategies/README.md)** - Pre-built strategies
- **[API Reference](docs/API.md)** - REST API documentation
- **[Docker Guide](DOCKER_DEPLOY.md)** - Deployment guide
- **[Risk Management](docs/RISK.md)** - Risk control strategies

## 🎓 Examples

### Example 1: Simple Buy/Sell

```python
from trading.hyperliquid_adapter import HyperliquidAdapter

hl = HyperliquidAdapter(testnet=True)
hl.connect()

# Buy 0.01 BTC at $40,000
hl.place_order(
    coin="BTC",
    is_buy=True,
    size=0.01,
    limit_price=40000
)

# Check position
positions = hl.get_positions()
print(f"BTC Position: {positions[0].size} @ ${positions[0].entry_price}")

# Close position
hl.close_position(coin="BTC")
```

### Example 2: Momentum Strategy

```python
from strategies import MomentumStrategy
from api.strategy import StrategyConfig

# Configure
config = StrategyConfig(
    name="CryptoMomentum",
    symbols=['BTC', 'ETH', 'SOL', 'AVAX'],
    parameters={
        'lookback_period': 20,
        'holding_period': 5
    },
    max_position_pct=0.20  # 20% max per coin
)

# Run strategy
strategy = MomentumStrategy(config)
strategy.start()

# Monitor
while True:
    metrics = strategy.get_metrics()
    print(f"Win Rate: {metrics.win_rate:.1%}")
    print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
    time.sleep(3600)  # Check hourly
```

### Example 3: With Notifications

```python
from notifications import MultiChannelNotifier, Notification
from trading.hyperliquid_adapter import HyperliquidAdapter

# Setup notifications
notifier = MultiChannelNotifier()

# Trade
hl = HyperliquidAdapter()
hl.connect()

response = hl.place_market_order("ETH", True, 0.1)

# Notify
notifier.send(Notification(
    title="Trade Executed",
    message=f"Bought 0.1 ETH at market",
    priority="normal"
))
```

## 🛠️ Available Strategies

| Strategy | Type | Best For | Risk | Complexity |
|----------|------|----------|------|------------|
| **Momentum** | Trend Following | Trending markets | Medium | Low |
| **Dual Momentum** | Absolute + Relative | Medium-term trends | Medium | Low |
| **Mean Reversion** | Counter-trend | Range-bound markets | Medium | Low |
| **Pairs Trading** | Market Neutral | Correlation plays | Low | Medium |
| **ML Prediction** | AI/ML | Complex patterns | High | High |
| **Ensemble ML** | Multi-model | Robust predictions | Medium | High |
| **Breakout** | Momentum | Volatile markets | High | Medium |
| **Trend Following** | MA Crossover | Clear trends | Medium | Low |

See [Strategy Library](strategies/README.md) for detailed documentation.

## 📊 Performance Monitoring

### Web Dashboard

```bash
# Start dashboard
python webapp/app.py

# Access at http://localhost:5000
# Default login: admin / quanttrader2024
```

Features:
- Real-time P&L tracking
- Position monitoring
- Trade history
- Risk metrics
- Performance analytics

### REST API

```bash
# Start API server
python api_server.py

# API docs at http://localhost:8000/docs
```

Endpoints:
- `POST /orders` - Place orders
- `GET /positions` - Get positions
- `GET /portfolio` - Portfolio summary
- `GET /market/quote/{symbol}` - Market data
- `GET /analytics/performance` - Performance metrics

### CLI Monitoring

```bash
# Real-time positions
python -c "
from trading.hyperliquid_adapter import HyperliquidAdapter
hl = HyperliquidAdapter()
hl.connect()
for pos in hl.get_positions():
    print(f'{pos.coin}: {pos.unrealized_pnl:+.2f} USDC')
"
```

## 🔐 Security Best Practices

### 1. Use API Wallets
```python
# ✅ Good: API wallet (cannot withdraw)
HYPERLIQUID_PRIVATE_KEY=0xAPI_WALLET_KEY

# ❌ Bad: Main wallet (can withdraw everything)
HYPERLIQUID_PRIVATE_KEY=0xMAIN_WALLET_KEY
```

### 2. Start with Testnet
```python
# Always test first!
hl = HyperliquidAdapter(testnet=True)  # ✅
# hl = HyperliquidAdapter(testnet=False)  # Only when ready
```

### 3. Limit Capital
```python
# Start small
INITIAL_CAPITAL=1000  # $1,000 USDC

# Not this
# INITIAL_CAPITAL=100000  # Too much for testing
```

### 4. Use Stop Losses
```python
# Always set max loss
config.max_daily_loss_pct = 0.02  # 2% max daily loss
config.max_position_pct = 0.10     # 10% max per position
```

### 5. Monitor Leverage
```python
# Check leverage regularly
state = hl.get_account_state()
leverage = state['marginSummary']['totalNtlPos'] / state['marginSummary']['accountValue']

if leverage > 5:
    print("⚠️ High leverage detected!")
```

## ⚠️ Risk Disclaimer

**IMPORTANT**: Trading crypto perpetual futures is extremely risky:

- ❌ You can lose MORE than your initial investment
- ❌ High leverage amplifies losses
- ❌ Funding rates can be expensive
- ❌ Liquidations can happen instantly
- ❌ Past performance ≠ future results

**Never trade with money you can't afford to lose.**

This software is provided "as is" without warranty. The developers are not responsible for any financial losses.

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

```bash
# Fork the repository
# Create a feature branch
git checkout -b feature/amazing-feature

# Make changes and test
pytest tests/

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# Create Pull Request
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **Hyperliquid Team** - For the excellent DEX and SDK
- **Community Contributors** - For feedback and improvements
- **Research Papers** - Academic foundations for strategies

## 📞 Support

- **Documentation**: [docs/](docs/)
- **GitHub Issues**: [Issues](https://github.com/yourusername/ShopGuard/issues)
- **Discord**: [Join Server](https://discord.gg/shopguard)
- **Email**: support@shopguard.trading

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/ShopGuard&type=Date)](https://star-history.com/#yourusername/ShopGuard&Date)

---

**Made with ❤️ for the crypto trading community**

**⚡ Start trading smarter with ShopGuard**
