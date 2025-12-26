"""
Trading Environment for Reinforcement Learning

Implements a gym-style environment for backtesting RL trading agents.

CRITICAL: This is a simulation. Real trading has:
- Execution delays
- Slippage
- Market impact
- Partial fills
- Queue position in order book

Always test with realistic friction before live trading.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List
from enum import Enum


class ActionType(Enum):
    """Trading action types."""
    CONTINUOUS = "continuous"    # Position sizing (e.g., -1 to 1)
    DISCRETE = "discrete"        # Buy/Hold/Sell


@dataclass
class TradingEnvConfig:
    """Configuration for trading environment."""
    # Data
    lookback_window: int = 60        # Number of past observations
    features: List[str] = None       # Feature names

    # Trading parameters
    initial_capital: float = 100000
    max_position: float = 1.0        # Max position as fraction of capital
    transaction_cost: float = 0.001  # 10 bps round-trip
    slippage: float = 0.0005         # 5 bps slippage

    # Environment settings
    action_type: ActionType = ActionType.CONTINUOUS
    episode_length: int = 252        # Trading days per episode
    reward_scaling: float = 100.0    # Scale rewards for numerical stability


class TradingEnvironment:
    """
    Trading environment for RL agents.

    Follows OpenAI Gym interface:
    - reset(): Start new episode
    - step(action): Take action, return (obs, reward, done, info)
    - render(): Visualize (optional)
    """

    def __init__(
        self,
        prices: np.ndarray,
        features: np.ndarray,
        config: TradingEnvConfig = None
    ):
        """
        Initialize trading environment.

        Args:
            prices: Asset prices (T,)
            features: Feature matrix (T, n_features)
            config: Environment configuration
        """
        self.prices = prices
        self.features = features
        self.config = config or TradingEnvConfig()

        # Compute returns
        self.returns = np.diff(prices) / prices[:-1]

        # Environment state
        self.current_step = 0
        self.start_step = 0
        self.portfolio_value = self.config.initial_capital
        self.position = 0.0
        self.cash = self.config.initial_capital

        # History for metrics
        self.portfolio_history = []
        self.position_history = []
        self.action_history = []

        # Episode boundaries
        self.max_steps = len(prices) - self.config.lookback_window - 1

    @property
    def observation_space_dim(self) -> int:
        """Dimension of observation space."""
        # Features + position + returns + portfolio value
        return self.features.shape[1] + 3

    @property
    def action_space_dim(self) -> int:
        """Dimension of action space."""
        if self.config.action_type == ActionType.CONTINUOUS:
            return 1  # Position size in [-1, 1]
        else:
            return 3  # Buy, Hold, Sell

    def reset(self, start_step: Optional[int] = None) -> np.ndarray:
        """
        Reset environment for new episode.

        Args:
            start_step: Optional starting point (for curriculum learning)

        Returns:
            Initial observation
        """
        # Random start point if not specified
        if start_step is None:
            max_start = self.max_steps - self.config.episode_length
            start_step = np.random.randint(
                self.config.lookback_window,
                max(self.config.lookback_window + 1, max_start)
            )

        self.start_step = start_step
        self.current_step = start_step
        self.portfolio_value = self.config.initial_capital
        self.position = 0.0
        self.cash = self.config.initial_capital

        # Clear history
        self.portfolio_history = [self.portfolio_value]
        self.position_history = [0.0]
        self.action_history = []

        return self._get_observation()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Execute one step in the environment.

        Args:
            action: Agent's action

        Returns:
            Tuple of (observation, reward, done, info)
        """
        # Parse action
        if self.config.action_type == ActionType.CONTINUOUS:
            target_position = float(np.clip(action, -1, 1))
        else:
            # Discrete: 0=sell, 1=hold, 2=buy
            action_map = {0: -1.0, 1: 0.0, 2: 1.0}
            target_position = action_map.get(int(action), 0.0)

        # Scale to max position
        target_position *= self.config.max_position

        # Calculate position change
        position_change = target_position - self.position

        # Get current price and next return
        current_price = self.prices[self.current_step]
        next_return = self.returns[self.current_step]

        # Execute trade with costs
        trade_value = abs(position_change) * self.portfolio_value
        transaction_cost = trade_value * self.config.transaction_cost
        slippage_cost = trade_value * self.config.slippage

        total_cost = transaction_cost + slippage_cost

        # Update position
        old_position = self.position
        self.position = target_position

        # Calculate portfolio return
        # Position return + cash return - costs
        position_return = self.position * next_return
        portfolio_return = position_return - total_cost / self.portfolio_value

        # Update portfolio value
        old_value = self.portfolio_value
        self.portfolio_value *= (1 + portfolio_return)

        # Compute reward
        reward = self._compute_reward(
            portfolio_return,
            position_change,
            self.portfolio_value,
            old_value
        )

        # Update histories
        self.portfolio_history.append(self.portfolio_value)
        self.position_history.append(self.position)
        self.action_history.append(action)

        # Advance step
        self.current_step += 1

        # Check termination
        done = (
            self.current_step >= self.start_step + self.config.episode_length or
            self.current_step >= self.max_steps or
            self.portfolio_value < self.config.initial_capital * 0.5  # Ruin
        )

        # Build info dict
        info = {
            "portfolio_value": self.portfolio_value,
            "position": self.position,
            "return": portfolio_return,
            "transaction_cost": transaction_cost,
            "slippage": slippage_cost,
            "step": self.current_step
        }

        return self._get_observation(), reward, done, info

    def _get_observation(self) -> np.ndarray:
        """
        Construct observation from current state.

        Observation includes:
        - Lookback window of features
        - Current position
        - Recent returns
        - Normalized portfolio value
        """
        # Get feature window
        start = self.current_step - self.config.lookback_window
        end = self.current_step
        feature_window = self.features[start:end]

        # Flatten feature window
        flat_features = feature_window.flatten()

        # Add state information
        position_info = np.array([
            self.position,
            self.returns[max(0, self.current_step - 1)],  # Last return
            self.portfolio_value / self.config.initial_capital - 1  # Normalized PnL
        ])

        return np.concatenate([flat_features, position_info])

    def _compute_reward(
        self,
        portfolio_return: float,
        position_change: float,
        new_value: float,
        old_value: float
    ) -> float:
        """
        Compute reward for the step.

        Using differential Sharpe ratio formulation for online learning.
        """
        # Differential Sharpe ratio
        # Approximates contribution to Sharpe from this step
        n = len(self.portfolio_history)

        if n < 2:
            return portfolio_return * self.config.reward_scaling

        returns = np.diff(self.portfolio_history) / np.array(self.portfolio_history[:-1])
        mean_return = np.mean(returns)
        std_return = np.std(returns) + 1e-8

        # Differential Sharpe
        delta_mean = (portfolio_return - mean_return) / n
        delta_var = ((portfolio_return - mean_return) ** 2 - std_return ** 2) / n

        if std_return > 0:
            diff_sharpe = (delta_mean - 0.5 * mean_return * delta_var / (std_return ** 2)) / std_return
        else:
            diff_sharpe = portfolio_return

        return diff_sharpe * self.config.reward_scaling

    def get_episode_metrics(self) -> Dict[str, float]:
        """Calculate episode performance metrics."""
        if len(self.portfolio_history) < 2:
            return {}

        values = np.array(self.portfolio_history)
        returns = np.diff(values) / values[:-1]

        # Total return
        total_return = (values[-1] - values[0]) / values[0]

        # Sharpe ratio (annualized)
        if np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(values)
        drawdown = (peak - values) / peak
        max_drawdown = np.max(drawdown)

        # Calmar ratio
        calmar = total_return / max_drawdown if max_drawdown > 0 else 0.0

        # Win rate
        win_rate = np.mean(returns > 0)

        # Turnover
        positions = np.array(self.position_history)
        turnover = np.mean(np.abs(np.diff(positions)))

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
            "avg_turnover": turnover,
            "final_value": values[-1]
        }


class MultiAssetEnvironment(TradingEnvironment):
    """
    Extension for multi-asset trading.

    Handles portfolio of assets with:
    - Cross-asset correlations
    - Portfolio constraints (long-only, gross exposure, etc.)
    - Sector/factor exposure limits
    """

    def __init__(
        self,
        prices: np.ndarray,      # (T, n_assets)
        features: np.ndarray,    # (T, n_assets, n_features)
        config: TradingEnvConfig = None
    ):
        self.n_assets = prices.shape[1]
        self.multi_prices = prices
        self.multi_features = features

        # Use first asset for base class initialization
        super().__init__(prices[:, 0], features[:, 0, :], config)

        # Multi-asset state
        self.positions = np.zeros(self.n_assets)

    def reset(self, start_step: Optional[int] = None) -> np.ndarray:
        """Reset for multi-asset."""
        obs = super().reset(start_step)
        self.positions = np.zeros(self.n_assets)
        return self._get_multi_observation()

    def _get_multi_observation(self) -> np.ndarray:
        """Get observation for all assets."""
        start = self.current_step - self.config.lookback_window
        end = self.current_step

        # Features for all assets
        all_features = []
        for asset in range(self.n_assets):
            asset_features = self.multi_features[start:end, asset, :]
            all_features.append(asset_features.flatten())

        # Current positions
        all_features.append(self.positions)

        # Portfolio-level info
        all_features.append(np.array([
            self.portfolio_value / self.config.initial_capital - 1
        ]))

        return np.concatenate(all_features)

    @property
    def action_space_dim(self) -> int:
        """Multi-asset action space."""
        return self.n_assets  # Position for each asset
