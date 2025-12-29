"""
Trading Teacher
===============
Comprehensive trading education system that teaches
everything the AI knows about markets and trading.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class LessonCategory(Enum):
    """Categories of trading lessons"""
    BASICS = "basics"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    RISK = "risk"
    PSYCHOLOGY = "psychology"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    STRATEGIES = "strategies"
    ADVANCED = "advanced"


@dataclass
class Lesson:
    """A single educational lesson"""
    id: str
    title: str
    category: LessonCategory
    difficulty: str  # beginner, intermediate, advanced
    content: str
    key_takeaways: List[str]
    quiz_questions: List[Dict] = field(default_factory=list)
    related_lessons: List[str] = field(default_factory=list)


class TradingTeacher:
    """
    Complete trading education system
    Teaches everything from basics to advanced strategies
    """

    def __init__(self):
        self.lessons = self._build_curriculum()
        self.user_progress = {}

    def _build_curriculum(self) -> Dict[str, Lesson]:
        """Build the complete curriculum"""
        lessons = {}

        # ========== BASICS ==========
        lessons["basics_01"] = Lesson(
            id="basics_01",
            title="What is Trading?",
            category=LessonCategory.BASICS,
            difficulty="beginner",
            content="""
# What is Trading?

Trading is the act of buying and selling financial assets (stocks, crypto, forex, etc.)
with the goal of making a profit from price movements.

## Types of Trading

### 1. Day Trading
- Opening and closing positions within the same day
- No overnight risk
- Requires active monitoring
- Timeframe: Minutes to hours

### 2. Swing Trading
- Holding positions for days to weeks
- Captures larger price swings
- Less time-intensive than day trading
- Timeframe: Days to weeks

### 3. Position Trading / Investing
- Holding for months to years
- Based on long-term fundamentals
- Minimal active management
- Timeframe: Months to years

### 4. Scalping
- Very short-term trades
- Small profits, many trades
- Requires fast execution
- Timeframe: Seconds to minutes

## Key Concepts

**Long Position**: Buying an asset expecting price to rise
**Short Position**: Selling/betting against an asset expecting price to fall

**Entry**: The price at which you open a position
**Exit**: The price at which you close a position

**Profit**: Exit > Entry (for longs), Entry > Exit (for shorts)
**Loss**: Entry > Exit (for longs), Exit > Entry (for shorts)

## Important Truth

Most traders lose money. Studies show:
- 80-90% of day traders lose money
- Successful trading requires education, discipline, and risk management
- Never trade with money you can't afford to lose
""",
            key_takeaways=[
                "Trading involves buying/selling assets for profit",
                "Different timeframes suit different lifestyles",
                "Most traders lose money - education is crucial",
                "Always manage risk carefully"
            ],
            related_lessons=["basics_02", "risk_01"]
        )

        lessons["basics_02"] = Lesson(
            id="basics_02",
            title="Understanding Market Orders",
            category=LessonCategory.BASICS,
            difficulty="beginner",
            content="""
# Understanding Market Orders

Orders are instructions you give to buy or sell assets.
Different order types serve different purposes.

## Order Types

### Market Order
Executes immediately at the best available price.

**Pros:**
- Guaranteed execution
- Fast

**Cons:**
- Price may differ from expected (slippage)
- Bad for illiquid assets

**Use when:** You need to enter/exit immediately

### Limit Order
Executes only at your specified price or better.

**Pros:**
- Control over execution price
- No slippage

**Cons:**
- May not fill if price doesn't reach limit
- Can miss moves

**Use when:** You want a specific price

### Stop Loss Order
Automatically sells if price falls to a certain level.

**Example:**
- Buy at $100
- Set stop loss at $97
- If price drops to $97, position automatically closes
- Maximum loss = 3%

**This is your safety net. ALWAYS use stop losses.**

### Take Profit Order
Automatically sells when price reaches your target.

**Example:**
- Buy at $100
- Set take profit at $106
- If price rises to $106, position automatically closes
- Locks in 6% profit

### Stop Limit Order
Combination of stop and limit order.

When stop price is triggered, a limit order is placed.
Risk: May not execute in fast-moving markets.

## Order Execution

**Bid**: Highest price buyers will pay
**Ask**: Lowest price sellers will accept
**Spread**: Difference between bid and ask

Narrow spread = liquid market (good)
Wide spread = illiquid market (be careful)
""",
            key_takeaways=[
                "Market orders execute immediately but may slip",
                "Limit orders give price control but may not fill",
                "ALWAYS use stop losses to limit risk",
                "Take profits to lock in gains"
            ],
            related_lessons=["basics_01", "risk_02"]
        )

        # ========== TECHNICAL ANALYSIS ==========
        lessons["tech_01"] = Lesson(
            id="tech_01",
            title="Introduction to Charts",
            category=LessonCategory.TECHNICAL,
            difficulty="beginner",
            content="""
# Introduction to Charts

Charts are visual representations of price movement over time.
Learning to read charts is fundamental to trading.

## Chart Types

### 1. Line Chart
- Simplest chart
- Connects closing prices
- Good for seeing overall trend
- Misses intraday information

### 2. Bar Chart (OHLC)
Each bar shows:
- Open: Where price started
- High: Highest price reached
- Low: Lowest price reached
- Close: Where price ended

### 3. Candlestick Chart (Most Popular)
Same info as bar chart but more visual.

**Green/White Candle**: Close > Open (price went up)
**Red/Black Candle**: Close < Open (price went down)

**Body**: Thick part (open to close range)
**Wicks/Shadows**: Thin lines (high and low)

## Timeframes

Charts can show different time periods:
- 1 minute (1m): Each candle = 1 minute of trading
- 5 minutes (5m): Scalping and day trading
- 15 minutes (15m): Day trading
- 1 hour (1h): Swing trading
- 4 hours (4h): Swing trading
- 1 day (1D): Position trading
- 1 week (1W): Long-term investing

**Rule**: Analyze higher timeframes first, then zoom in.

## Support and Resistance

**Support**: Price level where buying pressure is strong
- Floor that price bounces off
- Buyers defend this level

**Resistance**: Price level where selling pressure is strong
- Ceiling that price gets rejected from
- Sellers defend this level

**Breakout**: When price moves through support/resistance
- Resistance breaks → Bullish
- Support breaks → Bearish
""",
            key_takeaways=[
                "Candlestick charts show open, high, low, close",
                "Green candles = price went up, Red = down",
                "Always check multiple timeframes",
                "Support is the floor, Resistance is the ceiling"
            ],
            related_lessons=["tech_02", "tech_03"]
        )

        lessons["tech_02"] = Lesson(
            id="tech_02",
            title="Moving Averages Explained",
            category=LessonCategory.TECHNICAL,
            difficulty="intermediate",
            content="""
# Moving Averages

Moving averages smooth out price data to show the underlying trend.
They're among the most important technical indicators.

## Simple Moving Average (SMA)

Average of the last N prices.

**SMA 20** = Average of last 20 closing prices

Formula: SMA = (P1 + P2 + ... + PN) / N

Common periods:
- SMA 20: Short-term trend
- SMA 50: Medium-term trend
- SMA 200: Long-term trend

## Exponential Moving Average (EMA)

Gives more weight to recent prices.
Reacts faster to price changes than SMA.

Common EMAs:
- EMA 9: Very short-term
- EMA 12 & 26: Used in MACD
- EMA 21: Popular for swing trading

## How to Use Moving Averages

### 1. Trend Identification
- Price ABOVE MA = Uptrend
- Price BELOW MA = Downtrend

### 2. Dynamic Support/Resistance
- In uptrends, MA acts as support (price bounces off)
- In downtrends, MA acts as resistance

### 3. Crossovers

**Golden Cross**: Short MA crosses ABOVE long MA
→ Bullish signal

**Death Cross**: Short MA crosses BELOW long MA
→ Bearish signal

Example: 50 SMA crossing above 200 SMA = Golden Cross (bullish)

## Trading Strategy Example

Simple MA Trend Following:
1. Use 20 EMA and 50 SMA
2. Buy when: Price > 20 EMA > 50 SMA
3. Sell when: Price < 20 EMA < 50 SMA
4. Use previous swing low as stop loss

## Limitations

- Lagging indicator (based on past prices)
- Doesn't work well in choppy/sideways markets
- No price targets
""",
            key_takeaways=[
                "SMA is simple average, EMA weights recent prices more",
                "Price above MA = uptrend, below = downtrend",
                "MAs act as dynamic support/resistance",
                "Golden Cross is bullish, Death Cross is bearish"
            ],
            related_lessons=["tech_01", "tech_03", "tech_04"]
        )

        # ========== RISK MANAGEMENT ==========
        lessons["risk_01"] = Lesson(
            id="risk_01",
            title="Position Sizing - The Most Important Skill",
            category=LessonCategory.RISK,
            difficulty="beginner",
            content="""
# Position Sizing - The Most Important Skill

Position sizing is MORE IMPORTANT than your entry strategy.
It determines how much you risk on each trade.

## The 1-2% Rule

**Never risk more than 1-2% of your portfolio on a single trade.**

With $100 portfolio:
- 1% risk = $1 maximum loss per trade
- 2% risk = $2 maximum loss per trade

## Calculating Position Size

Position Size = Risk Amount / Stop Loss Distance

### Example:
- Portfolio: $100
- Risk per trade: 2% ($2)
- Asset price: $50
- Stop loss: 4% below entry ($48)

Calculation:
- Stop loss distance = $50 - $48 = $2 per share
- Position size = $2 (risk) / $2 (SL distance) = 1 share
- Position value = $50

## Why This Matters

### Scenario A: Risking 10% per trade
10 losing trades = 65% drawdown
Need 186% gain to recover!

### Scenario B: Risking 2% per trade
10 losing trades = 18% drawdown
Need only 22% to recover

## The Kelly Criterion

Mathematical formula for optimal bet sizing:

Kelly % = W - [(1-W) / R]

Where:
- W = Win rate (e.g., 0.55 = 55%)
- R = Win/Loss ratio (e.g., 2 = gains are 2x losses)

Example:
- Win rate: 55%
- Win/Loss ratio: 2
- Kelly = 0.55 - (0.45/2) = 0.55 - 0.225 = 32.5%

**IMPORTANT**: Use HALF-KELLY or less for safety!
Full Kelly is too aggressive for most traders.

## Position Sizing Rules

1. Never risk more than 2% per trade
2. Never have more than 6% total risk at once
3. Reduce size in losing streaks
4. Increase size (slightly) in winning streaks
5. Smaller size in volatile markets
""",
            key_takeaways=[
                "Never risk more than 1-2% per trade",
                "Position size is calculated from risk, not hope",
                "Small consistent losses are manageable; big losses are devastating",
                "Use Kelly Criterion divided by 2 for optimal sizing"
            ],
            related_lessons=["risk_02", "risk_03"]
        )

        # ========== PSYCHOLOGY ==========
        lessons["psych_01"] = Lesson(
            id="psych_01",
            title="Trading Psychology - Master Your Emotions",
            category=LessonCategory.PSYCHOLOGY,
            difficulty="intermediate",
            content="""
# Trading Psychology - Master Your Emotions

Psychology is the biggest factor in trading success.
Your emotions are your biggest enemy.

## The Two Enemies

### 1. Fear
- Fear of losing money
- Fear of missing out (FOMO)
- Fear of being wrong

Fear causes:
- Selling too early
- Not taking valid setups
- Moving stops to avoid loss

### 2. Greed
- Wanting more profit
- Overtrading
- Taking excessive risk

Greed causes:
- Holding too long
- Not taking profits
- Overleveraging

## Common Psychological Traps

### FOMO (Fear of Missing Out)
Seeing price rise and jumping in without analysis.

**Solution**: If you missed the move, wait for the next setup.
There's always another trade.

### Revenge Trading
After a loss, trading aggressively to "win it back."

**Solution**: After a loss, take a break.
Never increase size after losing.

### Confirmation Bias
Only seeing information that supports your position.

**Solution**: Actively look for reasons you might be wrong.

### Overconfidence
Winning streak leads to excessive risk-taking.

**Solution**: Stick to your rules regardless of recent results.

## Building Mental Discipline

### 1. Have a Trading Plan
- Entry criteria
- Exit criteria
- Position size rules
- Maximum daily loss

### 2. Keep a Trading Journal
Record every trade:
- Entry/exit reasons
- Emotional state
- What you learned

### 3. Accept Losses as Part of Trading
Even the best traders lose 40-50% of trades.
Focus on the process, not individual results.

### 4. Set Rules and Follow Them
- Daily loss limit: Stop trading if down 3%
- Maximum positions: Never more than 3-5 open
- Required setup: Only trade when criteria met

## The Profitable Mindset

"I don't need to be right. I need to follow my system."

Trading is:
- A probability game
- About edge over many trades
- Process over outcome
- Discipline over emotion
""",
            key_takeaways=[
                "Fear and greed are your biggest enemies",
                "FOMO causes buying at the top",
                "Revenge trading after losses makes things worse",
                "Have a plan, follow rules, keep a journal"
            ],
            related_lessons=["psych_02", "risk_01"]
        )

        # ========== CRYPTO SPECIFIC ==========
        lessons["crypto_01"] = Lesson(
            id="crypto_01",
            title="Crypto Trading Fundamentals",
            category=LessonCategory.CRYPTO,
            difficulty="beginner",
            content="""
# Crypto Trading Fundamentals

Cryptocurrency markets have unique characteristics
that differ from traditional markets.

## Crypto Market Characteristics

### 1. 24/7 Markets
- Never closes
- No opening gaps
- Can be exhausting to monitor

### 2. High Volatility
- 10-20% daily moves are normal
- Much higher than stocks
- Greater opportunity AND risk

### 3. Correlation
- Most altcoins follow Bitcoin
- BTC dumps → Everything dumps
- Always watch BTC regardless of what you trade

### 4. Market Cycles
- Bull markets: Everything goes up
- Bear markets: 80-90% drawdowns normal
- Cycle typically 4 years (Bitcoin halving)

## Key Crypto Concepts

### Market Cap
Market Cap = Price × Circulating Supply

Categories:
- Large cap ($10B+): BTC, ETH - safer
- Mid cap ($1-10B): More volatile
- Small cap (<$1B): Very risky
- Micro cap (<$100M): Extreme risk

### Tokenomics
Study of token economics:
- Total supply
- Circulating supply
- Inflation/emission schedule
- Burn mechanisms

### On-Chain Analysis
Analyzing blockchain data:
- Active addresses
- Transaction volume
- Exchange flows
- Whale movements

## Bitcoin Halving

Every ~4 years, Bitcoin mining reward halves.
Reduces new supply → Historically bullish.

Past halvings (2012, 2016, 2020) preceded bull markets.
Next halving: ~2024

## Common Crypto Trading Mistakes

1. Trading altcoins without watching BTC
2. Ignoring tokenomics (unlimited supply coins)
3. Trading small caps with large positions
4. Not taking profits in bull markets
5. Buying at all-time highs from FOMO

## Crypto Risk Management

- Smaller position sizes due to volatility
- Wider stop losses (normal swings are big)
- Don't use leverage (or very small)
- Take profits regularly
- Never invest more than you can lose
""",
            key_takeaways=[
                "Crypto trades 24/7 with high volatility",
                "Most altcoins follow Bitcoin",
                "Understand tokenomics before trading",
                "Use smaller positions due to volatility"
            ],
            related_lessons=["crypto_02", "risk_01"]
        )

        # ========== STRATEGIES ==========
        lessons["strat_01"] = Lesson(
            id="strat_01",
            title="Swing Trading Strategy",
            category=LessonCategory.STRATEGIES,
            difficulty="intermediate",
            content="""
# Swing Trading Strategy

Swing trading captures multi-day price movements.
Ideal timeframe for most traders.

## Why Swing Trading?

### Advantages
- Don't need to watch charts all day
- Larger moves = larger profits per trade
- Less noise than day trading
- Works with a job/life

### Disadvantages
- Overnight risk
- Requires patience
- Fewer trades

## The Swing Trading Setup

### Step 1: Identify the Trend (Daily Chart)
- Price above 50 SMA = Uptrend → Look for BUYS
- Price below 50 SMA = Downtrend → Look for SELLS
- Sideways = No trade or range strategies

### Step 2: Wait for Pullback (4H Chart)
In uptrend: Wait for price to pull back to support
In downtrend: Wait for price to rally to resistance

### Step 3: Entry Confirmation
Look for:
- RSI oversold (<35) in uptrend
- Price touching key support
- Bullish candlestick pattern

### Step 4: Entry and Risk Management
- Entry: After confirmation
- Stop Loss: Below recent swing low
- Take Profit: Previous high or 2:1 R:R

## Example Trade

**Setup:**
- Daily: Price above 50 SMA (uptrend)
- 4H: Price pulled back to 20 EMA
- RSI: 38 (approaching oversold)
- Pattern: Bullish engulfing candle

**Execution:**
- Entry: $100
- Stop Loss: $96 (4% risk)
- Target: $108 (8% gain)
- Risk/Reward: 1:2

**Position Size (with $100 portfolio, 2% risk):**
- Risk amount: $2
- Stop distance: $4
- Position: $2 / $4 = 0.5 shares
- Position value: $50

## Rules for Success

1. Only trade with the trend
2. Wait for pullbacks (don't chase)
3. Require confirmation before entry
4. Always use stop loss
5. Target minimum 2:1 reward/risk
6. Be patient - good setups are worth waiting for
""",
            key_takeaways=[
                "Trade with the trend, enter on pullbacks",
                "Use daily chart for trend, 4H for entry",
                "Require confirmation before entering",
                "Target at least 2:1 reward to risk"
            ],
            related_lessons=["strat_02", "tech_02", "risk_01"]
        )

        # ========== FUNDAMENTAL ANALYSIS ==========
        lessons["fund_01"] = Lesson(
            id="fund_01",
            title="What is Fundamental Analysis?",
            category=LessonCategory.FUNDAMENTAL,
            difficulty="beginner",
            content="""
# What is Fundamental Analysis?

Fundamental analysis studies what drives an asset's true value.
While technical analysis looks at charts, fundamentals look at the WHY.

## Stocks: What to Analyze

### 1. Earnings (Most Important)
**EPS (Earnings Per Share)**: Profit divided by shares
- Growing EPS = Company becoming more profitable
- Declining EPS = Warning sign

**P/E Ratio (Price to Earnings)**
- P/E = Stock Price / EPS
- P/E of 20 means paying $20 for $1 of earnings
- High P/E = Expensive OR high growth expected
- Low P/E = Cheap OR problems expected

### 2. Revenue Growth
Is the company selling more each quarter?
- Revenue growth > 10%/year is good
- Negative growth is concerning

### 3. Profit Margins
How much profit per dollar of sales?
- Gross margin > 40% is healthy
- Operating margin > 15% is strong

### 4. Debt Levels
**Debt-to-Equity Ratio**
- Under 1 = Conservative
- Over 2 = Risky (too much debt)

## Crypto: What to Analyze

### 1. Utility
What problem does it solve?
- Real use case = Long-term value
- No use case = Speculation only

### 2. Tokenomics
- Total supply (capped vs infinite)
- Inflation rate
- Token burns

### 3. Adoption
- Daily active users
- Transaction volume
- Developer activity

### 4. Team & Backing
- Who created it?
- Major investors/partners?
- Track record?

## Combining with Technicals

Best approach: Use fundamentals to decide WHAT to trade,
use technicals to decide WHEN to trade.

1. Find fundamentally strong assets
2. Wait for technical entry signal
3. Manage risk properly
""",
            key_takeaways=[
                "Fundamentals answer WHY an asset should move",
                "For stocks: earnings, revenue, and debt matter most",
                "For crypto: utility, tokenomics, and adoption",
                "Combine fundamentals (what) with technicals (when)"
            ],
            related_lessons=["fund_02", "tech_01"]
        )

        lessons["fund_02"] = Lesson(
            id="fund_02",
            title="Reading Financial Statements",
            category=LessonCategory.FUNDAMENTAL,
            difficulty="intermediate",
            content="""
# Reading Financial Statements

Every public company releases quarterly financial statements.
Here's how to read them quickly.

## The Three Statements

### 1. Income Statement (Profit & Loss)
Shows revenue and expenses over a period.

**Key Lines:**
- Revenue (Sales): Total money coming in
- Gross Profit: Revenue - Cost of goods
- Operating Income: Profit from main business
- Net Income: Final profit after everything

**What to Look For:**
- Revenue growing quarter over quarter
- Profit margins stable or improving
- Net income positive and growing

### 2. Balance Sheet
Snapshot of what company owns and owes.

**Assets** (What they own):
- Cash & equivalents
- Inventory
- Property & equipment

**Liabilities** (What they owe):
- Short-term debt
- Long-term debt
- Accounts payable

**Equity** = Assets - Liabilities

**What to Look For:**
- Cash increasing
- Debt under control
- Equity growing

### 3. Cash Flow Statement
Where cash actually goes.

**Operating Cash Flow**: Cash from business
**Investing Cash Flow**: Buying/selling assets
**Financing Cash Flow**: Debt/equity transactions

**Free Cash Flow** = Operating - Capital Expenditures
This is the real money available.

## Quick Analysis Checklist

For any stock, check:
1. Revenue growth (>10% good)
2. Profit margins (stable/improving)
3. Debt/Equity ratio (<1 safe)
4. Free cash flow (positive)
5. EPS growth (>15% excellent)

## Where to Find This Data

- Company investor relations page
- SEC EDGAR (official filings)
- Yahoo Finance / Google Finance
- Seeking Alpha
""",
            key_takeaways=[
                "Income statement shows profitability",
                "Balance sheet shows financial health",
                "Cash flow shows real money movement",
                "Focus on trends, not single numbers"
            ],
            related_lessons=["fund_01", "stocks_01"]
        )

        # ========== STOCK SPECIFIC ==========
        lessons["stocks_01"] = Lesson(
            id="stocks_01",
            title="Stock Market Basics",
            category=LessonCategory.STOCKS,
            difficulty="beginner",
            content="""
# Stock Market Basics

Stocks represent ownership in companies.
Understanding the basics is essential.

## What is a Stock?

A stock (or share) is a piece of ownership in a company.

**Example:**
- Apple has ~16 billion shares outstanding
- Owning 100 shares = Tiny percentage of Apple
- You share in profits and growth

## Stock Market Hours

**US Markets:**
- Regular: 9:30 AM - 4:00 PM Eastern
- Pre-market: 4:00 AM - 9:30 AM
- After-hours: 4:00 PM - 8:00 PM

**Important Times:**
- 9:30-10:30 AM: High volatility (opening)
- 11:30-1:00 PM: Lunch lull (low volume)
- 3:00-4:00 PM: Power hour (closing moves)

## Types of Stocks

### By Size (Market Cap)
- **Large Cap** (>$10B): Apple, Microsoft, Google
  - More stable, lower risk
  - Good for beginners

- **Mid Cap** ($2-10B): Growing companies
  - More volatile
  - Higher growth potential

- **Small Cap** (<$2B): Smaller companies
  - Very volatile
  - Highest risk/reward

### By Sector
Technology, Healthcare, Finance, Energy, Consumer, etc.
Different sectors perform well in different economic conditions.

## Key Concepts

### Dividends
Some stocks pay quarterly cash to shareholders.
- Dividend Yield = Annual dividend / Stock price
- 2-4% yield is typical

### Stock Splits
Company divides shares to lower price.
- 4:1 split: 1 share at $400 becomes 4 at $100
- Total value unchanged

### Earnings Reports
Companies report quarterly (4x per year).
- Stock often moves 5-15% on earnings
- "Earnings season" is high volatility

## Starting with $100

With small capital, focus on:
1. **Fractional shares**: Buy $20 of expensive stocks
2. **ETFs**: Instant diversification (SPY, QQQ)
3. **1-2 positions max**: Don't over-diversify
4. **Learn first**: Use paper trading
""",
            key_takeaways=[
                "Stocks are ownership shares in companies",
                "Market hours are 9:30 AM - 4:00 PM Eastern",
                "Different cap sizes have different risk levels",
                "With $100, use fractional shares and focus on learning"
            ],
            related_lessons=["stocks_02", "basics_01"]
        )

        lessons["stocks_02"] = Lesson(
            id="stocks_02",
            title="Trading ETFs for Beginners",
            category=LessonCategory.STOCKS,
            difficulty="beginner",
            content="""
# Trading ETFs for Beginners

ETFs (Exchange-Traded Funds) are the best way to start.
They're baskets of stocks that trade like single stocks.

## Why ETFs for Beginners?

### 1. Instant Diversification
One ETF = Many stocks
- SPY holds 500 companies
- If one fails, others balance it out

### 2. Lower Risk
Can't go to zero (unlike single stocks)
Slower moves = Easier to manage

### 3. Lower Cost
No need to buy multiple stocks
Often lower fees than mutual funds

## Essential ETFs to Know

### Broad Market
- **SPY**: S&P 500 (500 largest US companies)
- **QQQ**: NASDAQ-100 (100 largest tech stocks)
- **IWM**: Russell 2000 (small caps)
- **VTI**: Total US stock market

### Sector ETFs
- **XLK**: Technology
- **XLF**: Financials
- **XLE**: Energy
- **XLV**: Healthcare

### Leveraged (ADVANCED - Be Careful!)
- **TQQQ**: 3x NASDAQ (triple the moves)
- **SQQQ**: -3x NASDAQ (inverse)
These are for SHORT-TERM only. They decay over time.

## Trading Strategy for $100

### Simple SPY/QQQ Strategy

1. **Trend Check** (Daily Chart)
   - Price above 20 EMA = Uptrend (look to buy)
   - Price below 20 EMA = Downtrend (stay out or short)

2. **Entry** (4H Chart)
   - Wait for pullback to 20 EMA in uptrend
   - RSI approaching 40 (not oversold yet)
   - Buy on bounce confirmation

3. **Position Size**
   - Risk 2% ($2 with $100 account)
   - Stop loss 2% below entry
   - Position = $100 (full account in one ETF is OK)

4. **Exit**
   - Stop loss if trade goes wrong
   - Take profit at 4%+ or when RSI > 70

### Why This Works

- SPY/QQQ trend most of the time
- Pullbacks in uptrends are buying opportunities
- Stops protect from crashes
- 2:1+ reward/risk builds account over time
""",
            key_takeaways=[
                "ETFs provide instant diversification",
                "SPY and QQQ are ideal for beginners",
                "Avoid leveraged ETFs until experienced",
                "Trade pullbacks in uptrends for best results"
            ],
            related_lessons=["stocks_01", "strat_01", "risk_01"]
        )

        # ========== ADVANCED ==========
        lessons["adv_01"] = Lesson(
            id="adv_01",
            title="Building Your Trading System",
            category=LessonCategory.ADVANCED,
            difficulty="advanced",
            content="""
# Building Your Trading System

A trading system removes emotion and creates consistency.
This is how professionals trade.

## What is a Trading System?

A complete set of rules that tells you:
1. WHAT to trade
2. WHEN to enter
3. WHEN to exit
4. HOW MUCH to risk

## System Components

### 1. Market Selection
Which assets will you trade?

For $100 account, focus on:
- 2-3 assets maximum
- Liquid markets (SPY, QQQ, BTC, ETH)
- Assets you understand

### 2. Entry Rules
Specific conditions that MUST be met.

**Example Entry Rules:**
1. Daily trend is up (price > 50 SMA)
2. 4H RSI is below 40
3. Price touches 20 EMA
4. Bullish candle forms
ALL conditions must be true = Entry

### 3. Exit Rules
When to close positions.

**Stop Loss Rules:**
- Maximum 3% from entry
- Below recent swing low
- Never move stop further from entry

**Take Profit Rules:**
- Minimum 2:1 reward/risk
- Scale out: 50% at 2:1, 50% at 3:1
- Trail stop after 2:1 reached

### 4. Position Sizing Rules
How much per trade.

- Risk 1-2% of account per trade
- Calculate position from stop distance
- Never exceed 3 open positions

## System Testing

Before trading real money:

### 1. Backtest
Look at historical charts.
Would your rules have worked?

### 2. Paper Trade
Trade your system with fake money.
Minimum 20 trades before going live.

### 3. Track Results
Win rate, average win, average loss.
Expectancy = (Win% × AvgWin) - (Loss% × AvgLoss)
Must be positive!

## Example System

**The Pullback Trend System**

Asset: SPY or QQQ
Timeframes: Daily (trend), 4H (entry)

Entry Rules:
1. Daily close > 20 EMA (uptrend)
2. 4H RSI crosses above 35 (was oversold)
3. 4H candle closes above previous candle high

Exit Rules:
- Stop: Below 4H swing low
- Target: 2x stop distance

Position Size:
- Risk 2% per trade

This is a complete, tradeable system.
""",
            key_takeaways=[
                "A system removes emotion from trading",
                "Must have entry, exit, and sizing rules",
                "Backtest and paper trade before real money",
                "Consistency beats perfection"
            ],
            related_lessons=["adv_02", "strat_01", "risk_01"]
        )

        lessons["adv_02"] = Lesson(
            id="adv_02",
            title="Trading Journal & Performance Analysis",
            category=LessonCategory.ADVANCED,
            difficulty="advanced",
            content="""
# Trading Journal & Performance Analysis

The difference between amateurs and professionals:
Professionals track everything.

## Why Keep a Trading Journal?

### 1. Find Your Leaks
Where are you losing money unnecessarily?
- Entries too early?
- Stops too tight?
- Not taking profits?

### 2. Improve Over Time
Can't improve what you don't measure.

### 3. Stay Disciplined
Writing forces you to follow rules.

## What to Record

### For Every Trade:

**Before Entry:**
- Date and time
- Asset and direction (long/short)
- Reason for entry (what rules were met?)
- Entry price, stop loss, target

**After Exit:**
- Exit price and date
- Result (win/loss, dollar amount, %)
- Did you follow your rules?
- What did you learn?

**Emotional State:**
- How did you feel entering?
- Any FOMO or fear?
- Were you patient or impulsive?

## Key Metrics to Track

### 1. Win Rate
Wins / Total Trades × 100

- 40-50% is normal for trend traders
- 60%+ requires small wins (scalping)

### 2. Risk/Reward Ratio
Average Win / Average Loss

- 2:1 minimum for trend trading
- 1.5:1 acceptable with 60%+ win rate

### 3. Expectancy
Expected profit per trade

Expectancy = (Win% × AvgWin) - (Loss% × AvgLoss)

**Example:**
- Win rate: 45%
- Average win: $6
- Average loss: $3

Expectancy = (0.45 × $6) - (0.55 × $3)
           = $2.70 - $1.65
           = $1.05 per trade

You expect to make $1.05 for every trade (on average).

### 4. Maximum Drawdown
Largest peak-to-trough decline.

- Under 10% = Excellent
- 10-20% = Acceptable
- Over 20% = Review your system

### 5. Profit Factor
Gross Wins / Gross Losses

- 1.5+ = Good system
- 2.0+ = Excellent system
- Under 1.0 = Losing system

## Weekly Review Process

Every weekend:

1. **List all trades**
2. **Calculate metrics**
3. **Identify patterns:**
   - Best performing setups
   - Worst performing setups
   - Time of day patterns
   - Emotional triggers
4. **Make ONE improvement**
   - Don't change everything at once
   - Small tweaks compound over time

## The Path to Consistency

Month 1-3: Focus on following rules
Month 4-6: Refine entries
Month 7-12: Optimize position sizing

Patience. This takes time.
""",
            key_takeaways=[
                "Track every trade with full details",
                "Calculate win rate, R:R, and expectancy",
                "Weekly reviews find patterns and leaks",
                "Improve one thing at a time"
            ],
            related_lessons=["adv_01", "psych_01"]
        )

        # ========== MORE TECHNICAL ==========
        lessons["tech_03"] = Lesson(
            id="tech_03",
            title="RSI - The Momentum Indicator",
            category=LessonCategory.TECHNICAL,
            difficulty="intermediate",
            content="""
# RSI - The Momentum Indicator

RSI (Relative Strength Index) measures momentum.
It's one of the most useful indicators.

## What is RSI?

RSI oscillates between 0 and 100.
It measures the speed and change of price movements.

**Formula** (calculated automatically):
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (over 14 periods)

## Key Levels

### Overbought: Above 70
- Price has risen quickly
- May be due for a pullback
- NOT a sell signal alone

### Oversold: Below 30
- Price has fallen quickly
- May be due for a bounce
- NOT a buy signal alone

### Neutral: 40-60
- No strong momentum either way

## How to Use RSI

### 1. Overbought/Oversold in Trends

**In Uptrends:**
- Oversold (RSI < 35) = Buying opportunity
- Overbought (RSI > 70) = Take some profit, don't short

**In Downtrends:**
- Overbought (RSI > 65) = Shorting opportunity
- Oversold (RSI < 30) = Cover shorts, don't buy

### 2. Divergences

**Bullish Divergence:**
Price makes lower low, RSI makes higher low.
→ Momentum weakening, potential reversal up

**Bearish Divergence:**
Price makes higher high, RSI makes lower high.
→ Momentum weakening, potential reversal down

### 3. RSI Range Shifts

In strong uptrends:
- RSI often stays between 40-80
- 40 becomes support instead of 30

In strong downtrends:
- RSI often stays between 20-60
- 60 becomes resistance instead of 70

## Trading with RSI

### Pullback Entry Strategy

1. Confirm uptrend (price > 50 SMA)
2. Wait for RSI to drop below 40
3. Buy when RSI crosses back above 40
4. Stop below recent swing low
5. Target previous high or 2:1 R/R

### Divergence Strategy

1. Spot divergence on 4H chart
2. Wait for confirmation candle
3. Enter after break of short-term resistance
4. Stop below the low of divergence
5. Target based on structure

## RSI Settings

**Standard: 14 periods**
- Good for swing trading
- Not too sensitive

**7 periods (faster):**
- More signals
- More false signals

**21 periods (slower):**
- Fewer signals
- More reliable
""",
            key_takeaways=[
                "RSI above 70 is overbought, below 30 is oversold",
                "Use RSI with trend, not against it",
                "Divergences warn of potential reversals",
                "RSI works best for entry timing, not trend direction"
            ],
            related_lessons=["tech_01", "tech_02", "strat_01"]
        )

        return lessons

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        """Get a specific lesson by ID"""
        return self.lessons.get(lesson_id)

    def get_lessons_by_category(self, category: LessonCategory) -> List[Lesson]:
        """Get all lessons in a category"""
        return [l for l in self.lessons.values() if l.category == category]

    def get_lessons_by_difficulty(self, difficulty: str) -> List[Lesson]:
        """Get all lessons of a specific difficulty"""
        return [l for l in self.lessons.values() if l.difficulty == difficulty]

    def get_curriculum_overview(self) -> Dict[str, Any]:
        """Get overview of all available lessons"""
        overview = {}

        for category in LessonCategory:
            lessons = self.get_lessons_by_category(category)
            overview[category.value] = {
                "title": category.value.replace("_", " ").title(),
                "lesson_count": len(lessons),
                "lessons": [
                    {
                        "id": l.id,
                        "title": l.title,
                        "difficulty": l.difficulty
                    }
                    for l in lessons
                ]
            }

        return overview

    def get_recommended_learning_path(self, skill_level: str = "beginner") -> List[str]:
        """Get recommended order of lessons based on skill level"""

        if skill_level == "beginner":
            return [
                "basics_01",  # What is Trading
                "basics_02",  # Market Orders
                "risk_01",    # Position Sizing
                "tech_01",    # Charts
                "psych_01",   # Psychology
                "crypto_01",  # Crypto Basics
                "tech_02",    # Moving Averages
                "strat_01",   # Swing Trading
            ]
        elif skill_level == "intermediate":
            return [
                "tech_02",    # Moving Averages
                "tech_03",    # RSI and Momentum
                "strat_01",   # Swing Trading
                "risk_02",    # Advanced Risk
                "psych_01",   # Psychology
            ]
        else:
            return [lesson_id for lesson_id in self.lessons.keys()]

    def format_lesson_for_display(self, lesson: Lesson) -> str:
        """Format a lesson for web display"""
        output = f"""
<div class="lesson">
    <div class="lesson-header">
        <h2>{lesson.title}</h2>
        <span class="badge {lesson.difficulty}">{lesson.difficulty.upper()}</span>
        <span class="badge category">{lesson.category.value.upper()}</span>
    </div>

    <div class="lesson-content">
        {lesson.content}
    </div>

    <div class="key-takeaways">
        <h3>📌 Key Takeaways</h3>
        <ul>
"""
        for takeaway in lesson.key_takeaways:
            output += f"            <li>{takeaway}</li>\n"

        output += """
        </ul>
    </div>
</div>
"""
        return output


# Global teacher instance
teacher = TradingTeacher()
