"""
Proximal Policy Optimization (PPO) Agent for Trading

PPO is a policy gradient method that:
1. Is more stable than vanilla policy gradient
2. Can handle continuous action spaces (position sizing)
3. Uses clipped objectives to prevent destructive updates

For trading, the RL formulation is:
- State: Market features, current position, account state
- Action: Position change (buy/sell/hold amount)
- Reward: Risk-adjusted returns (Sharpe-like)

KEY INSIGHT: The reward function IS the strategy.
Reward design is more important than architecture.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Normal
from typing import Tuple, Dict, Optional, List
import numpy as np
from dataclasses import dataclass


@dataclass
class PPOConfig:
    """Configuration for PPO agent."""
    # Network architecture
    hidden_dim: int = 128
    num_layers: int = 2

    # PPO hyperparameters
    clip_epsilon: float = 0.2        # Clipping parameter
    value_coef: float = 0.5          # Value loss coefficient
    entropy_coef: float = 0.01       # Entropy bonus coefficient
    max_grad_norm: float = 0.5       # Gradient clipping

    # Training
    gamma: float = 0.99              # Discount factor
    gae_lambda: float = 0.95         # GAE lambda
    learning_rate: float = 3e-4
    batch_size: int = 64
    n_epochs: int = 10               # Epochs per update

    # Trading-specific
    max_position: float = 1.0        # Maximum position size
    transaction_cost: float = 0.001  # Transaction cost (0.1%)
    risk_free_rate: float = 0.0      # Risk-free rate (annualized)


class ActorCritic(nn.Module):
    """
    Actor-Critic network for trading.

    Actor: Outputs action distribution (mean and std of position)
    Critic: Estimates state value (expected future rewards)
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = 1,
        config: PPOConfig = None
    ):
        super().__init__()

        self.config = config or PPOConfig()
        hidden_dim = self.config.hidden_dim

        # Shared feature extractor
        self.feature_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU()
        )

        # Actor head (policy)
        self.actor_mean = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
            nn.Tanh()  # Bound actions to [-1, 1]
        )

        # Learnable log standard deviation
        self.actor_log_std = nn.Parameter(torch.zeros(action_dim))

        # Critic head (value function)
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Returns:
            Tuple of (action_mean, state_value)
        """
        features = self.feature_net(state)
        action_mean = self.actor_mean(features)
        value = self.critic(features)
        return action_mean, value

    def get_action(
        self,
        state: torch.Tensor,
        deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Sample action from policy.

        Returns:
            Tuple of (action, log_prob, value)
        """
        action_mean, value = self.forward(state)
        action_std = torch.exp(self.actor_log_std)

        if deterministic:
            action = action_mean
            log_prob = torch.zeros_like(action)
        else:
            dist = Normal(action_mean, action_std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)

        # Clamp action to valid range
        action = torch.clamp(action, -1.0, 1.0)

        return action, log_prob, value

    def evaluate_actions(
        self,
        states: torch.Tensor,
        actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Evaluate actions for PPO update.

        Returns:
            Tuple of (log_probs, values, entropy)
        """
        action_mean, values = self.forward(states)
        action_std = torch.exp(self.actor_log_std)

        dist = Normal(action_mean, action_std)
        log_probs = dist.log_prob(actions).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)

        return log_probs, values, entropy


class TradingPPOAgent:
    """
    PPO Agent specifically designed for trading.

    Key features:
    1. Sharpe-ratio based reward shaping
    2. Transaction cost modeling
    3. Drawdown penalty
    4. Position limits
    """

    def __init__(
        self,
        state_dim: int,
        config: PPOConfig = None,
        device: str = "cpu"
    ):
        """
        Initialize trading agent.

        Args:
            state_dim: Dimension of state space
            config: PPO configuration
            device: Torch device
        """
        self.config = config or PPOConfig()
        self.device = device

        # Initialize networks
        self.actor_critic = ActorCritic(state_dim, 1, self.config).to(device)

        # Optimizer
        self.optimizer = torch.optim.Adam(
            self.actor_critic.parameters(),
            lr=self.config.learning_rate
        )

        # Experience buffer
        self.buffer = RolloutBuffer()

        # Trading state
        self.current_position = 0.0
        self.peak_value = 1.0
        self.cumulative_returns = []

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[float, dict]:
        """
        Select trading action.

        Args:
            state: Current state observation
            deterministic: Use mean action (for evaluation)

        Returns:
            Tuple of (position_change, info_dict)
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob, value = self.actor_critic.get_action(
                state_tensor, deterministic
            )

        action = action.cpu().numpy().flatten()[0]
        log_prob = log_prob.cpu().numpy().flatten()[0]
        value = value.cpu().numpy().flatten()[0]

        # Convert action to position
        # Action in [-1, 1] maps to position in [-max_pos, max_pos]
        target_position = action * self.config.max_position
        position_change = target_position - self.current_position

        info = {
            "target_position": target_position,
            "position_change": position_change,
            "value_estimate": value,
            "log_prob": log_prob
        }

        return position_change, info

    def compute_reward(
        self,
        returns: float,
        position_change: float,
        current_value: float
    ) -> float:
        """
        Compute shaped reward for trading.

        Reward components:
        1. Base return: Profit from position
        2. Transaction cost penalty: Discourage excessive trading
        3. Drawdown penalty: Discourage large drawdowns
        4. Risk adjustment: Penalize high variance

        This reward function encourages:
        - Profitable trades
        - Low turnover
        - Stable equity curve
        """
        # Base reward: raw return
        reward = returns

        # Transaction cost penalty
        cost = abs(position_change) * self.config.transaction_cost
        reward -= cost

        # Drawdown penalty
        if current_value > self.peak_value:
            self.peak_value = current_value
        drawdown = (self.peak_value - current_value) / self.peak_value
        drawdown_penalty = 0.5 * (drawdown ** 2)  # Quadratic penalty
        reward -= drawdown_penalty

        # Risk adjustment (penalize high variance)
        self.cumulative_returns.append(returns)
        if len(self.cumulative_returns) > 20:
            recent_vol = np.std(self.cumulative_returns[-20:])
            vol_penalty = 0.1 * recent_vol
            reward -= vol_penalty

        return reward

    def store_transition(
        self,
        state: np.ndarray,
        action: float,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        log_prob: float,
        value: float
    ):
        """Store experience in buffer."""
        self.buffer.add(state, action, reward, next_state, done, log_prob, value)

    def update(self) -> Dict[str, float]:
        """
        Update policy using PPO.

        Returns:
            Dictionary of training metrics
        """
        if len(self.buffer) < self.config.batch_size:
            return {}

        # Get all data from buffer
        states, actions, rewards, next_states, dones, old_log_probs, old_values = \
            self.buffer.get_all()

        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).unsqueeze(-1).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        old_log_probs = torch.FloatTensor(old_log_probs).unsqueeze(-1).to(self.device)
        old_values = torch.FloatTensor(old_values).unsqueeze(-1).to(self.device)

        # Compute advantages using GAE
        advantages, returns = self._compute_gae(rewards, old_values, dones)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0

        for epoch in range(self.config.n_epochs):
            # Get current policy outputs
            log_probs, values, entropy = self.actor_critic.evaluate_actions(states, actions)

            # Policy loss (clipped surrogate objective)
            ratio = torch.exp(log_probs - old_log_probs)
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()

            # Value loss
            value_loss = F.mse_loss(values, returns)

            # Total loss
            loss = (
                policy_loss +
                self.config.value_coef * value_loss -
                self.config.entropy_coef * entropy.mean()
            )

            # Update
            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(
                self.actor_critic.parameters(), self.config.max_grad_norm
            )
            self.optimizer.step()

            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
            total_entropy += entropy.mean().item()

        # Clear buffer
        self.buffer.clear()

        return {
            "policy_loss": total_policy_loss / self.config.n_epochs,
            "value_loss": total_value_loss / self.config.n_epochs,
            "entropy": total_entropy / self.config.n_epochs
        }

    def _compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute Generalized Advantage Estimation (GAE).

        GAE provides lower variance advantage estimates by
        exponentially weighting TD residuals.

        δ_t = r_t + γV(s_{t+1}) - V(s_t)
        A_t = Σ_{l=0}^{∞} (γλ)^l δ_{t+l}
        """
        gamma = self.config.gamma
        gae_lambda = self.config.gae_lambda

        advantages = torch.zeros_like(rewards)
        last_advantage = 0

        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]

            delta = rewards[t] + gamma * next_value * (1 - dones[t]) - values[t]
            advantages[t] = last_advantage = delta + gamma * gae_lambda * (1 - dones[t]) * last_advantage

        returns = advantages + values.squeeze()

        return advantages.unsqueeze(-1), returns.unsqueeze(-1)

    def save(self, path: str):
        """Save agent state."""
        torch.save({
            "actor_critic": self.actor_critic.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "config": self.config
        }, path)

    def load(self, path: str):
        """Load agent state."""
        checkpoint = torch.load(path, map_location=self.device)
        self.actor_critic.load_state_dict(checkpoint["actor_critic"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.config = checkpoint["config"]


class RolloutBuffer:
    """Simple buffer for storing rollout experiences."""

    def __init__(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.next_states = []
        self.dones = []
        self.log_probs = []
        self.values = []

    def add(self, state, action, reward, next_state, done, log_prob, value):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.next_states.append(next_state)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)

    def get_all(self):
        return (
            np.array(self.states),
            np.array(self.actions),
            np.array(self.rewards),
            np.array(self.next_states),
            np.array(self.dones),
            np.array(self.log_probs),
            np.array(self.values)
        )

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.next_states.clear()
        self.dones.clear()
        self.log_probs.clear()
        self.values.clear()

    def __len__(self):
        return len(self.states)


# =============================================================================
# REWARD FUNCTION DESIGN (The most important part!)
# =============================================================================

class RewardShaper:
    """
    Reward function design for trading RL.

    THE REWARD FUNCTION IS THE STRATEGY.

    Bad reward = bad strategy, no matter how good the network.

    Common mistakes:
    1. Using raw PnL (ignores risk)
    2. Ignoring transaction costs (learns to overtrade)
    3. Ignoring drawdowns (learns to take tail risks)
    4. Short-term focus (learns noise, not signal)
    """

    def __init__(
        self,
        transaction_cost: float = 0.001,
        risk_free_rate: float = 0.0,
        target_vol: float = 0.15,
        drawdown_penalty: float = 2.0,
        turnover_penalty: float = 0.5
    ):
        self.transaction_cost = transaction_cost
        self.risk_free_rate = risk_free_rate
        self.target_vol = target_vol
        self.drawdown_penalty = drawdown_penalty
        self.turnover_penalty = turnover_penalty

        # Running statistics
        self.returns_history = []
        self.peak_value = 1.0

    def compute_reward(
        self,
        portfolio_return: float,
        position_change: float,
        portfolio_value: float
    ) -> float:
        """
        Compute shaped reward.

        Reward = Sharpe-like component - costs - drawdown penalty - turnover penalty

        This encourages:
        1. High risk-adjusted returns (not just high returns)
        2. Low turnover (fewer trades)
        3. Controlled drawdowns (stable equity curve)
        """
        # Update history
        self.returns_history.append(portfolio_return)
        if len(self.returns_history) > 252:
            self.returns_history.pop(0)

        # Update peak for drawdown calculation
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value

        # Component 1: Risk-adjusted return
        if len(self.returns_history) >= 20:
            recent_mean = np.mean(self.returns_history[-20:])
            recent_std = np.std(self.returns_history[-20:]) + 1e-8
            sharpe_component = recent_mean / recent_std
        else:
            sharpe_component = portfolio_return

        # Component 2: Transaction costs
        cost_component = abs(position_change) * self.transaction_cost

        # Component 3: Drawdown penalty
        drawdown = (self.peak_value - portfolio_value) / self.peak_value
        drawdown_component = self.drawdown_penalty * (drawdown ** 2)

        # Component 4: Turnover penalty (encourages holding)
        turnover_component = self.turnover_penalty * abs(position_change)

        # Final reward
        reward = sharpe_component - cost_component - drawdown_component - turnover_component

        return reward

    def reset(self):
        """Reset for new episode."""
        self.returns_history.clear()
        self.peak_value = 1.0
