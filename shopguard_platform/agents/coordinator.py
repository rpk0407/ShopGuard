"""
Agent Coordinator
=================
Orchestrates all agents to produce unified analysis and recommendations.

The Coordinator:
1. Gathers opinions from all specialized agents
2. Weighs opinions based on confidence and relevance
3. Detects consensus or disagreement
4. Produces unified recommendation with detailed explanation
5. Provides educational content about the decision
"""
import requests
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .base_agent import AgentOpinion, Action, Confidence
from .technical_agent import TechnicalAgent
from .news_agent import NewsAgent
from .social_agent import SocialAgent
from .risk_agent import RiskAgent
from .fundamental_agent import FundamentalAgent


@dataclass
class ConvergenceSignal:
    """Three-pillar convergence signal for entry/exit"""
    # Entry Conditions (ALL must be True for entry)
    bio_check_passed: bool  # Viral K > 1.2 AND acceleration > 0
    physics_check_passed: bool  # Entropy < 0.6 AND Hurst > 0.65
    micro_check_passed: bool  # Whale trap detected (CVD divergence)

    # Exit Conditions (ANY triggers exit)
    entropy_circuit_breaker: bool  # Entropy > 0.9
    viral_death: bool  # Viral K < 0.8
    distribution_exit: bool  # CVD distribution detected

    # Overall Signal
    entry_signal: bool  # All 3 entry conditions met
    exit_signal: bool  # Any exit condition triggered
    signal_strength: float  # 0-1 combined strength

    # Details
    entry_reasons: List[str]
    exit_reasons: List[str]


@dataclass
class UnifiedAnalysis:
    """Complete analysis from all agents"""
    asset: str
    timestamp: datetime

    # Final recommendation
    action: Action
    confidence: Confidence
    consensus_level: float  # 0-1, how much agents agree

    # Summary
    summary: str
    key_reasons: List[str]
    primary_opportunity: str
    primary_risk: str

    # Position guidance
    recommended_entry: str
    recommended_exit: str
    position_size_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    suggested_hold_time: str

    # Individual agent opinions
    agent_opinions: Dict[str, AgentOpinion]

    # Educational explanation
    learning_points: List[str]
    what_to_watch: List[str]

    # Warnings
    warnings: List[str]

    # Convergence Signal (New Strategy) - Optional field with default
    convergence: ConvergenceSignal = None

    def to_dict(self) -> Dict:
        result = {
            "asset": self.asset,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "confidence": self.confidence.name,
            "consensus_level": self.consensus_level,
            "summary": self.summary,
            "key_reasons": self.key_reasons,
            "primary_opportunity": self.primary_opportunity,
            "primary_risk": self.primary_risk,
            "recommended_entry": self.recommended_entry,
            "recommended_exit": self.recommended_exit,
            "position_size_pct": self.position_size_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "suggested_hold_time": self.suggested_hold_time,
            "agent_opinions": {name: op.to_dict() for name, op in self.agent_opinions.items()},
            "learning_points": self.learning_points,
            "what_to_watch": self.what_to_watch,
            "warnings": self.warnings
        }

        # Add convergence signal if available
        if self.convergence:
            result["convergence"] = {
                "bio_check_passed": self.convergence.bio_check_passed,
                "physics_check_passed": self.convergence.physics_check_passed,
                "micro_check_passed": self.convergence.micro_check_passed,
                "entry_signal": self.convergence.entry_signal,
                "exit_signal": self.convergence.exit_signal,
                "signal_strength": self.convergence.signal_strength,
                "entry_reasons": self.convergence.entry_reasons,
                "exit_reasons": self.convergence.exit_reasons,
                "entropy_circuit_breaker": self.convergence.entropy_circuit_breaker,
                "viral_death": self.convergence.viral_death,
                "distribution_exit": self.convergence.distribution_exit
            }

        return result


class AgentCoordinator:
    """
    Coordinates all agents to produce unified analysis
    """

    def __init__(self):
        # Initialize all agents
        self.technical_agent = TechnicalAgent()
        self.news_agent = NewsAgent()
        self.social_agent = SocialAgent()
        self.risk_agent = RiskAgent()
        self.fundamental_agent = FundamentalAgent()

        # Agent weights (how much each opinion counts)
        self.weights = {
            'technical': 0.30,    # 30% - Technical analysis
            'fundamental': 0.20,  # 20% - Fundamentals
            'news': 0.20,         # 20% - News sentiment
            'social': 0.15,       # 15% - Social sentiment
            'risk': 0.15          # 15% - Risk assessment
        }

    def _calculate_convergence(self, opinions: Dict[str, AgentOpinion]) -> ConvergenceSignal:
        """
        Calculate the three-pillar convergence signal

        Entry requires ALL THREE conditions:
        1. Bio-Check: Viral K > 1.2 AND acceleration > 0
        2. Physics-Check: Entropy < 0.6 AND Hurst > 0.65
        3. Micro-Check: Whale trap detected (CVD divergence)

        Exit triggers if ANY of these occur:
        1. Entropy > 0.9 (circuit breaker)
        2. Viral K < 0.8 (viral death)
        3. Distribution detected (smart money selling)
        """
        entry_reasons = []
        exit_reasons = []

        # === BIO-CHECK (Social Agent - Viral K-Factor) ===
        social = opinions.get('social')
        bio_check_passed = False
        viral_k = 1.0
        viral_acceleration = 0.0
        viral_death = False

        if social and social.indicators:
            viral_k = social.indicators.get('viral_k_factor', 1.0)
            viral_acceleration = social.indicators.get('viral_acceleration', 0.0)
            bio_check_passed = social.indicators.get('bio_check_passed', False)

            if bio_check_passed:
                entry_reasons.append(f"✅ Bio-Check PASSED: Viral K={viral_k:.2f}, Acceleration={viral_acceleration:.2f}")
            else:
                entry_reasons.append(f"❌ Bio-Check FAILED: Viral K={viral_k:.2f} (need >1.2)")

            # Exit condition: Viral death
            viral_death = viral_k < 0.8
            if viral_death:
                exit_reasons.append(f"🔴 VIRAL DEATH: K-Factor dropped to {viral_k:.2f}")

        # === PHYSICS-CHECK (Technical Agent - Entropy + Hurst) ===
        technical = opinions.get('technical')
        physics_check_passed = False
        entropy = 0.5
        hurst = 0.5
        entropy_circuit_breaker = False

        if technical and technical.indicators:
            entropy = technical.indicators.get('shannon_entropy', 0.5)
            hurst = technical.indicators.get('hurst_exponent', 0.5)
            physics_check_passed = technical.indicators.get('physics_check_passed', False)

            if physics_check_passed:
                entry_reasons.append(f"✅ Physics-Check PASSED: Entropy={entropy:.2f}, Hurst={hurst:.2f}")
            else:
                entry_reasons.append(f"❌ Physics-Check FAILED: Entropy={entropy:.2f} (need <0.6), Hurst={hurst:.2f} (need >0.65)")

            # Exit condition: Entropy circuit breaker
            entropy_circuit_breaker = entropy > 0.9
            if entropy_circuit_breaker:
                exit_reasons.append(f"🔴 CIRCUIT BREAKER: Entropy spiked to {entropy:.2f} - market is chaotic")

        # === MICRO-CHECK (Risk Agent - CVD Divergence) ===
        risk = opinions.get('risk')
        micro_check_passed = False
        distribution_exit = False

        if risk and risk.indicators:
            micro_check_passed = risk.indicators.get('micro_check_passed', False)
            whale_trap = risk.indicators.get('whale_trap_detected', False)
            distribution_exit = risk.indicators.get('distribution_detected', False)

            if micro_check_passed:
                entry_reasons.append("✅ Micro-Check PASSED: Whale absorption detected")
            else:
                cvd_trend = risk.indicators.get('cvd_trend', 'NEUTRAL')
                entry_reasons.append(f"❌ Micro-Check FAILED: No whale trap (CVD: {cvd_trend})")

            # Exit condition: Distribution detected
            if distribution_exit:
                exit_reasons.append("🔴 DISTRIBUTION: Smart money selling into strength")

        # === CALCULATE FINAL SIGNALS ===

        # Entry requires ALL THREE checks to pass
        entry_signal = bio_check_passed and physics_check_passed and micro_check_passed

        # Exit triggers if ANY condition is met
        exit_signal = entropy_circuit_breaker or viral_death or distribution_exit

        # Calculate signal strength (0-1)
        checks_passed = sum([bio_check_passed, physics_check_passed, micro_check_passed])
        signal_strength = checks_passed / 3.0

        # Boost signal strength if all checks pass
        if entry_signal:
            # Add bonus for convergence
            signal_strength = min(1.0, signal_strength + 0.2)

        return ConvergenceSignal(
            bio_check_passed=bio_check_passed,
            physics_check_passed=physics_check_passed,
            micro_check_passed=micro_check_passed,
            entropy_circuit_breaker=entropy_circuit_breaker,
            viral_death=viral_death,
            distribution_exit=distribution_exit,
            entry_signal=entry_signal,
            exit_signal=exit_signal,
            signal_strength=round(signal_strength, 2),
            entry_reasons=entry_reasons,
            exit_reasons=exit_reasons
        )

    def fetch_price_data(self, asset: str) -> Dict[str, Any]:
        """Fetch current price and history for an asset"""
        data = {'asset': asset, 'price': 0, 'price_history': []}

        try:
            if asset in ['BTC', 'ETH']:
                # Crypto from CoinGecko
                coin_id = 'bitcoin' if asset == 'BTC' else 'ethereum'
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    result = response.json()
                    prices = result.get('prices', [])
                    data['price_history'] = [p[1] for p in prices]
                    data['price'] = data['price_history'][-1] if data['price_history'] else 0

                    # Get additional data
                    detail_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                    detail_response = requests.get(detail_url, timeout=10)
                    if detail_response.status_code == 200:
                        detail = detail_response.json()
                        market_data = detail.get('market_data', {})
                        data['market_cap'] = market_data.get('market_cap', {}).get('usd', 0)
                        data['volume'] = market_data.get('total_volume', {}).get('usd', 0)
                        data['change_24h'] = market_data.get('price_change_percentage_24h', 0)

            else:
                # Stocks from Yahoo Finance
                ticker = asset
                if asset == 'SPY':
                    ticker = 'SPY'
                elif asset == 'QQQ':
                    ticker = 'QQQ'

                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1mo"
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    result = response.json()
                    chart = result.get('chart', {}).get('result', [{}])[0]
                    closes = chart.get('indicators', {}).get('quote', [{}])[0].get('close', [])
                    data['price_history'] = [p for p in closes if p is not None]
                    data['price'] = data['price_history'][-1] if data['price_history'] else 0

                    # Meta data
                    meta = chart.get('meta', {})
                    data['volume'] = meta.get('regularMarketVolume', 0)

        except Exception as e:
            print(f"Error fetching data for {asset}: {e}")

        # Ensure we have some price data
        if not data['price_history']:
            data['price_history'] = [100] * 30
            data['price'] = 100

        return data

    def analyze(self, asset: str, capital: float = 100, positions: List = None) -> UnifiedAnalysis:
        """
        Perform comprehensive analysis using all agents
        """
        if positions is None:
            positions = []

        # Fetch market data
        market_data = self.fetch_price_data(asset)
        market_data['capital'] = capital
        market_data['positions'] = positions

        # Gather opinions from all agents
        opinions = {}

        print(f"  📊 Technical analysis...")
        opinions['technical'] = self.technical_agent.analyze(asset, market_data)

        print(f"  📰 News research...")
        opinions['news'] = self.news_agent.analyze(asset, market_data)

        print(f"  💬 Social sentiment...")
        opinions['social'] = self.social_agent.analyze(asset, market_data)

        print(f"  ⚠️ Risk assessment...")
        opinions['risk'] = self.risk_agent.analyze(asset, market_data)

        print(f"  📈 Fundamental analysis...")
        opinions['fundamental'] = self.fundamental_agent.analyze(asset, market_data)

        # Calculate weighted consensus
        final_action, final_confidence, consensus_level = self._calculate_consensus(opinions)

        # Calculate convergence signal (Three-Pillar Strategy)
        print(f"  🎯 Convergence analysis...")
        convergence = self._calculate_convergence(opinions)

        # Modify action based on convergence signal
        if convergence.entry_signal and final_action in [Action.HOLD, Action.BUY]:
            # Strong convergence entry signal
            final_action = Action.STRONG_BUY
            final_confidence = Confidence.VERY_HIGH
            print(f"  🔥 CONVERGENCE ENTRY: All 3 checks passed!")

        if convergence.exit_signal:
            # Exit signal triggered - override to SELL
            if final_action in [Action.BUY, Action.STRONG_BUY, Action.HOLD]:
                final_action = Action.SELL
                final_confidence = Confidence.HIGH
                print(f"  ⚠️ CONVERGENCE EXIT: Circuit breaker triggered!")

        # Generate unified summary
        summary = self._generate_summary(asset, opinions, final_action, consensus_level)

        # Extract key reasons
        key_reasons = self._extract_key_reasons(opinions, final_action)

        # Identify primary opportunity and risk
        opportunity, risk = self._identify_opportunity_and_risk(opinions)

        # Determine position guidance
        position_guidance = self._determine_position_guidance(opinions, final_action)

        # Generate learning points
        learning_points = self._generate_learning_points(opinions, final_action)

        # What to watch
        what_to_watch = self._generate_watch_list(opinions)

        # Collect all warnings
        warnings = self._collect_warnings(opinions, consensus_level)

        # Add convergence reasons to key_reasons
        if convergence.entry_signal:
            key_reasons.insert(0, "🔥 CONVERGENCE ENTRY SIGNAL: All 3 checks passed!")
            key_reasons.extend(convergence.entry_reasons)
        elif convergence.exit_signal:
            key_reasons.insert(0, "⚠️ CONVERGENCE EXIT SIGNAL: Circuit breaker triggered!")
            key_reasons.extend(convergence.exit_reasons)
        else:
            # Show which checks are passing/failing
            key_reasons.extend(convergence.entry_reasons[:3])

        return UnifiedAnalysis(
            asset=asset,
            timestamp=datetime.now(),
            action=final_action,
            confidence=final_confidence,
            consensus_level=consensus_level,
            summary=summary,
            key_reasons=key_reasons,
            primary_opportunity=opportunity,
            primary_risk=risk,
            recommended_entry=position_guidance['entry'],
            recommended_exit=position_guidance['exit'],
            position_size_pct=position_guidance['size'],
            stop_loss_pct=position_guidance['stop_loss'],
            take_profit_pct=position_guidance['take_profit'],
            suggested_hold_time=position_guidance['hold_time'],
            agent_opinions=opinions,
            learning_points=learning_points,
            what_to_watch=what_to_watch,
            warnings=warnings,
            convergence=convergence  # Optional field at the end
        )

    def _calculate_consensus(self, opinions: Dict[str, AgentOpinion]) -> tuple:
        """Calculate weighted consensus from all agents"""

        # Convert actions to scores
        action_scores = []
        confidence_weights = []

        for agent_name, opinion in opinions.items():
            weight = self.weights.get(agent_name, 0.1)
            conf_weight = opinion.confidence.weight

            action_score = opinion.action.score
            action_scores.append(action_score * weight * conf_weight)
            confidence_weights.append(weight * conf_weight)

        # Weighted average score
        total_weight = sum(confidence_weights)
        if total_weight > 0:
            final_score = sum(action_scores) / total_weight
        else:
            final_score = 0

        # Determine action from score
        if final_score > 0.5:
            action = Action.STRONG_BUY
        elif final_score > 0.2:
            action = Action.BUY
        elif final_score < -0.5:
            action = Action.STRONG_SELL
        elif final_score < -0.2:
            action = Action.SELL
        else:
            action = Action.HOLD

        # Calculate consensus level (how much agents agree)
        individual_scores = [op.action.score for op in opinions.values()]
        if individual_scores:
            # Standard deviation of scores
            mean_score = sum(individual_scores) / len(individual_scores)
            variance = sum((s - mean_score) ** 2 for s in individual_scores) / len(individual_scores)
            std_dev = variance ** 0.5

            # Convert to consensus (lower std = higher consensus)
            # Max possible std is 1 (from -1 to 1)
            consensus = max(0, 1 - std_dev)
        else:
            consensus = 0.5

        # Determine confidence
        if consensus > 0.8:
            confidence = Confidence.VERY_HIGH
        elif consensus > 0.6:
            confidence = Confidence.HIGH
        elif consensus > 0.4:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        return action, confidence, consensus

    def _generate_summary(self, asset: str, opinions: Dict, action: Action, consensus: float) -> str:
        """Generate human-readable summary"""

        consensus_desc = "strong" if consensus > 0.7 else "moderate" if consensus > 0.4 else "weak"

        summary = f"Analysis of {asset} shows {consensus_desc} consensus ({consensus:.0%}) "

        if action in [Action.STRONG_BUY, Action.BUY]:
            summary += "favoring a BULLISH outlook. "
        elif action in [Action.STRONG_SELL, Action.SELL]:
            summary += "favoring a BEARISH outlook. "
        else:
            summary += "with MIXED signals - no clear direction. "

        # Add highlights from each agent
        tech_action = opinions['technical'].action.value
        news_action = opinions['news'].action.value
        social_action = opinions['social'].action.value

        summary += f"Technical analysis says {tech_action}, "
        summary += f"news sentiment is {news_action}, "
        summary += f"and social sentiment shows {social_action}. "

        if consensus < 0.4:
            summary += "⚠️ Low consensus suggests waiting for clearer signals."

        return summary

    def _extract_key_reasons(self, opinions: Dict, action: Action) -> List[str]:
        """Extract the most important reasons for the recommendation"""
        reasons = []

        for agent_name, opinion in opinions.items():
            # Get the most relevant factors from each agent
            if opinion.key_factors:
                for factor in opinion.key_factors[:2]:  # Top 2 from each
                    # Only include factors that support the final action
                    if action in [Action.BUY, Action.STRONG_BUY]:
                        if any(word in factor.lower() for word in ['bullish', 'support', 'positive', 'buy', 'opportunity', 'oversold']):
                            reasons.append(f"[{agent_name.title()}] {factor}")
                    elif action in [Action.SELL, Action.STRONG_SELL]:
                        if any(word in factor.lower() for word in ['bearish', 'resistance', 'negative', 'sell', 'risk', 'overbought']):
                            reasons.append(f"[{agent_name.title()}] {factor}")
                    else:
                        reasons.append(f"[{agent_name.title()}] {factor}")

        return reasons[:6]  # Top 6 reasons

    def _identify_opportunity_and_risk(self, opinions: Dict) -> tuple:
        """Identify the primary opportunity and risk"""

        opportunities = []
        risks = []

        # From technical
        tech = opinions['technical']
        if tech.indicators.get('rsi_signal') == 'OVERSOLD':
            opportunities.append("RSI oversold - potential bounce opportunity")
        if tech.indicators.get('rsi_signal') == 'OVERBOUGHT':
            risks.append("RSI overbought - potential pullback risk")
        if 'VOLATILITY_SQUEEZE' in tech.indicators.get('patterns', []):
            opportunities.append("Volatility squeeze - big move likely")

        # From news
        news = opinions['news']
        if news.indicators.get('opportunities'):
            opportunities.extend(news.indicators['opportunities'][:1])
        if news.indicators.get('risks'):
            risks.extend(news.indicators['risks'][:1])

        # From social
        social = opinions['social']
        if social.indicators.get('fomo_level', 0) > 0.6:
            risks.append("High FOMO - potential local top")
        if social.indicators.get('fud_level', 0) > 0.6:
            opportunities.append("High FUD - potential capitulation/bottom")

        # From risk
        risk_agent = opinions['risk']
        if risk_agent.indicators.get('risk_level') == 'EXTREME':
            risks.append("Extreme risk level - reduce position size")

        primary_opportunity = opportunities[0] if opportunities else "No clear opportunity identified - wait for setup"
        primary_risk = risks[0] if risks else "Standard market risk applies"

        return primary_opportunity, primary_risk

    def _determine_position_guidance(self, opinions: Dict, action: Action) -> Dict:
        """Determine specific position guidance"""

        risk_opinion = opinions['risk']
        tech_opinion = opinions['technical']

        # Get from risk agent
        position_sizing = risk_opinion.indicators.get('position_sizing', {})
        size_pct = position_sizing.get('pct_of_portfolio', 10)

        # Stop loss and take profit from risk agent
        stop_loss = risk_opinion.indicators.get('stop_loss_pct', 0.03) * 100
        take_profit = risk_opinion.indicators.get('take_profit_pct', 0.06) * 100

        # Entry timing from technical
        entry = tech_opinion.entry_timing if tech_opinion.entry_timing else "Wait for confirmation"

        # Exit based on action
        if action in [Action.STRONG_SELL, Action.SELL]:
            exit_guidance = "Consider exiting current positions"
        elif action == Action.HOLD:
            exit_guidance = "Hold current positions, no new entries"
        else:
            exit_guidance = f"Take profit at +{take_profit:.0f}% or stop loss at -{stop_loss:.0f}%"

        # Hold time (most conservative from agents)
        hold_times = [op.suggested_hold_time for op in opinions.values() if op.suggested_hold_time]
        hold_time = hold_times[0] if hold_times else "8-24 hours"

        return {
            'entry': entry,
            'exit': exit_guidance,
            'size': size_pct,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'hold_time': hold_time
        }

    def _generate_learning_points(self, opinions: Dict, action: Action) -> List[str]:
        """Generate educational points about this analysis"""

        points = []

        # Technical lessons
        tech = opinions['technical']
        rsi = tech.indicators.get('rsi', 50)
        if rsi < 30:
            points.append(f"📚 RSI at {rsi:.0f} is OVERSOLD. RSI below 30 historically indicates selling exhaustion - buyers often step in.")
        elif rsi > 70:
            points.append(f"📚 RSI at {rsi:.0f} is OVERBOUGHT. RSI above 70 suggests potential pullback as buyers become exhausted.")

        trend = tech.indicators.get('trend')
        if trend == 'BULLISH':
            points.append("📚 TREND: Price above key moving averages = bullish trend. Trading WITH the trend has higher success rate.")
        elif trend == 'BEARISH':
            points.append("📚 TREND: Price below key moving averages = bearish trend. Fighting the trend is risky.")

        # News lessons
        news = opinions['news']
        if news.indicators.get('high_impact_count', 0) > 2:
            points.append("📚 NEWS: Multiple high-impact news events increase volatility. Consider smaller positions during news-heavy periods.")

        # Social lessons
        social = opinions['social']
        if social.indicators.get('contrarian_signal'):
            points.append("📚 CONTRARIAN: Extreme social sentiment often marks turning points. 'Be fearful when others are greedy, greedy when others are fearful.'")

        # Risk lessons
        risk = opinions['risk']
        if risk.indicators.get('risk_level') in ['HIGH', 'EXTREME']:
            points.append("📚 RISK: High volatility = reduce position size. Never risk more than 1-2% of portfolio on a single trade.")

        # Consensus lesson
        if action == Action.HOLD:
            points.append("📚 PATIENCE: When signals conflict, the best trade is often NO trade. Wait for clearer setups.")

        return points[:4]

    def _generate_watch_list(self, opinions: Dict) -> List[str]:
        """Generate list of things to watch"""

        watch = []

        # From technical
        tech = opinions['technical']
        support = tech.indicators.get('support')
        resistance = tech.indicators.get('resistance')
        if support:
            watch.append(f"👀 Watch support level at ${support:,.2f}")
        if resistance:
            watch.append(f"👀 Watch resistance level at ${resistance:,.2f}")

        # From news
        news = opinions['news']
        themes = news.indicators.get('key_themes', [])
        if themes:
            watch.append(f"👀 Monitor news on: {', '.join(themes[:2])}")

        # From social
        social = opinions['social']
        if social.indicators.get('fomo_level', 0) > 0.5:
            watch.append("👀 Watch for FOMO exhaustion (potential top)")
        if social.indicators.get('fud_level', 0) > 0.5:
            watch.append("👀 Watch for FUD exhaustion (potential bottom)")

        # From risk
        risk = opinions['risk']
        vol_pct = risk.indicators.get('volatility_percentile', 50)
        if vol_pct > 70:
            watch.append(f"👀 Volatility elevated ({vol_pct:.0f} percentile) - watch for breakout")

        return watch[:5]

    def _collect_warnings(self, opinions: Dict, consensus: float) -> List[str]:
        """Collect all warnings from agents"""

        warnings = []

        # Low consensus warning
        if consensus < 0.4:
            warnings.append("⚠️ LOW CONSENSUS: Agents disagree significantly - higher uncertainty")

        # Collect from all agents
        for opinion in opinions.values():
            warnings.extend(opinion.warnings)

        # Deduplicate and limit
        unique_warnings = list(dict.fromkeys(warnings))
        return unique_warnings[:6]

    def get_all_teaching_content(self) -> Dict[str, Any]:
        """Get educational content from all agents"""
        return {
            'technical': self.technical_agent.get_teaching_content(),
            'news': self.news_agent.get_teaching_content(),
            'social': self.social_agent.get_teaching_content(),
            'risk': self.risk_agent.get_teaching_content(),
            'fundamental': self.fundamental_agent.get_teaching_content()
        }


# Global coordinator instance
coordinator = AgentCoordinator()
