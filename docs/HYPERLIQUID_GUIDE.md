# Hyperliquid Trading Guide

Complete guide to trading crypto perpetual futures on Hyperliquid using ShopGuard.

## Table of Contents

1. [What is Hyperliquid?](#what-is-hyperliquid)
2. [Getting Started](#getting-started)
3. [Account Setup](#account-setup)
4. [Basic Trading](#basic-trading)
5. [Advanced Features](#advanced-features)
6. [Risk Management](#risk-management)
7. [Common Issues](#common-issues)

## What is Hyperliquid?

Hyperliquid is a **decentralized perpetual futures exchange** that offers:

- **Perpetual Futures**: Trade crypto with leverage (up to 50x)
- **On-chain Settlement**: All trades settled on L1 blockchain
- **No KYC**: Trade directly from your wallet
- **Low Fees**: Competitive maker/taker fees
- **High Liquidity**: Deep order books
- **API Wallets**: Secure delegation for bots

### Key Features

| Feature | Description |
|---------|-------------|
| **Assets** | BTC, ETH, SOL, AVAX, and 100+ crypto perpetuals |
| **Leverage** | 1x to 50x (cross or isolated margin) |
| **Order Types** | Limit, Market, Stop-Market, Stop-Limit, TWAP |
| **Funding** | 8-hour funding rate cycles |
| **Minimum** | No minimum deposit |
| **API** | Full REST + WebSocket API |

## Getting Started

### Prerequisites

1. **Python 3.10+** installed
2. **Ethereum wallet** (MetaMask, Ledger, etc.)
3. **USDC** for trading (on Arbitrum network)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/ShopGuard.git
cd ShopGuard

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
```

### Quick Test

```bash
# Run crypto quick start (testnet)
python crypto_quick_start.py
```

This will:
- ✅ Check your setup
- ✅ Connect to Hyperliquid testnet
- ✅ Show market data
- ✅ Display account info (if configured)

## Account Setup

### Option 1: Read-Only Mode (Market Data Only)

No credentials needed! Just use the adapter:

```python
from trading.hyperliquid_adapter import HyperliquidAdapter

# Read-only connection
hl = HyperliquidAdapter(testnet=True)
hl.connect()

# Get market data
btc_price = hl.get_market_price("BTC")
print(f"BTC: ${btc_price:,.2f}")
```

### Option 2: Trading with Private Key

⚠️ **Start with TESTNET first!**

1. **Get Testnet Funds**:
   - Visit [Hyperliquid Testnet](https://app.hyperliquid.xyz/)
   - Switch to testnet network
   - Request testnet USDC from faucet

2. **Export Private Key**:
   - From MetaMask: Account → Export Private Key
   - ⚠️ **Never share your private key!**

3. **Configure `.env`**:
   ```bash
   HYPERLIQUID_PRIVATE_KEY=0x1234...  # Your private key
   HYPERLIQUID_TESTNET=true           # Use testnet
   ```

4. **Test Connection**:
   ```bash
   python crypto_quick_start.py
   ```

### Option 3: API Wallet (Recommended for Bots)

API wallets provide **secure delegation** - they can trade but **cannot withdraw**.

1. **Create API Wallet** (in app):
   - Go to app.hyperliquid.xyz
   - Settings → API → Create API Wallet
   - Copy the private key

2. **Use API Wallet**:
   ```python
   hl = HyperliquidAdapter(
       private_key="0xAPI_WALLET_KEY",
       testnet=True
   )
   ```

Benefits:
- ✅ Cannot withdraw funds
- ✅ Can be revoked instantly
- ✅ Separate from main wallet
- ✅ Perfect for automated trading

## Basic Trading

### Place a Limit Order

```python
from trading.hyperliquid_adapter import HyperliquidAdapter

hl = HyperliquidAdapter(testnet=True)
hl.connect()

# Buy 0.01 BTC at $40,000
response = hl.place_order(
    coin="BTC",
    is_buy=True,
    size=0.01,
    limit_price=40000,
    order_type="limit"
)

print(f"Order placed: {response}")
```

### Place a Market Order

```python
# Buy 0.01 BTC at market price (with 1% slippage protection)
response = hl.place_market_order(
    coin="BTC",
    is_buy=True,
    size=0.01,
    slippage_tolerance=0.01  # 1%
)
```

### Check Positions

```python
# Get all open positions
positions = hl.get_positions()

for pos in positions:
    print(f"{pos.coin}: {pos.side.upper()}")
    print(f"  Size: {pos.size}")
    print(f"  Entry: ${pos.entry_price:,.2f}")
    print(f"  PnL: ${pos.unrealized_pnl:,.2f}")
    print(f"  Leverage: {pos.leverage}x")
```

### Close a Position

```python
# Close entire BTC position at market
hl.close_position(coin="BTC")

# Or close at specific limit price
hl.close_position(coin="BTC", close_price=41000)
```

## Advanced Features

### Set Leverage

```python
# Set 5x leverage for BTC (cross margin)
hl.update_leverage(
    coin="BTC",
    leverage=5,
    is_cross=True  # True = cross margin, False = isolated
)
```

**Leverage Guidelines:**
- **1-3x**: Conservative, lower liquidation risk
- **5-10x**: Moderate, balanced risk/reward
- **10-20x**: Aggressive, higher risk
- **20-50x**: Very risky, only for experts

### Post-Only Orders (Maker Only)

```python
# Place maker-only order (earns rebates)
hl.place_order(
    coin="ETH",
    is_buy=True,
    size=0.1,
    limit_price=2000,
    post_only=True  # Will not take liquidity
)
```

### Reduce-Only Orders

```python
# Only reduce existing position (can't increase)
hl.place_order(
    coin="BTC",
    is_buy=False,
    size=0.01,
    limit_price=41000,
    reduce_only=True  # Safety: won't open new position
)
```

### Cancel Orders

```python
# Cancel specific order
hl.cancel_order(coin="BTC", order_id=12345)

# Cancel all orders for BTC
hl.cancel_all_orders(coin="BTC")

# Cancel all orders (all symbols)
hl.cancel_all_orders()
```

### Get Funding Rates

```python
# Check funding rate
funding = hl.get_funding_rate("BTC")
print(f"BTC Funding: {funding*100:.4f}% per 8h")

# Annualized funding rate
annual_funding = funding * 3 * 365
print(f"Annualized: {annual_funding*100:.2f}%")
```

**Funding Rate Tips:**
- Positive funding = Longs pay shorts
- Negative funding = Shorts pay longs
- Paid every 8 hours
- Use for arbitrage opportunities

## Risk Management

### 1. Position Sizing

```python
# Calculate safe position size
account = hl.get_account_state()
account_value = account['marginSummary']['accountValue']

# Risk 2% per trade
risk_pct = 0.02
risk_amount = account_value * risk_pct

# With 10% stop loss
stop_loss_pct = 0.10
position_size = risk_amount / stop_loss_pct

print(f"Safe position size: ${position_size:,.2f}")
```

### 2. Stop Losses

```python
# Manual stop loss implementation
def check_stop_loss(entry_price, current_price, stop_pct=0.05):
    """Check if stop loss hit"""
    loss_pct = (current_price - entry_price) / entry_price
    return loss_pct <= -stop_pct

# In trading loop
positions = hl.get_positions()
for pos in positions:
    current_price = hl.get_market_price(pos.coin)

    if check_stop_loss(pos.entry_price, current_price, stop_pct=0.05):
        print(f"Stop loss hit for {pos.coin}!")
        hl.close_position(pos.coin)
```

### 3. Diversification

```python
# Trade multiple uncorrelated assets
watchlist = [
    "BTC",   # Bitcoin
    "ETH",   # Ethereum
    "SOL",   # Solana
    "AVAX",  # Avalanche
    "ATOM"   # Cosmos
]

# Limit per position
max_position_pct = 0.20  # 20% max per asset
```

### 4. Monitoring

```python
# Check account health
state = hl.get_account_state()
margin_summary = state['marginSummary']

leverage = margin_summary['totalNtlPos'] / margin_summary['accountValue']
print(f"Account Leverage: {leverage:.2f}x")

margin_ratio = margin_summary['totalMarginUsed'] / margin_summary['accountValue']
print(f"Margin Usage: {margin_ratio*100:.1f}%")

# Alert if leverage too high
if leverage > 10:
    print("⚠️ WARNING: High leverage!")
```

## Using with Strategies

### Example: Momentum Strategy on Crypto

```python
from strategies import MomentumStrategy
from api.strategy import StrategyConfig

# Configure for crypto markets
config = StrategyConfig(
    name="CryptoMomentum",
    symbols=['BTC', 'ETH', 'SOL', 'AVAX', 'ATOM'],
    parameters={
        'lookback_period': 20,
        'holding_period': 5,
        'momentum_threshold': 0.03  # 3% minimum momentum
    },
    max_position_pct=0.15,  # 15% max per position
    max_order_pct=0.10       # 10% max per order
)

# Create strategy
strategy = MomentumStrategy(config)

# Start trading
strategy.start()
```

### Example: Mean Reversion

```python
from strategies import MeanReversionStrategy
from strategies.mean_reversion import MeanReversionConfig

config = MeanReversionConfig(
    name="CryptoMeanReversion",
    symbols=['BTC', 'ETH'],
    lookback_period=20,
    entry_threshold=2.0,  # 2 std devs
    exit_threshold=0.5,
    max_holding_period=10
)

strategy = MeanReversionStrategy(config)
strategy.start()
```

## Common Issues

### Issue: "Exchange not initialized"

**Cause**: No private key provided.

**Solution**:
```python
# Make sure to provide private key
hl = HyperliquidAdapter(
    private_key=os.getenv('HYPERLIQUID_PRIVATE_KEY'),
    testnet=True
)
```

### Issue: "Order rejected - insufficient margin"

**Cause**: Not enough collateral for the order.

**Solutions**:
1. Reduce position size
2. Reduce leverage
3. Add more USDC to account
4. Close other positions to free up margin

### Issue: "Rate limited"

**Cause**: Too many API requests.

**Solution**:
```python
import time

# Add delays between requests
for symbol in symbols:
    data = hl.get_market_price(symbol)
    time.sleep(0.1)  # 100ms delay
```

### Issue: Orders not filling

**Causes**:
1. Limit price too far from market
2. Low liquidity
3. Post-only order in wrong direction

**Solutions**:
```python
# Use market orders for guaranteed fills
hl.place_market_order(coin="BTC", is_buy=True, size=0.01)

# Or use aggressive limit orders
market_price = hl.get_market_price("BTC")
aggressive_price = market_price * 1.001  # 0.1% above market
hl.place_order(coin="BTC", is_buy=True, size=0.01, limit_price=aggressive_price)
```

## Best Practices

### 1. Always Start with Testnet

```python
# TESTNET for testing
hl = HyperliquidAdapter(testnet=True)

# Only switch to mainnet when confident
# hl = HyperliquidAdapter(testnet=False)
```

### 2. Use API Wallets for Bots

- ✅ Create dedicated API wallet
- ✅ Fund with limited capital
- ✅ Revoke if compromised
- ❌ Never use main wallet for automated trading

### 3. Implement Circuit Breakers

```python
MAX_DAILY_LOSS = 1000  # USDC
daily_pnl = -500

if daily_pnl < -MAX_DAILY_LOSS:
    print("Circuit breaker triggered!")
    # Close all positions
    positions = hl.get_positions()
    for pos in positions:
        hl.close_position(pos.coin)
    # Stop trading
    exit()
```

### 4. Monitor Funding Rates

```python
# Check funding before holding overnight
funding = hl.get_funding_rate("BTC")

# If funding is expensive, consider closing
if abs(funding) > 0.01:  # 1% per 8h = expensive
    print(f"Warning: High funding rate: {funding*100:.2f}%")
```

### 5. Diversify Across Assets

Don't put all capital in one trade:
```python
num_positions = 5
capital_per_position = total_capital / num_positions
```

## Resources

- **Hyperliquid Docs**: https://hyperliquid.gitbook.io/hyperliquid-docs
- **Hyperliquid App**: https://app.hyperliquid.xyz/
- **Python SDK**: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- **Discord**: https://discord.gg/hyperliquid
- **Twitter**: https://twitter.com/HyperliquidX

## Support

For issues specific to ShopGuard:
- GitHub Issues: https://github.com/yourusername/ShopGuard/issues
- Email: support@shopguard.trading

For Hyperliquid platform issues:
- Discord: https://discord.gg/hyperliquid
- Support: support@hyperliquid.xyz

---

**⚠️ Risk Disclaimer**: Trading crypto perpetual futures is extremely risky. Never trade with money you can't afford to lose. Past performance does not guarantee future results. This is not financial advice.
