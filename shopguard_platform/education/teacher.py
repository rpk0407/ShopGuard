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
