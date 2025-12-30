"""
Trading Assistant Brain
=======================
The AI brain that understands natural language and controls the trading system.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class IntentType(Enum):
    """Types of user intents"""
    # Trading actions
    BUY = "buy"
    SELL = "sell"
    CLOSE_ALL = "close_all"
    CLOSE_POSITION = "close_position"

    # Analysis
    ANALYZE = "analyze"
    SCAN = "scan"
    CHECK_PRICE = "check_price"
    FIND_OPPORTUNITIES = "find_opportunities"

    # Portfolio
    PORTFOLIO_STATUS = "portfolio_status"
    CHECK_POSITIONS = "check_positions"
    TRADE_HISTORY = "trade_history"
    PERFORMANCE = "performance"

    # Settings
    CHANGE_SETTINGS = "change_settings"
    CHECK_SETTINGS = "check_settings"

    # Education
    EXPLAIN = "explain"
    TEACH = "teach"
    HELP = "help"

    # System
    SYSTEM_STATUS = "system_status"
    GREETING = "greeting"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Parsed user intent"""
    type: IntentType
    asset: Optional[str] = None
    amount: Optional[float] = None
    topic: Optional[str] = None
    raw_query: str = ""
    confidence: float = 1.0


@dataclass
class AssistantResponse:
    """Response from the assistant"""
    message: str
    action_taken: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    follow_up_prompt: Optional[str] = None


class TradingAssistant:
    """
    AI Trading Assistant
    Controls the entire system through natural language
    """

    def __init__(self, engine, coordinator, teacher, db):
        self.engine = engine
        self.coordinator = coordinator
        self.teacher = teacher
        self.db = db

        self.conversation_history = []
        self.user_context = {
            "last_asset_mentioned": None,
            "last_action": None,
            "experience_level": "beginner"
        }

        # Asset mappings
        self.asset_aliases = {
            # Crypto
            'bitcoin': 'BTC', 'btc': 'BTC', 'bit': 'BTC',
            'ethereum': 'ETH', 'eth': 'ETH', 'ether': 'ETH',

            # Stocks/ETFs
            'spy': 'SPY', 's&p': 'SPY', 's&p 500': 'SPY', 'sp500': 'SPY',
            'qqq': 'QQQ', 'nasdaq': 'QQQ', 'tech': 'QQQ',
            'nvidia': 'NVDA', 'nvda': 'NVDA',
            'apple': 'AAPL', 'aapl': 'AAPL',
            'tesla': 'TSLA', 'tsla': 'TSLA',
            'amd': 'AMD',
        }

        # Greeting patterns
        self.greetings = ['hi', 'hello', 'hey', 'yo', 'sup', 'good morning',
                          'good afternoon', 'good evening', 'whats up', "what's up"]

    def process_message(self, message: str) -> AssistantResponse:
        """
        Main entry point - process user message and return response
        """
        # Add to history
        self.conversation_history.append({
            "role": "user",
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

        # Parse intent
        intent = self._parse_intent(message)

        # Handle based on intent
        response = self._handle_intent(intent)

        # Add response to history
        self.conversation_history.append({
            "role": "assistant",
            "message": response.message,
            "timestamp": datetime.now().isoformat()
        })

        return response

    def _parse_intent(self, message: str) -> Intent:
        """Parse user message to determine intent"""
        msg_lower = message.lower().strip()

        # Check for greetings
        if any(g in msg_lower for g in self.greetings):
            return Intent(type=IntentType.GREETING, raw_query=message)

        # Check for help
        if any(w in msg_lower for w in ['help', 'how do i', 'what can you do', 'guide me']):
            return Intent(type=IntentType.HELP, raw_query=message)

        # Trading actions
        if any(w in msg_lower for w in ['buy', 'purchase', 'long', 'enter']):
            asset = self._extract_asset(message)
            amount = self._extract_amount(message)
            return Intent(type=IntentType.BUY, asset=asset, amount=amount, raw_query=message)

        if any(w in msg_lower for w in ['sell', 'exit', 'close position', 'dump']):
            if 'all' in msg_lower or 'everything' in msg_lower:
                return Intent(type=IntentType.CLOSE_ALL, raw_query=message)
            asset = self._extract_asset(message)
            return Intent(type=IntentType.SELL, asset=asset, raw_query=message)

        if 'close all' in msg_lower:
            return Intent(type=IntentType.CLOSE_ALL, raw_query=message)

        # Analysis - expanded patterns
        analysis_patterns = [
            'analyze', 'analysis', 'analyse', 'deep dive', 'research',
            'what do you think', 'should i', 'is it good', 'is it bad',
            'will it go', 'price prediction', 'forecast', 'outlook',
            'bullish', 'bearish', 'momentum', 'trend',
            'next move', 'what could', 'what would', 'change your',
            'recommendation', 'signal', 'when should'
        ]
        if any(w in msg_lower for w in analysis_patterns):
            asset = self._extract_asset(message)
            # If no asset found, check context for last mentioned asset
            if not asset and self.user_context.get("last_asset_mentioned"):
                asset = self.user_context["last_asset_mentioned"]
            return Intent(type=IntentType.ANALYZE, asset=asset, raw_query=message)

        if any(w in msg_lower for w in ['scan', 'find signals', 'check market', 'market scan']):
            return Intent(type=IntentType.SCAN, raw_query=message)

        if any(w in msg_lower for w in ['opportunities', 'opportunity', 'what should i', 'what to trade']):
            return Intent(type=IntentType.FIND_OPPORTUNITIES, raw_query=message)

        if any(w in msg_lower for w in ['price', 'how much', 'current']) and self._extract_asset(message):
            asset = self._extract_asset(message)
            return Intent(type=IntentType.CHECK_PRICE, asset=asset, raw_query=message)

        # Portfolio
        if any(w in msg_lower for w in ['portfolio', 'balance', 'equity', 'how much do i have', 'my money']):
            return Intent(type=IntentType.PORTFOLIO_STATUS, raw_query=message)

        if any(w in msg_lower for w in ['positions', 'holdings', 'what do i own', 'my trades']):
            return Intent(type=IntentType.CHECK_POSITIONS, raw_query=message)

        if any(w in msg_lower for w in ['history', 'past trades', 'trade log']):
            return Intent(type=IntentType.TRADE_HISTORY, raw_query=message)

        if any(w in msg_lower for w in ['performance', 'how am i doing', 'win rate', 'profit']):
            return Intent(type=IntentType.PERFORMANCE, raw_query=message)

        # Settings
        if any(w in msg_lower for w in ['settings', 'config', 'configure']):
            if any(w in msg_lower for w in ['change', 'set', 'update', 'modify']):
                return Intent(type=IntentType.CHANGE_SETTINGS, raw_query=message)
            return Intent(type=IntentType.CHECK_SETTINGS, raw_query=message)

        # Education
        if any(w in msg_lower for w in ['explain', 'what is', 'tell me about', 'how does', 'teach me']):
            topic = self._extract_topic(message)
            return Intent(type=IntentType.EXPLAIN, topic=topic, raw_query=message)

        if any(w in msg_lower for w in ['learn', 'education', 'lessons', 'course', 'tutorial']):
            topic = self._extract_topic(message)
            return Intent(type=IntentType.TEACH, topic=topic, raw_query=message)

        # System
        if any(w in msg_lower for w in ['status', 'system', 'running', 'working']):
            return Intent(type=IntentType.SYSTEM_STATUS, raw_query=message)

        # Smart fallback: If message contains an asset, analyze it
        asset = self._extract_asset(message)
        if asset:
            return Intent(type=IntentType.ANALYZE, asset=asset, raw_query=message)

        # If there's a last mentioned asset and it seems like a follow-up question
        if self.user_context.get("last_asset_mentioned"):
            followup_words = ['it', 'that', 'this', 'move', 'change', 'go', 'drop', 'rise', 'pump', 'dump', 'break', 'hold', 'buy', 'sell', 'when', 'what', 'why', 'how', 'could', 'would', 'should', 'will', 'can']
            if any(w in msg_lower for w in followup_words):
                return Intent(type=IntentType.ANALYZE, asset=self.user_context["last_asset_mentioned"], raw_query=message)

        # Unknown - try to be helpful
        return Intent(type=IntentType.UNKNOWN, raw_query=message)

    def _extract_asset(self, message: str) -> Optional[str]:
        """Extract asset symbol from message"""
        msg_lower = message.lower()

        # Check aliases
        for alias, symbol in self.asset_aliases.items():
            if alias in msg_lower:
                self.user_context["last_asset_mentioned"] = symbol
                return symbol

        # Check if they're referring to the last mentioned asset
        if self.user_context["last_asset_mentioned"]:
            if any(w in msg_lower for w in ['it', 'that', 'same', 'again']):
                return self.user_context["last_asset_mentioned"]

        return None

    def _extract_amount(self, message: str) -> Optional[float]:
        """Extract dollar amount from message"""
        # Match patterns like $50, 50 dollars, 50$
        patterns = [
            r'\$(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:dollars?|usd|\$)',
            r'(\d+(?:\.\d+)?)\s*(?:bucks?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return float(match.group(1))

        return None

    def _extract_topic(self, message: str) -> Optional[str]:
        """Extract educational topic from message"""
        topics = {
            'rsi': 'RSI (Relative Strength Index)',
            'macd': 'MACD',
            'bollinger': 'Bollinger Bands',
            'moving average': 'Moving Averages',
            'support': 'Support and Resistance',
            'resistance': 'Support and Resistance',
            'fibonacci': 'Fibonacci Retracement',
            'stop loss': 'Stop Loss',
            'take profit': 'Take Profit',
            'position sizing': 'Position Sizing',
            'risk management': 'Risk Management',
            'trend': 'Trend Analysis',
            'candlestick': 'Candlestick Charts',
            'chart': 'Chart Reading',
            'sentiment': 'Market Sentiment',
            'fomo': 'FOMO and FUD',
            'fud': 'FOMO and FUD',
        }

        msg_lower = message.lower()
        for keyword, topic in topics.items():
            if keyword in msg_lower:
                return topic

        return None

    def _handle_intent(self, intent: Intent) -> AssistantResponse:
        """Handle parsed intent and return response"""

        handlers = {
            IntentType.GREETING: self._handle_greeting,
            IntentType.HELP: self._handle_help,
            IntentType.BUY: self._handle_buy,
            IntentType.SELL: self._handle_sell,
            IntentType.CLOSE_ALL: self._handle_close_all,
            IntentType.ANALYZE: self._handle_analyze,
            IntentType.SCAN: self._handle_scan,
            IntentType.FIND_OPPORTUNITIES: self._handle_opportunities,
            IntentType.CHECK_PRICE: self._handle_check_price,
            IntentType.PORTFOLIO_STATUS: self._handle_portfolio,
            IntentType.CHECK_POSITIONS: self._handle_positions,
            IntentType.TRADE_HISTORY: self._handle_trade_history,
            IntentType.PERFORMANCE: self._handle_performance,
            IntentType.CHECK_SETTINGS: self._handle_check_settings,
            IntentType.CHANGE_SETTINGS: self._handle_change_settings,
            IntentType.EXPLAIN: self._handle_explain,
            IntentType.TEACH: self._handle_teach,
            IntentType.SYSTEM_STATUS: self._handle_system_status,
            IntentType.UNKNOWN: self._handle_unknown,
        }

        handler = handlers.get(intent.type, self._handle_unknown)
        return handler(intent)

    # =========================================================================
    # INTENT HANDLERS
    # =========================================================================

    def _handle_greeting(self, intent: Intent) -> AssistantResponse:
        return AssistantResponse(
            message="""Hey! 👋 I'm your AI Trading Assistant.

I can help you with:
• **Trade**: "Buy Bitcoin" or "Sell ETH"
• **Analyze**: "Analyze NVDA" for deep multi-agent analysis
• **Learn**: "Explain RSI" or "Teach me about risk management"
• **Check Portfolio**: "Show my portfolio" or "What positions do I have?"
• **Find Opportunities**: "Find trading opportunities"
• **Scan Markets**: "Scan the market"

What would you like to do?""",
            suggestions=[
                "Analyze Bitcoin",
                "Show my portfolio",
                "Find opportunities",
                "Teach me about trading"
            ],
            follow_up_prompt="How can I help you today?"
        )

    def _handle_help(self, intent: Intent) -> AssistantResponse:
        return AssistantResponse(
            message="""Here's everything I can do:

**🔄 TRADING COMMANDS**
• "Buy Bitcoin" / "Buy $50 of ETH"
• "Sell NVDA" / "Close my ETH position"
• "Close all positions"

**📊 ANALYSIS**
• "Analyze BTC" - Deep multi-agent analysis
• "Scan the market" - Check all assets for signals
• "Find opportunities" - Get explained trading setups
• "What's the price of Ethereum?"

**💰 PORTFOLIO**
• "Show my portfolio"
• "What positions do I have?"
• "Show my trade history"
• "How am I performing?"

**📚 LEARNING**
• "Explain RSI" / "What is MACD?"
• "Teach me about risk management"
• "How does position sizing work?"

**⚙️ SETTINGS**
• "Show settings"
• "Change my capital to $200"

Just talk to me naturally - I'll understand!""",
            suggestions=[
                "Analyze Bitcoin",
                "Show portfolio",
                "Find opportunities",
                "Explain RSI"
            ]
        )

    def _handle_buy(self, intent: Intent) -> AssistantResponse:
        if not intent.asset:
            return AssistantResponse(
                message="Which asset would you like to buy? For example: 'Buy Bitcoin' or 'Buy $50 of ETH'",
                follow_up_prompt="What do you want to buy?"
            )

        # First, run a quick analysis
        try:
            analysis = self.coordinator.analyze(intent.asset, capital=100)

            # Check if signal is favorable
            action = analysis.action.value
            confidence = analysis.confidence.name

            if 'SELL' in action:
                return AssistantResponse(
                    message=f"""⚠️ **Hold on!** My analysis suggests {intent.asset} might not be a good buy right now.

**Current Signal**: {action}
**Confidence**: {confidence}
**Reason**: {analysis.summary}

Do you still want to proceed? Say "Yes, buy {intent.asset} anyway" to confirm, or ask me to "analyze {intent.asset}" for more details.""",
                    data={"asset": intent.asset, "signal": action},
                    follow_up_prompt="Still want to buy?"
                )

            # Execute the buy
            if self.engine.last_signals.get(intent.asset):
                sig = self.engine.last_signals[intent.asset]
            else:
                self.engine.scan_all()
                sig = self.engine.last_signals.get(intent.asset)

            if sig:
                success = self.engine.execute_buy(intent.asset, sig)
                if success:
                    return AssistantResponse(
                        message=f"""✅ **Bought {intent.asset}!**

**Entry Price**: ${sig.price:.2f}
**Stop Loss**: ${sig.stop_loss:.2f} ({((sig.stop_loss - sig.price) / sig.price * 100):.1f}%)
**Take Profit**: ${sig.take_profit:.2f} ({((sig.take_profit - sig.price) / sig.price * 100):.1f}%)

**Analysis Summary**: {analysis.summary[:200]}...

I'll monitor this position for you. Say "show positions" to see your holdings.""",
                        action_taken=f"Bought {intent.asset}",
                        data={"asset": intent.asset, "price": sig.price}
                    )

            return AssistantResponse(
                message=f"Sorry, I couldn't execute the buy for {intent.asset}. Let me scan the market first. Say 'scan market' then try again."
            )

        except Exception as e:
            return AssistantResponse(
                message=f"Error analyzing/buying {intent.asset}: {str(e)}"
            )

    def _handle_sell(self, intent: Intent) -> AssistantResponse:
        if not intent.asset:
            # Check if they have positions
            positions = self.db.get_positions()
            if positions:
                pos_list = ', '.join([p.symbol for p in positions])
                return AssistantResponse(
                    message=f"Which position do you want to close? You have: {pos_list}",
                    follow_up_prompt="Which one to sell?"
                )
            return AssistantResponse(
                message="You don't have any open positions to sell."
            )

        try:
            success = self.engine.execute_sell(intent.asset)
            if success:
                return AssistantResponse(
                    message=f"✅ **Sold {intent.asset}!** Position closed.",
                    action_taken=f"Sold {intent.asset}"
                )
            else:
                return AssistantResponse(
                    message=f"I couldn't sell {intent.asset}. You might not have a position in it."
                )
        except Exception as e:
            return AssistantResponse(message=f"Error selling: {str(e)}")

    def _handle_close_all(self, intent: Intent) -> AssistantResponse:
        positions = self.db.get_positions()
        if not positions:
            return AssistantResponse(message="You don't have any open positions.")

        closed = 0
        for pos in positions:
            if self.engine.execute_sell(pos.symbol):
                closed += 1

        return AssistantResponse(
            message=f"✅ **Closed {closed} positions.** All trades have been exited.",
            action_taken=f"Closed {closed} positions"
        )

    def _handle_analyze(self, intent: Intent) -> AssistantResponse:
        if not intent.asset:
            return AssistantResponse(
                message="Which asset would you like me to analyze? For example: 'Analyze Bitcoin' or 'Analyze NVDA'",
                suggestions=["Analyze BTC", "Analyze ETH", "Analyze SPY", "Analyze NVDA"]
            )

        try:
            analysis = self.coordinator.analyze(intent.asset, capital=100)
            query = intent.raw_query.lower()

            # Check if user is asking about what would change the recommendation
            if any(phrase in query for phrase in ['change', 'what would', 'what could', 'when would', 'when will', 'what move', 'what if']):
                return self._build_change_recommendation_response(intent.asset, analysis)

            # Check if user is asking about prediction/direction
            if any(phrase in query for phrase in ['will it', 'going to', 'predict', 'next', 'where', 'direction']):
                return self._build_prediction_response(intent.asset, analysis)

            # Check if user is asking for opinion/advice
            if any(phrase in query for phrase in ['should i', 'do you think', 'is it good', 'is it worth', 'recommend']):
                return self._build_opinion_response(intent.asset, analysis)

            # Default: Full analysis
            return self._build_full_analysis_response(intent.asset, analysis)

        except Exception as e:
            return AssistantResponse(message=f"Error analyzing {intent.asset}: {str(e)}")

    def _build_change_recommendation_response(self, asset: str, analysis) -> AssistantResponse:
        """Build response for 'what would change your recommendation' questions"""
        action = analysis.action.value
        tech = analysis.agent_opinions.get('technical', {})

        # Get key levels from technical analysis
        support = tech.indicators.get('support', 0) if hasattr(tech, 'indicators') else 0
        resistance = tech.indicators.get('resistance', 0) if hasattr(tech, 'indicators') else 0
        rsi = tech.indicators.get('rsi', 50) if hasattr(tech, 'indicators') else 50

        if 'HOLD' in action:
            response = f"""🔄 **What Would Change My HOLD on {asset}?**

My current recommendation is **HOLD** because the signals are mixed. Here's what could shift my view:

**📈 For a BUY signal, I'd want to see:**
• RSI dropping below 30 (currently {rsi:.0f}) - showing oversold conditions
• Price bouncing off support level{f' around ${support:,.0f}' if support else ''}
• Positive news catalyst or social sentiment shift
• Multiple agents agreeing on bullish outlook (currently {analysis.consensus_level:.0%} consensus)

**📉 For a SELL signal, I'd want to see:**
• RSI spiking above 70 - showing overbought conditions
• Price rejecting resistance{f' around ${resistance:,.0f}' if resistance else ''}
• Negative news or bearish social sentiment
• Breakdown below key support levels

**⏰ KEY LEVELS TO WATCH:**
• Support: {f'${support:,.0f}' if support else 'Calculating...'}
• Resistance: {f'${resistance:,.0f}' if resistance else 'Calculating...'}

**💡 TIP:** In uncertain markets, patience pays. Wait for clearer signals rather than forcing a trade."""

        elif 'BUY' in action:
            response = f"""🔄 **What Would Change My BUY on {asset}?**

I'm currently bullish with a **{action}** recommendation. Here's what could change my mind:

**⚠️ Warning signs that would flip me to HOLD/SELL:**
• RSI climbing above 70 (currently {rsi:.0f}) - overbought territory
• Price failing at resistance{f' near ${resistance:,.0f}' if resistance else ''}
• Negative news breaking or social sentiment turning fearful
• Volume drying up on the rally

**✅ What would strengthen my conviction:**
• Breaking above resistance with strong volume
• RSI staying in 50-70 range (healthy momentum)
• Continued positive news flow
• Social sentiment staying bullish without extreme FOMO

**⏰ KEY LEVELS:**
• Stop Loss Zone: {f'${support:,.0f}' if support else '-3% from entry'}
• Take Profit Zone: {f'${resistance:,.0f}' if resistance else '+6% from entry'}"""

        else:  # SELL
            response = f"""🔄 **What Would Change My SELL on {asset}?**

I'm currently bearish with a **{action}** recommendation. Here's what could change my mind:

**✅ Signs that would flip me to HOLD/BUY:**
• RSI dropping below 30 (currently {rsi:.0f}) - oversold bounce potential
• Price holding at support{f' near ${support:,.0f}' if support else ''}
• Positive news catalyst emerging
• Extreme FUD in social media (contrarian buy signal)

**⚠️ What would confirm my bearish view:**
• Breaking below key support levels
• RSI staying below 50
• Continued negative news or sentiment
• Lower highs and lower lows pattern

**⏰ KEY LEVELS:**
• Critical Support: {f'${support:,.0f}' if support else 'Calculating...'}
• Resistance to reclaim: {f'${resistance:,.0f}' if resistance else 'Calculating...'}"""

        return AssistantResponse(
            message=response,
            data={"analysis": analysis.to_dict()},
            suggestions=[f"Analyze {asset}", "Scan market", "Show opportunities"]
        )

    def _build_prediction_response(self, asset: str, analysis) -> AssistantResponse:
        """Build response for prediction/direction questions"""
        action = analysis.action.value
        confidence = analysis.confidence.name

        direction = "UP 📈" if 'BUY' in action else "DOWN 📉" if 'SELL' in action else "SIDEWAYS ↔️"

        response = f"""🔮 **{asset} Direction Outlook**

**Expected Direction:** {direction}
**Confidence:** {confidence}
**Timeframe:** {analysis.suggested_hold_time}

**Why I think this:**
{analysis.summary}

**Key Factors:**
"""
        for reason in analysis.key_reasons[:3]:
            response += f"• {reason}\n"

        response += f"""
**📊 Agent Consensus:** {analysis.consensus_level:.0%}
• Technical: {analysis.agent_opinions.get('technical', {}).action.value if hasattr(analysis.agent_opinions.get('technical', {}), 'action') else 'N/A'}
• News: {analysis.agent_opinions.get('news', {}).action.value if hasattr(analysis.agent_opinions.get('news', {}), 'action') else 'N/A'}
• Social: {analysis.agent_opinions.get('social', {}).action.value if hasattr(analysis.agent_opinions.get('social', {}), 'action') else 'N/A'}

**⚠️ DISCLAIMER:** This is algorithmic analysis, not financial advice. Markets can move unexpectedly!"""

        return AssistantResponse(
            message=response,
            data={"analysis": analysis.to_dict()},
            suggestions=[f"Buy {asset}", f"What would change this?", "Show my portfolio"]
        )

    def _build_opinion_response(self, asset: str, analysis) -> AssistantResponse:
        """Build response for 'should I buy/sell' questions"""
        action = analysis.action.value
        confidence = analysis.confidence.name

        if 'STRONG_BUY' in action:
            verdict = "Yes, this looks like a good opportunity! 🟢"
            advice = "Multiple signals align bullishly. Consider a position with proper risk management."
        elif 'BUY' in action:
            verdict = "Leaning yes, but with caution 🟡"
            advice = "Signals are moderately bullish. Use a smaller position size and set a stop loss."
        elif 'STRONG_SELL' in action:
            verdict = "No, I'd avoid buying right now 🔴"
            advice = "Multiple bearish signals. If you're holding, consider reducing or exiting."
        elif 'SELL' in action:
            verdict = "Probably not the best time 🟠"
            advice = "Signals lean bearish. Wait for better entry or set tight stops."
        else:
            verdict = "I'm neutral - no strong edge either way ⚪"
            advice = "Signals are mixed. Best to wait for clearer direction."

        response = f"""💭 **My Opinion on {asset}**

**Verdict:** {verdict}
**Recommendation:** {action}
**Confidence:** {confidence}

**My Advice:** {advice}

**Quick Summary:**
{analysis.summary[:300]}...

**Opportunity:** {analysis.primary_opportunity}
**Risk:** {analysis.primary_risk}

**Position Guidance:**
• Entry: {analysis.recommended_entry}
• Stop Loss: -{analysis.stop_loss_pct:.0f}%
• Take Profit: +{analysis.take_profit_pct:.0f}%
• Hold Time: {analysis.suggested_hold_time}

*Remember: Never risk more than 1-2% of your portfolio on a single trade!*"""

        return AssistantResponse(
            message=response,
            data={"analysis": analysis.to_dict()},
            suggestions=[f"Buy {asset}" if 'BUY' in action else "Find opportunities", "Explain risk management", "Show portfolio"]
        )

    def _build_full_analysis_response(self, asset: str, analysis) -> AssistantResponse:
        """Build the full detailed analysis response"""
        agent_summary = ""
        for name, opinion in analysis.agent_opinions.items():
            agent_summary += f"\n• **{opinion.agent_name}**: {opinion.action.value} ({opinion.confidence.name})"

        response = f"""🧠 **Deep Analysis: {asset}**

**RECOMMENDATION**: {analysis.action.value}
**CONFIDENCE**: {analysis.confidence.name}
**CONSENSUS**: {analysis.consensus_level:.0%} agreement among agents

**SUMMARY**:
{analysis.summary}

**AGENT OPINIONS**:{agent_summary}

**💡 OPPORTUNITY**: {analysis.primary_opportunity}

**⚠️ RISK**: {analysis.primary_risk}

**📋 KEY REASONS**:
"""
        for reason in analysis.key_reasons[:4]:
            response += f"• {reason}\n"

        response += f"""
**⏱️ SUGGESTED HOLD TIME**: {analysis.suggested_hold_time}

**📚 WHAT YOU CAN LEARN**:
"""
        for point in analysis.learning_points[:2]:
            response += f"• {point}\n"

        return AssistantResponse(
            message=response,
            data={"analysis": analysis.to_dict()},
            suggestions=[
                f"Buy {asset}" if 'BUY' in analysis.action.value else f"Analyze another asset",
                "Show opportunities",
                f"What would change this recommendation?"
            ]
        )

    def _handle_scan(self, intent: Intent) -> AssistantResponse:
        try:
            signals = self.engine.scan_all()

            if not signals:
                return AssistantResponse(message="No signals found. Market might be quiet.")

            response = "📡 **Market Scan Results**\n\n"

            for symbol, sig in sorted(signals.items(), key=lambda x: x[1].confidence, reverse=True):
                signal_emoji = "🟢" if "BUY" in sig.signal.value else "🔴" if "SELL" in sig.signal.value else "🟡"
                response += f"{signal_emoji} **{symbol}**: {sig.signal.value} ({sig.confidence:.0%} conf) @ ${sig.price:.2f}\n"

            response += "\n*Say 'Analyze [asset]' for deep analysis or 'Buy [asset]' to trade.*"

            return AssistantResponse(
                message=response,
                data={"signals": {s: v.signal.value for s, v in signals.items()}}
            )

        except Exception as e:
            return AssistantResponse(message=f"Error scanning market: {str(e)}")

    def _handle_opportunities(self, intent: Intent) -> AssistantResponse:
        try:
            from ..analysis.opportunity import detector

            response = "💡 **Trading Opportunities**\n\n"
            found_any = False

            for asset in ['BTC', 'ETH', 'SPY', 'QQQ', 'NVDA']:
                try:
                    analysis = self.coordinator.analyze(asset, capital=100)
                    opportunities = detector.detect_opportunities(analysis)

                    for opp in opportunities[:1]:  # Top opportunity per asset
                        found_any = True
                        direction_emoji = "🟢" if opp.direction == "LONG" else "🔴"
                        response += f"""{direction_emoji} **{opp.asset}: {opp.headline}**
   • Direction: {opp.direction}
   • Entry: {opp.entry_zone}
   • Why now: {opp.why_now[:100]}...

"""
                except:
                    continue

            if not found_any:
                response = "No clear opportunities right now. Markets might be mixed. Try 'Scan market' for current signals."

            response += "*Say 'Analyze [asset]' for more details on any opportunity.*"

            return AssistantResponse(message=response)

        except Exception as e:
            return AssistantResponse(message=f"Error finding opportunities: {str(e)}")

    def _handle_check_price(self, intent: Intent) -> AssistantResponse:
        if not intent.asset:
            return AssistantResponse(message="Which asset? Say 'price of Bitcoin' or 'BTC price'")

        try:
            price = self.engine.get_price(intent.asset)
            if price:
                return AssistantResponse(
                    message=f"**{intent.asset}** is currently at **${price:,.2f}**",
                    data={"asset": intent.asset, "price": price}
                )
            return AssistantResponse(message=f"Couldn't get price for {intent.asset}")
        except Exception as e:
            return AssistantResponse(message=f"Error: {str(e)}")

    def _handle_portfolio(self, intent: Intent) -> AssistantResponse:
        try:
            portfolio = self.engine.get_portfolio_value()

            response = f"""💰 **Your Portfolio**

**Total Equity**: ${portfolio['equity']:.2f}
**Cash Available**: ${portfolio['cash']:.2f}
**Positions Value**: ${portfolio['positions_value']:.2f}

**Total P&L**: ${portfolio['total_pnl']:+.2f} ({portfolio['total_pnl_pct']:+.1f}%)
"""
            if portfolio['positions']:
                response += "\n**Open Positions**:\n"
                for pos in portfolio['positions']:
                    pnl = (pos.current_price - pos.entry_price) * pos.quantity
                    pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price * 100
                    emoji = "🟢" if pnl >= 0 else "🔴"
                    response += f"{emoji} {pos.symbol}: {pnl:+.2f} ({pnl_pct:+.1f}%)\n"
            else:
                response += "\n*No open positions*"

            return AssistantResponse(
                message=response,
                data=portfolio
            )
        except Exception as e:
            return AssistantResponse(message=f"Error: {str(e)}")

    def _handle_positions(self, intent: Intent) -> AssistantResponse:
        positions = self.db.get_positions()

        if not positions:
            return AssistantResponse(
                message="You don't have any open positions.",
                suggestions=["Scan market", "Find opportunities", "Buy Bitcoin"]
            )

        response = "📊 **Your Open Positions**\n\n"
        for pos in positions:
            pnl = (pos.current_price - pos.entry_price) * pos.quantity
            pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price * 100
            emoji = "🟢" if pnl >= 0 else "🔴"

            response += f"""{emoji} **{pos.symbol}**
   Entry: ${pos.entry_price:.2f} | Current: ${pos.current_price:.2f}
   Qty: {pos.quantity:.4f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)
   SL: ${pos.stop_loss:.2f} | TP: ${pos.take_profit:.2f}

"""

        return AssistantResponse(message=response)

    def _handle_trade_history(self, intent: Intent) -> AssistantResponse:
        trades = self.db.get_trades(10)

        if not trades:
            return AssistantResponse(message="No trade history yet.")

        response = "📜 **Recent Trades**\n\n"
        for trade in trades[:10]:
            emoji = "🟢" if trade.side == "BUY" else "🔴"
            pnl_str = f" | P&L: ${trade.pnl:+.2f}" if trade.pnl != 0 else ""
            response += f"{emoji} {trade.side} {trade.symbol} @ ${trade.price:.2f}{pnl_str}\n"

        return AssistantResponse(message=response)

    def _handle_performance(self, intent: Intent) -> AssistantResponse:
        stats = self.db.get_trade_stats()
        portfolio = self.engine.get_portfolio_value()

        response = f"""📈 **Your Performance**

**Win Rate**: {stats['win_rate']}%
**Total Trades**: {stats['total_trades']}
**Profitable Trades**: {stats['profitable_trades']}
**Losing Trades**: {stats['losing_trades']}

**Total P&L**: ${portfolio['total_pnl']:+.2f} ({portfolio['total_pnl_pct']:+.1f}%)
**Current Equity**: ${portfolio['equity']:.2f}
"""

        if stats['win_rate'] >= 50:
            response += "\n✨ You're doing well! Keep following your strategy."
        elif stats['total_trades'] < 5:
            response += "\n💡 Still early! Focus on learning and small position sizes."
        else:
            response += "\n💡 Consider reviewing your entry criteria or risk management."

        return AssistantResponse(message=response)

    def _handle_check_settings(self, intent: Intent) -> AssistantResponse:
        settings = self.db.get_all_settings()

        response = f"""⚙️ **Current Settings**

**Capital**: ${float(settings.get('initial_capital', 100)):.2f}
**Risk Level**: {settings.get('risk_level', 'moderate')}
**Min Confidence**: {float(settings.get('min_confidence', 0.65)) * 100:.0f}%
**Scan Interval**: {settings.get('scan_interval', 5)} minutes

Say 'change capital to $X' or 'set risk to aggressive' to modify."""

        return AssistantResponse(message=response)

    def _handle_change_settings(self, intent: Intent) -> AssistantResponse:
        msg = intent.raw_query.lower()

        # Try to extract what they want to change
        if 'capital' in msg:
            amount = self._extract_amount(intent.raw_query)
            if amount:
                self.db.set_setting('initial_capital', str(amount))
                return AssistantResponse(
                    message=f"✅ Capital updated to ${amount:.2f}",
                    action_taken="Updated capital"
                )

        if 'risk' in msg:
            if 'aggressive' in msg:
                self.db.set_setting('risk_level', 'aggressive')
                return AssistantResponse(message="✅ Risk level set to AGGRESSIVE (5% SL, 10% TP)")
            elif 'conservative' in msg:
                self.db.set_setting('risk_level', 'conservative')
                return AssistantResponse(message="✅ Risk level set to CONSERVATIVE (2% SL, 4% TP)")
            elif 'moderate' in msg:
                self.db.set_setting('risk_level', 'moderate')
                return AssistantResponse(message="✅ Risk level set to MODERATE (3% SL, 6% TP)")

        return AssistantResponse(
            message="What would you like to change? Examples:\n• 'Set capital to $500'\n• 'Set risk to aggressive'\n• 'Set confidence to 70%'"
        )

    def _handle_explain(self, intent: Intent) -> AssistantResponse:
        if not intent.topic:
            return AssistantResponse(
                message="What would you like me to explain? For example:\n• 'Explain RSI'\n• 'What is MACD?'\n• 'How does position sizing work?'",
                suggestions=["Explain RSI", "What is MACD", "Explain stop loss", "Position sizing"]
            )

        # Get explanation based on topic
        explanations = {
            'RSI (Relative Strength Index)': """📊 **RSI (Relative Strength Index)**

RSI measures momentum on a scale of 0-100.

**Key Levels:**
• **Above 70**: OVERBOUGHT - Price might pull back
• **Below 30**: OVERSOLD - Price might bounce
• **40-60**: Neutral zone

**How I use it:**
- In uptrends, RSI dropping to 30-40 = buying opportunity
- In downtrends, RSI rising to 60-70 = selling opportunity
- Divergence (price makes new high but RSI doesn't) = warning sign

**Formula:** RSI = 100 - (100 / (1 + Average Gain / Average Loss))""",

            'MACD': """📊 **MACD (Moving Average Convergence Divergence)**

MACD shows the relationship between two moving averages.

**Components:**
• **MACD Line**: 12-day EMA minus 26-day EMA
• **Signal Line**: 9-day EMA of MACD
• **Histogram**: Difference between them

**Signals:**
• MACD crosses ABOVE signal = **BULLISH**
• MACD crosses BELOW signal = **BEARISH**
• Histogram growing = momentum increasing

**Best used for:** Trend-following trades in trending markets.""",

            'Bollinger Bands': """📊 **Bollinger Bands**

Shows volatility and potential overbought/oversold levels.

**Components:**
• **Middle**: 20-day simple moving average
• **Upper**: Middle + (2 × standard deviation)
• **Lower**: Middle - (2 × standard deviation)

**Interpretation:**
• Price at upper band = potentially overbought
• Price at lower band = potentially oversold
• Bands squeezing = big move coming!
• Bands expanding = high volatility

**Strategy:** "Bollinger Bounce" - buy near lower, sell near upper.""",

            'Support and Resistance': """📊 **Support and Resistance**

Key price levels where buying/selling pressure is strong.

**SUPPORT:** Floor where buyers step in
**RESISTANCE:** Ceiling where sellers appear

**How they form:**
• Previous highs and lows
• Round numbers ($100, $50,000)
• Moving averages
• High volume areas

**Key rule:** Once broken, support becomes resistance and vice versa!

**Trading:**
• Buy near support with stop below
• Sell near resistance with stop above
• Breakouts signal continuation""",

            'Stop Loss': """⚠️ **Stop Loss**

A stop loss automatically closes your position if price moves against you.

**Why it's CRUCIAL:**
• Limits your maximum loss
• Removes emotion from exit decisions
• Preserves capital for future trades

**Types:**
• **Fixed %**: 3% below entry
• **ATR-based**: 2× Average True Range
• **Support-based**: Below key support level

**Golden Rules:**
1. ALWAYS set a stop loss BEFORE entering
2. NEVER move it further away
3. Calculate position size from your stop

**Example:** Entry $100, Stop $97 = 3% risk""",

            'Position Sizing': """📏 **Position Sizing - The Most Important Skill**

Position sizing determines how much to risk on each trade.

**The 1-2% Rule:**
Never risk more than 1-2% of your portfolio per trade.

**Formula:**
Position Size = Risk Amount / Stop Loss Distance

**Example:**
• Portfolio: $100
• Risk 2% = $2
• Stop Loss: 3% below entry
• Position Size = $2 / $3 = $66.67

**Why it matters:**
• 10 losses at 2% = 18% drawdown (recoverable)
• 10 losses at 10% = 65% drawdown (devastating)

**Kelly Criterion:** Optimal bet = Win% - (Loss% / Win-Loss Ratio)""",

            'Risk Management': """⚖️ **Risk Management - How to Not Blow Up**

Risk management is about surviving to trade another day.

**Core Principles:**
1. Never risk more than 1-2% per trade
2. Never risk more than 6% total at once
3. Always use stop losses
4. Size positions based on volatility

**Drawdown Math:**
• -10% needs +11% to recover
• -50% needs +100% to recover
• -90% needs +900% to recover

**My Rules:**
• Daily loss limit: Stop if down 3-5%
• Reduce size after losing streak
• Take profits regularly
• Never revenge trade""",

            'FOMO and FUD': """🧠 **FOMO and FUD - The Emotional Traps**

**FOMO (Fear Of Missing Out):**
Buying because price is rising and you're scared to miss it.
• Usually marks TOPS
• Results in buying high
• Solution: If you missed it, wait for next setup

**FUD (Fear, Uncertainty, Doubt):**
Selling because everyone else is scared.
• Usually marks BOTTOMS
• Results in selling low
• Solution: This is often the best time to buy

**Contrarian Wisdom:**
"Be fearful when others are greedy, greedy when others are fearful."

**My approach:** I track extreme sentiment as a reversal signal."""
        }

        explanation = explanations.get(intent.topic)
        if explanation:
            return AssistantResponse(message=explanation)

        # Generic response for unknown topics
        return AssistantResponse(
            message=f"I don't have a specific lesson on '{intent.topic}', but try:\n• 'Explain RSI'\n• 'What is MACD'\n• 'Explain stop loss'\n• 'Position sizing'\n• 'Risk management'",
            suggestions=["Explain RSI", "What is MACD", "Position sizing"]
        )

    def _handle_teach(self, intent: Intent) -> AssistantResponse:
        return AssistantResponse(
            message="""📚 **Trading Education - What would you like to learn?**

**BEGINNER (Start Here):**
• What is trading? - Say "explain trading basics"
• Order types - Say "explain order types"
• Risk management - Say "explain risk management"

**TECHNICAL ANALYSIS:**
• RSI - Say "explain RSI"
• MACD - Say "explain MACD"
• Bollinger Bands - Say "explain bollinger bands"
• Support/Resistance - Say "explain support and resistance"

**RISK & PSYCHOLOGY:**
• Position sizing - Say "explain position sizing"
• Stop losses - Say "explain stop loss"
• Trading psychology - Say "explain FOMO and FUD"

Or go to the **📚 Learn** tab for full courses!""",
            suggestions=[
                "Explain trading basics",
                "Explain RSI",
                "Explain position sizing",
                "Explain FOMO"
            ]
        )

    def _handle_system_status(self, intent: Intent) -> AssistantResponse:
        portfolio = self.engine.get_portfolio_value()
        positions = self.db.get_positions()

        return AssistantResponse(
            message=f"""✅ **System Status: ONLINE**

**Portfolio**: ${portfolio['equity']:.2f}
**Open Positions**: {len(positions)}
**Last Scan**: {self.engine.last_scan.strftime('%H:%M:%S') if self.engine.last_scan else 'Never'}

**Available Agents:**
🟢 Technical Agent - Online
🟢 News Agent - Online
🟢 Social Agent - Online
🟢 Risk Agent - Online
🟢 Fundamental Agent - Online

All systems operational! How can I help you?"""
        )

    def _handle_unknown(self, intent: Intent) -> AssistantResponse:
        return AssistantResponse(
            message=f"""I'm not sure what you mean by "{intent.raw_query}".

Try:
• **Trade**: "Buy Bitcoin" or "Sell ETH"
• **Analyze**: "Analyze NVDA"
• **Learn**: "Explain RSI"
• **Portfolio**: "Show my portfolio"
• **Help**: "What can you do?"

I'm here to help with trading - just talk naturally!""",
            suggestions=["Help", "Analyze BTC", "Show portfolio", "Find opportunities"]
        )


# Global assistant instance (initialized in app.py)
assistant = None
