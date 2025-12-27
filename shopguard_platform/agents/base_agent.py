"""
Base Agent Class
================
Foundation for all specialized trading agents.
Each agent analyzes markets from their specialized perspective.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class Confidence(Enum):
    """Confidence levels for agent opinions"""
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5

    @property
    def weight(self) -> float:
        return self.value / 5.0


class Action(Enum):
    """Recommended actions"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    WAIT = "WAIT"  # Wait for better entry

    @property
    def score(self) -> float:
        scores = {
            "STRONG_BUY": 1.0,
            "BUY": 0.6,
            "HOLD": 0.0,
            "WAIT": -0.1,
            "SELL": -0.6,
            "STRONG_SELL": -1.0
        }
        return scores[self.value]


@dataclass
class AgentOpinion:
    """
    Structured opinion from an agent about an asset.
    Contains the recommendation, reasoning, and supporting data.
    """
    agent_name: str
    asset: str
    action: Action
    confidence: Confidence

    # Reasoning - WHY this recommendation
    reasoning: str
    key_factors: List[str]

    # Timeframe recommendation
    suggested_hold_time: str  # e.g., "4-8 hours", "1-2 days"
    entry_timing: str  # e.g., "Now", "Wait for pullback to $X"

    # Price targets
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None

    # Risk/Reward
    risk_reward_ratio: Optional[float] = None
    win_probability: Optional[float] = None

    # Supporting data
    indicators: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent_name,
            "asset": self.asset,
            "action": self.action.value,
            "confidence": self.confidence.name,
            "confidence_weight": self.confidence.weight,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "suggested_hold_time": self.suggested_hold_time,
            "entry_timing": self.entry_timing,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "risk_reward_ratio": self.risk_reward_ratio,
            "win_probability": self.win_probability,
            "indicators": self.indicators,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat()
        }


class BaseAgent:
    """
    Base class for all trading agents.
    Each agent specializes in a specific type of analysis.
    """

    def __init__(self, name: str, specialty: str):
        self.name = name
        self.specialty = specialty
        self.last_analysis = {}

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """
        Analyze an asset and provide an opinion.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement analyze()")

    def explain(self, opinion: AgentOpinion) -> str:
        """
        Generate a detailed explanation of the opinion.
        Used for teaching the user.
        """
        explanation = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{self.name} Analysis for {opinion.asset}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOMMENDATION: {opinion.action.value}
CONFIDENCE: {opinion.confidence.name} ({opinion.confidence.weight:.0%})

WHY THIS RECOMMENDATION:
{opinion.reasoning}

KEY FACTORS:
"""
        for i, factor in enumerate(opinion.key_factors, 1):
            explanation += f"  {i}. {factor}\n"

        explanation += f"""
SUGGESTED ACTION:
  • Entry Timing: {opinion.entry_timing}
  • Hold Duration: {opinion.suggested_hold_time}
"""

        if opinion.entry_price:
            explanation += f"  • Entry Price: ${opinion.entry_price:,.2f}\n"
        if opinion.target_price:
            explanation += f"  • Target Price: ${opinion.target_price:,.2f}\n"
        if opinion.stop_loss_price:
            explanation += f"  • Stop Loss: ${opinion.stop_loss_price:,.2f}\n"
        if opinion.risk_reward_ratio:
            explanation += f"  • Risk/Reward Ratio: 1:{opinion.risk_reward_ratio:.1f}\n"

        if opinion.warnings:
            explanation += "\n⚠️ WARNINGS:\n"
            for warning in opinion.warnings:
                explanation += f"  • {warning}\n"

        return explanation

    def get_teaching_content(self) -> Dict[str, str]:
        """
        Return educational content about this agent's specialty.
        Used by the teaching system.
        """
        return {
            "name": self.name,
            "specialty": self.specialty,
            "description": "Base agent - no specific teaching content."
        }
