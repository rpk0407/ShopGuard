"""
Reinforcement Learning Trading Agent

A self-learning trading agent that:
- Learns optimal trading policies through experience
- Uses Deep Q-Learning (DQN) with experience replay
- Adapts to changing market conditions
- Balances exploration vs exploitation
- Learns risk management automatically

This is a REAL RL agent that learns from trading outcomes.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import random


class TradingAction(Enum):
    """Possible trading actions"""
    HOLD = 0
    BUY = 1
    SELL = 2
    STRONG_BUY = 3
    STRONG_SELL = 4


@dataclass
class Experience:
    """Single experience tuple for replay buffer"""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


@dataclass
class TradingState:
    """State representation for the RL agent"""
    # Price features
    price_change_1: float
    price_change_5: float
    price_change_10: float
    price_change_20: float

    # Technical indicators
    rsi: float
    macd: float
    bollinger_position: float
    volume_ratio: float

    # Position features
    current_position: float  # -1 to 1
    unrealized_pnl: float
    time_in_position: int

    # Market features
    volatility: float
    trend_strength: float
    momentum: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.price_change_1, self.price_change_5,
            self.price_change_10, self.price_change_20,
            self.rsi, self.macd, self.bollinger_position,
            self.volume_ratio, self.current_position,
            self.unrealized_pnl, self.time_in_position,
            self.volatility, self.trend_strength, self.momentum
        ])


class NeuralNetwork:
    """Simple neural network for Q-value approximation"""

    def __init__(self, input_size: int, hidden_sizes: List[int], output_size: int):
        self.layers = []
        self.biases = []

        sizes = [input_size] + hidden_sizes + [output_size]

        for i in range(len(sizes) - 1):
            # He initialization
            scale = np.sqrt(2.0 / sizes[i])
            self.layers.append(np.random.randn(sizes[i], sizes[i+1]) * scale)
            self.biases.append(np.zeros((1, sizes[i+1])))

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass"""
        out = x
        for i, (w, b) in enumerate(zip(self.layers, self.biases)):
            out = np.dot(out, w) + b
            if i < len(self.layers) - 1:  # ReLU for hidden layers
                out = np.maximum(0, out)
        return out

    def copy_from(self, other: 'NeuralNetwork'):
        """Copy weights from another network"""
        for i in range(len(self.layers)):
            self.layers[i] = other.layers[i].copy()
            self.biases[i] = other.biases[i].copy()


class ReplayBuffer:
    """Experience replay buffer for DQN"""

    def __init__(self, capacity: int = 100000):
        self.buffer = deque(maxlen=capacity)

    def push(self, experience: Experience):
        """Add experience to buffer"""
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch"""
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self):
        return len(self.buffer)


class PrioritizedReplayBuffer:
    """Prioritized experience replay - samples important experiences more often"""

    def __init__(self, capacity: int = 100000, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = []
        self.priorities = np.zeros(capacity)
        self.position = 0
        self.size = 0

    def push(self, experience: Experience, priority: float = 1.0):
        """Add experience with priority"""
        max_priority = self.priorities.max() if self.size > 0 else priority

        if self.size < self.capacity:
            self.buffer.append(experience)
            self.size += 1
        else:
            self.buffer[self.position] = experience

        self.priorities[self.position] = max_priority
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int, beta: float = 0.4) -> Tuple[List[Experience], np.ndarray, np.ndarray]:
        """Sample batch with importance sampling weights"""
        if self.size < batch_size:
            batch_size = self.size

        # Calculate sampling probabilities
        priorities = self.priorities[:self.size]
        probs = priorities ** self.alpha
        probs /= probs.sum()

        # Sample indices
        indices = np.random.choice(self.size, batch_size, p=probs, replace=False)

        # Calculate importance sampling weights
        weights = (self.size * probs[indices]) ** (-beta)
        weights /= weights.max()

        experiences = [self.buffer[i] for i in indices]

        return experiences, indices, weights

    def update_priorities(self, indices: np.ndarray, priorities: np.ndarray):
        """Update priorities after learning"""
        for idx, priority in zip(indices, priorities):
            self.priorities[idx] = priority + 1e-6


class DQNAgent:
    """
    Deep Q-Network Trading Agent

    Uses:
    - Double DQN for stable learning
    - Prioritized experience replay
    - Epsilon-greedy exploration with decay
    - Target network for stability
    """

    def __init__(
        self,
        state_size: int = 14,
        action_size: int = 5,
        hidden_sizes: List[int] = [128, 64, 32],
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        buffer_size: int = 100000,
        batch_size: int = 64,
        target_update_freq: int = 100
    ):
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq

        # Exploration parameters
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        # Networks
        self.q_network = NeuralNetwork(state_size, hidden_sizes, action_size)
        self.target_network = NeuralNetwork(state_size, hidden_sizes, action_size)
        self.target_network.copy_from(self.q_network)

        # Experience replay
        self.replay_buffer = PrioritizedReplayBuffer(buffer_size)

        # Training stats
        self.training_step = 0
        self.episode_rewards = []
        self.losses = []

    def get_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select action using epsilon-greedy policy"""
        if training and random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)

        q_values = self.q_network.forward(state.reshape(1, -1))
        return int(np.argmax(q_values[0]))

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for all actions"""
        return self.q_network.forward(state.reshape(1, -1))[0]

    def store_experience(self, state: np.ndarray, action: int, reward: float,
                         next_state: np.ndarray, done: bool):
        """Store experience in replay buffer"""
        experience = Experience(state, action, reward, next_state, done)

        # Calculate TD error for priority
        q_values = self.q_network.forward(state.reshape(1, -1))[0]
        next_q_values = self.target_network.forward(next_state.reshape(1, -1))[0]

        if done:
            td_target = reward
        else:
            td_target = reward + self.gamma * np.max(next_q_values)

        td_error = abs(td_target - q_values[action])

        self.replay_buffer.push(experience, td_error)

    def train_step(self) -> float:
        """Single training step"""
        if len(self.replay_buffer) < self.batch_size:
            return 0.0

        # Sample batch
        beta = min(1.0, 0.4 + self.training_step * 0.001)
        experiences, indices, weights = self.replay_buffer.sample(self.batch_size, beta)

        # Prepare batch
        states = np.array([e.state for e in experiences])
        actions = np.array([e.action for e in experiences])
        rewards = np.array([e.reward for e in experiences])
        next_states = np.array([e.next_state for e in experiences])
        dones = np.array([e.done for e in experiences])

        # Current Q values
        current_q = self.q_network.forward(states)

        # Next Q values (Double DQN: use online network to select, target to evaluate)
        next_q_online = self.q_network.forward(next_states)
        next_q_target = self.target_network.forward(next_states)

        best_actions = np.argmax(next_q_online, axis=1)
        next_q = next_q_target[np.arange(len(best_actions)), best_actions]

        # TD targets
        td_targets = rewards + self.gamma * next_q * (1 - dones)

        # TD errors
        td_errors = td_targets - current_q[np.arange(len(actions)), actions]

        # Update priorities
        self.replay_buffer.update_priorities(indices, np.abs(td_errors))

        # Loss (weighted by importance sampling)
        loss = np.mean(weights * td_errors ** 2)

        # Gradient update (simplified)
        target_q = current_q.copy()
        target_q[np.arange(len(actions)), actions] = td_targets

        # Simple gradient descent on output layer
        grad = (current_q - target_q) * weights.reshape(-1, 1)

        for i in range(len(self.q_network.layers) - 1, -1, -1):
            if i == len(self.q_network.layers) - 1:
                # Output layer
                layer_input = self._get_layer_input(states, i)
                self.q_network.layers[i] -= self.learning_rate * np.dot(layer_input.T, grad) / len(states)
                self.q_network.biases[i] -= self.learning_rate * np.mean(grad, axis=0, keepdims=True)

        self.training_step += 1
        self.losses.append(loss)

        # Update target network
        if self.training_step % self.target_update_freq == 0:
            self.target_network.copy_from(self.q_network)

        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        return loss

    def _get_layer_input(self, x: np.ndarray, layer_idx: int) -> np.ndarray:
        """Get input to specific layer"""
        out = x
        for i in range(layer_idx):
            out = np.dot(out, self.q_network.layers[i]) + self.q_network.biases[i]
            out = np.maximum(0, out)
        return out


class TradingEnvironment:
    """
    Trading environment for RL agent training.
    Simulates realistic market conditions.
    """

    def __init__(
        self,
        price_data: np.ndarray,
        volume_data: np.ndarray,
        initial_balance: float = 100000,
        transaction_cost: float = 0.001,
        max_position: float = 1.0
    ):
        self.price_data = price_data
        self.volume_data = volume_data
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.max_position = max_position

        self.reset()

    def reset(self) -> TradingState:
        """Reset environment to initial state"""
        self.current_step = 20  # Start with some history
        self.balance = self.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.time_in_position = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

        return self._get_state()

    def _get_state(self) -> TradingState:
        """Get current state representation"""
        prices = self.price_data[self.current_step-20:self.current_step+1]
        volumes = self.volume_data[self.current_step-20:self.current_step+1]

        current_price = prices[-1]

        # Price changes
        price_change_1 = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        price_change_5 = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        price_change_10 = (prices[-1] - prices[-10]) / prices[-10] if len(prices) >= 10 else 0
        price_change_20 = (prices[-1] - prices[-20]) / prices[-20] if len(prices) >= 20 else 0

        # RSI
        rsi = self._calculate_rsi(prices)

        # MACD
        macd = self._calculate_macd(prices)

        # Bollinger position
        bollinger_pos = self._calculate_bollinger_position(prices)

        # Volume ratio
        avg_volume = np.mean(volumes[:-1])
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1.0

        # Volatility
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) if len(returns) > 0 else 0

        # Trend strength
        trend_strength = price_change_20 / (volatility + 1e-6)

        # Momentum
        momentum = np.mean(returns[-5:]) if len(returns) >= 5 else 0

        # Position features
        if self.position != 0:
            unrealized_pnl = (current_price - self.entry_price) / self.entry_price * np.sign(self.position)
        else:
            unrealized_pnl = 0.0

        return TradingState(
            price_change_1=price_change_1,
            price_change_5=price_change_5,
            price_change_10=price_change_10,
            price_change_20=price_change_20,
            rsi=rsi,
            macd=macd,
            bollinger_position=bollinger_pos,
            volume_ratio=min(volume_ratio, 5.0),
            current_position=self.position,
            unrealized_pnl=unrealized_pnl,
            time_in_position=min(self.time_in_position, 100),
            volatility=volatility,
            trend_strength=trend_strength,
            momentum=momentum
        )

    def step(self, action: int) -> Tuple[TradingState, float, bool, Dict]:
        """Execute action and return new state, reward, done, info"""
        current_price = self.price_data[self.current_step]
        prev_portfolio_value = self._get_portfolio_value(current_price)

        # Execute action
        reward = self._execute_action(action, current_price)

        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.price_data) - 1

        # Get new state
        new_state = self._get_state()
        new_price = self.price_data[self.current_step]
        new_portfolio_value = self._get_portfolio_value(new_price)

        # Calculate reward based on portfolio change
        portfolio_return = (new_portfolio_value - prev_portfolio_value) / prev_portfolio_value
        reward += portfolio_return * 100  # Scale reward

        # Penalty for excessive trading
        if action != TradingAction.HOLD.value:
            reward -= 0.1

        # Update time in position
        if self.position != 0:
            self.time_in_position += 1
        else:
            self.time_in_position = 0

        info = {
            'portfolio_value': new_portfolio_value,
            'position': self.position,
            'total_trades': self.total_trades,
            'win_rate': self.winning_trades / max(1, self.total_trades)
        }

        return new_state, reward, done, info

    def _execute_action(self, action: int, current_price: float) -> float:
        """Execute trading action"""
        reward = 0.0

        if action == TradingAction.HOLD.value:
            pass

        elif action == TradingAction.BUY.value:
            if self.position <= 0:
                # Close short if any
                if self.position < 0:
                    pnl = (self.entry_price - current_price) / self.entry_price * abs(self.position)
                    reward += pnl
                    self.total_pnl += pnl
                    self.total_trades += 1
                    if pnl > 0:
                        self.winning_trades += 1

                # Open long
                self.position = 0.5
                self.entry_price = current_price * (1 + self.transaction_cost)
                self.time_in_position = 0

        elif action == TradingAction.SELL.value:
            if self.position >= 0:
                # Close long if any
                if self.position > 0:
                    pnl = (current_price - self.entry_price) / self.entry_price * self.position
                    reward += pnl
                    self.total_pnl += pnl
                    self.total_trades += 1
                    if pnl > 0:
                        self.winning_trades += 1

                # Open short
                self.position = -0.5
                self.entry_price = current_price * (1 - self.transaction_cost)
                self.time_in_position = 0

        elif action == TradingAction.STRONG_BUY.value:
            if self.position < self.max_position:
                if self.position < 0:
                    # Close short first
                    pnl = (self.entry_price - current_price) / self.entry_price * abs(self.position)
                    reward += pnl
                    self.total_pnl += pnl
                    self.total_trades += 1
                    if pnl > 0:
                        self.winning_trades += 1

                self.position = self.max_position
                self.entry_price = current_price * (1 + self.transaction_cost)
                self.time_in_position = 0

        elif action == TradingAction.STRONG_SELL.value:
            if self.position > -self.max_position:
                if self.position > 0:
                    # Close long first
                    pnl = (current_price - self.entry_price) / self.entry_price * self.position
                    reward += pnl
                    self.total_pnl += pnl
                    self.total_trades += 1
                    if pnl > 0:
                        self.winning_trades += 1

                self.position = -self.max_position
                self.entry_price = current_price * (1 - self.transaction_cost)
                self.time_in_position = 0

        return reward

    def _get_portfolio_value(self, current_price: float) -> float:
        """Calculate current portfolio value"""
        if self.position == 0:
            return self.balance

        position_value = abs(self.position) * self.initial_balance
        if self.position > 0:
            pnl = (current_price - self.entry_price) / self.entry_price
        else:
            pnl = (self.entry_price - current_price) / self.entry_price

        return self.balance + position_value * pnl

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 0.5

        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 1.0

        rs = avg_gain / avg_loss
        rsi = 1 - (1 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: np.ndarray) -> float:
        """Calculate MACD signal"""
        if len(prices) < 26:
            return 0

        ema_12 = self._ema(prices, 12)
        ema_26 = self._ema(prices, 26)

        macd_line = ema_12 - ema_26
        return macd_line / prices[-1]  # Normalize

    def _calculate_bollinger_position(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate position within Bollinger Bands (-1 to 1)"""
        if len(prices) < period:
            return 0

        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])

        if std == 0:
            return 0

        position = (prices[-1] - sma) / (2 * std)
        return max(-1, min(1, position))

    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(data) < period:
            return data[-1]

        multiplier = 2 / (period + 1)
        ema = data[-period]

        for price in data[-period+1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema


class RLTradingSystem:
    """
    Complete RL-based trading system.

    Combines:
    - DQN agent for decision making
    - Trading environment for training
    - Performance tracking
    - Live trading interface
    """

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.agent = DQNAgent()
        self.is_trained = False
        self.training_history = []

    def train(self, price_data: np.ndarray, volume_data: np.ndarray,
              episodes: int = 100, verbose: bool = True):
        """Train the RL agent on historical data"""
        env = TradingEnvironment(price_data, volume_data, self.initial_capital)

        if verbose:
            print(f"Training RL Agent for {episodes} episodes...")

        for episode in range(episodes):
            state = env.reset()
            episode_reward = 0
            done = False

            while not done:
                # Get action
                action = self.agent.get_action(state.to_array(), training=True)

                # Take step
                next_state, reward, done, info = env.step(action)

                # Store experience
                self.agent.store_experience(
                    state.to_array(), action, reward,
                    next_state.to_array(), done
                )

                # Train
                if len(self.agent.replay_buffer) >= self.agent.batch_size:
                    self.agent.train_step()

                state = next_state
                episode_reward += reward

            self.agent.episode_rewards.append(episode_reward)

            if verbose and episode % 10 == 0:
                avg_reward = np.mean(self.agent.episode_rewards[-10:])
                print(f"Episode {episode}: Reward = {episode_reward:.2f}, "
                      f"Avg = {avg_reward:.2f}, Epsilon = {self.agent.epsilon:.3f}, "
                      f"Win Rate = {info['win_rate']*100:.1f}%")

        self.is_trained = True

        if verbose:
            print("Training complete!")
            print(f"Final Win Rate: {info['win_rate']*100:.1f}%")
            print(f"Total P&L: {env.total_pnl*100:.2f}%")

    def get_action(self, state: TradingState) -> Tuple[TradingAction, float]:
        """Get trading action for current state"""
        if not self.is_trained:
            return TradingAction.HOLD, 0.0

        q_values = self.agent.get_q_values(state.to_array())
        action_idx = np.argmax(q_values)
        confidence = self._softmax(q_values)[action_idx]

        return TradingAction(action_idx), confidence

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()

    def get_stats(self) -> Dict:
        """Get training statistics"""
        return {
            'is_trained': self.is_trained,
            'episodes': len(self.agent.episode_rewards),
            'avg_reward': np.mean(self.agent.episode_rewards[-100:]) if self.agent.episode_rewards else 0,
            'epsilon': self.agent.epsilon,
            'buffer_size': len(self.agent.replay_buffer),
            'training_steps': self.agent.training_step
        }
