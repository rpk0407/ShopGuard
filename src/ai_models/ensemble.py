"""
Ensemble Model Combiner

Combines all specialized AI models into a unified prediction system:
- Deep Learning (LSTM, Transformer)
- Reinforcement Learning (DQN Agent)
- Financial NLP (Sentiment Analysis)
- Pattern Recognition (CNN)
- Regime Classification (HMM + NN)
- Self-Learning Adaptation

Uses multiple ensemble techniques:
- Weighted averaging
- Stacking
- Boosting
- Dynamic model selection
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import time


class EnsembleMethod(Enum):
    SIMPLE_AVERAGE = "simple_average"
    WEIGHTED_AVERAGE = "weighted_average"
    STACKING = "stacking"
    VOTING = "voting"
    DYNAMIC_SELECTION = "dynamic_selection"
    BOOSTING = "boosting"


class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class ModelPrediction:
    model_name: str
    signal: float  # -1 to 1 (sell to buy)
    confidence: float  # 0 to 1
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsemblePrediction:
    final_signal: SignalType
    signal_strength: float
    confidence: float
    model_contributions: Dict[str, float]
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size_multiplier: float = 1.0
    reasoning: str = ""


class ModelWeight:
    """Dynamic model weight based on performance"""

    def __init__(self, initial_weight: float = 1.0, decay: float = 0.95):
        self.weight = initial_weight
        self.decay = decay
        self.performance_history = deque(maxlen=100)
        self.correct_predictions = 0
        self.total_predictions = 0

    def update(self, was_correct: bool, magnitude: float = 1.0):
        """Update weight based on prediction result"""
        self.total_predictions += 1
        if was_correct:
            self.correct_predictions += 1
            self.weight = min(2.0, self.weight * (1 + 0.1 * magnitude))
        else:
            self.weight = max(0.1, self.weight * self.decay)

        self.performance_history.append(1 if was_correct else 0)

    def get_accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.5
        return self.correct_predictions / self.total_predictions

    def get_recent_accuracy(self, window: int = 20) -> float:
        if len(self.performance_history) == 0:
            return 0.5
        recent = list(self.performance_history)[-window:]
        return sum(recent) / len(recent)


class StackingMetaLearner:
    """Meta-learner for stacking ensemble"""

    def __init__(self, n_models: int, hidden_size: int = 32):
        self.n_models = n_models
        self.W1 = np.random.randn(n_models, hidden_size) * 0.1
        self.b1 = np.zeros(hidden_size)
        self.W2 = np.random.randn(hidden_size, 1) * 0.1
        self.b2 = np.zeros(1)

    def predict(self, model_outputs: np.ndarray) -> float:
        """Combine model outputs"""
        h = np.tanh(np.dot(model_outputs, self.W1) + self.b1)
        output = np.tanh(np.dot(h, self.W2) + self.b2)
        return float(output[0])

    def train(self, model_outputs: np.ndarray, target: float, lr: float = 0.01):
        """Train meta-learner"""
        h = np.tanh(np.dot(model_outputs, self.W1) + self.b1)
        pred = np.tanh(np.dot(h, self.W2) + self.b2)[0]

        # Backprop
        error = pred - target
        d_output = error * (1 - pred ** 2)

        d_W2 = np.outer(h, d_output)
        d_b2 = d_output

        d_h = d_output * self.W2.flatten() * (1 - h ** 2)
        d_W1 = np.outer(model_outputs, d_h)
        d_b1 = d_h

        self.W1 -= lr * d_W1
        self.b1 -= lr * d_b1
        self.W2 -= lr * d_W2
        self.b2 -= lr * d_b2


class BoostingEnsemble:
    """Gradient boosting-inspired ensemble"""

    def __init__(self, n_models: int):
        self.n_models = n_models
        self.model_weights = np.ones(n_models) / n_models
        self.residual_weights = np.ones(n_models)

    def fit_weights(self, predictions: List[np.ndarray], targets: np.ndarray, n_rounds: int = 10):
        """Fit boosting weights"""
        residuals = targets.copy()

        for _ in range(n_rounds):
            for i, preds in enumerate(predictions):
                # Fit to residuals
                correlation = np.corrcoef(preds, residuals)[0, 1]
                if not np.isnan(correlation):
                    self.residual_weights[i] = max(0, correlation)

            # Normalize
            self.residual_weights /= self.residual_weights.sum() + 1e-10

            # Update residuals
            combined = sum(w * p for w, p in zip(self.residual_weights, predictions))
            residuals = targets - combined

        self.model_weights = self.residual_weights.copy()

    def predict(self, predictions: List[float]) -> float:
        return sum(w * p for w, p in zip(self.model_weights, predictions))


class DynamicModelSelector:
    """Select best model based on recent performance and market conditions"""

    def __init__(self, n_models: int):
        self.n_models = n_models
        self.model_scores = np.ones(n_models)
        self.condition_performance: Dict[str, np.ndarray] = {}
        self.current_condition = "normal"

    def update_performance(self, model_idx: int, score: float, condition: str = "normal"):
        """Update model performance for condition"""
        self.model_scores[model_idx] = 0.9 * self.model_scores[model_idx] + 0.1 * score

        if condition not in self.condition_performance:
            self.condition_performance[condition] = np.ones(self.n_models)
        self.condition_performance[condition][model_idx] = \
            0.9 * self.condition_performance[condition][model_idx] + 0.1 * score

    def select_models(self, condition: str = "normal", n_select: int = 3) -> List[int]:
        """Select top models for current condition"""
        if condition in self.condition_performance:
            scores = self.condition_performance[condition]
        else:
            scores = self.model_scores

        return list(np.argsort(scores)[-n_select:])

    def get_weights(self, condition: str = "normal") -> np.ndarray:
        """Get normalized weights for all models"""
        if condition in self.condition_performance:
            scores = self.condition_performance[condition]
        else:
            scores = self.model_scores

        weights = np.maximum(scores, 0.1)
        return weights / weights.sum()


class ModelEnsemble:
    """Main ensemble class combining all models"""

    def __init__(self, model_names: List[str]):
        self.model_names = model_names
        self.n_models = len(model_names)

        # Weights for each model
        self.model_weights = {name: ModelWeight() for name in model_names}

        # Ensemble methods
        self.stacking = StackingMetaLearner(self.n_models)
        self.boosting = BoostingEnsemble(self.n_models)
        self.selector = DynamicModelSelector(self.n_models)

        # Default method
        self.method = EnsembleMethod.WEIGHTED_AVERAGE

        # Prediction history
        self.prediction_history: List[EnsemblePrediction] = []

        # Correlation tracking
        self.correlation_matrix = np.eye(self.n_models)

    def combine(self, predictions: List[ModelPrediction], method: Optional[EnsembleMethod] = None) -> EnsemblePrediction:
        """Combine model predictions"""
        if method is None:
            method = self.method

        if not predictions:
            return EnsemblePrediction(
                final_signal=SignalType.HOLD,
                signal_strength=0,
                confidence=0,
                model_contributions={},
                reasoning="No predictions available"
            )

        # Extract signals and confidences
        signals = np.array([p.signal for p in predictions])
        confidences = np.array([p.confidence for p in predictions])
        names = [p.model_name for p in predictions]

        # Get weights
        weights = np.array([self.model_weights[n].weight if n in self.model_weights else 1.0 for n in names])
        weights = weights / weights.sum()

        # Combine based on method
        if method == EnsembleMethod.SIMPLE_AVERAGE:
            combined_signal = np.mean(signals)
            combined_confidence = np.mean(confidences)

        elif method == EnsembleMethod.WEIGHTED_AVERAGE:
            # Weight by both model performance and prediction confidence
            effective_weights = weights * confidences
            effective_weights = effective_weights / (effective_weights.sum() + 1e-10)
            combined_signal = np.sum(signals * effective_weights)
            combined_confidence = np.sum(confidences * effective_weights)

        elif method == EnsembleMethod.STACKING:
            combined_signal = self.stacking.predict(signals)
            combined_confidence = np.mean(confidences)

        elif method == EnsembleMethod.VOTING:
            # Majority voting with confidence weighting
            votes = np.sign(signals) * confidences
            combined_signal = np.sign(np.sum(votes))
            combined_confidence = np.abs(np.sum(votes)) / len(votes)

        elif method == EnsembleMethod.DYNAMIC_SELECTION:
            # Use only top performing models
            selected_idx = self.selector.select_models(n_select=min(3, len(signals)))
            selected_signals = signals[selected_idx]
            selected_confidences = confidences[selected_idx]
            combined_signal = np.average(selected_signals, weights=selected_confidences)
            combined_confidence = np.mean(selected_confidences)

        elif method == EnsembleMethod.BOOSTING:
            combined_signal = self.boosting.predict(list(signals))
            combined_confidence = np.mean(confidences)

        else:
            combined_signal = np.mean(signals)
            combined_confidence = np.mean(confidences)

        # Determine signal type
        if combined_signal > 0.6:
            final_signal = SignalType.STRONG_BUY
        elif combined_signal > 0.2:
            final_signal = SignalType.BUY
        elif combined_signal < -0.6:
            final_signal = SignalType.STRONG_SELL
        elif combined_signal < -0.2:
            final_signal = SignalType.SELL
        else:
            final_signal = SignalType.HOLD

        # Calculate model contributions
        contributions = {}
        for i, name in enumerate(names):
            contributions[name] = float(weights[i] * abs(signals[i]))

        # Calculate target and stop loss
        targets = [p.target_price for p in predictions if p.target_price is not None]
        stops = [p.stop_loss for p in predictions if p.stop_loss is not None]

        target_price = np.mean(targets) if targets else None
        stop_loss = np.mean(stops) if stops else None

        # Position sizing based on agreement
        agreement = np.std(signals)
        position_multiplier = 1.0 - min(agreement, 0.5)  # Lower if disagreement

        # Generate reasoning
        reasoning_parts = []
        if final_signal in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
            reasoning_parts.append(f"Strong consensus ({combined_confidence:.0%} confidence)")
        if agreement < 0.3:
            reasoning_parts.append("High model agreement")
        else:
            reasoning_parts.append("Mixed signals")

        top_contributors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
        reasoning_parts.append(f"Led by: {', '.join(c[0] for c in top_contributors)}")

        result = EnsemblePrediction(
            final_signal=final_signal,
            signal_strength=abs(combined_signal),
            confidence=combined_confidence,
            model_contributions=contributions,
            target_price=target_price,
            stop_loss=stop_loss,
            position_size_multiplier=position_multiplier,
            reasoning=" | ".join(reasoning_parts)
        )

        self.prediction_history.append(result)
        return result

    def update_weights(self, prediction: EnsemblePrediction, actual_return: float):
        """Update model weights based on outcome"""
        was_correct = (prediction.final_signal.value > 0 and actual_return > 0) or \
                      (prediction.final_signal.value < 0 and actual_return < 0)

        for name, contribution in prediction.model_contributions.items():
            if name in self.model_weights:
                self.model_weights[name].update(was_correct, abs(actual_return))

    def train_stacking(self, predictions_history: List[List[float]], targets: List[float]):
        """Train stacking meta-learner"""
        for preds, target in zip(predictions_history, targets):
            self.stacking.train(np.array(preds), target)

    def train_boosting(self, predictions_history: List[List[float]], targets: np.ndarray):
        """Train boosting weights"""
        pred_arrays = [np.array([p[i] for p in predictions_history]) for i in range(self.n_models)]
        self.boosting.fit_weights(pred_arrays, targets)

    def update_correlations(self, predictions: List[ModelPrediction]):
        """Update model correlation matrix"""
        if len(predictions) < 2:
            return

        signals = [p.signal for p in predictions]
        names = [p.model_name for p in predictions]

        # Update running correlation estimate
        for i, name_i in enumerate(names):
            idx_i = self.model_names.index(name_i) if name_i in self.model_names else -1
            if idx_i < 0:
                continue

            for j, name_j in enumerate(names):
                if i >= j:
                    continue

                idx_j = self.model_names.index(name_j) if name_j in self.model_names else -1
                if idx_j < 0:
                    continue

                # Simple correlation update
                corr = signals[i] * signals[j]  # Same sign = positive correlation
                self.correlation_matrix[idx_i, idx_j] = \
                    0.95 * self.correlation_matrix[idx_i, idx_j] + 0.05 * corr
                self.correlation_matrix[idx_j, idx_i] = self.correlation_matrix[idx_i, idx_j]

    def get_diversified_weights(self) -> np.ndarray:
        """Get weights that maximize diversification"""
        # Penalize correlated models
        inv_corr = 1 - np.abs(self.correlation_matrix)
        diversification_scores = np.mean(inv_corr, axis=1)

        performance_weights = np.array([self.model_weights[n].weight for n in self.model_names])

        # Combine performance and diversification
        combined = performance_weights * diversification_scores
        return combined / combined.sum()

    def get_model_stats(self) -> Dict[str, Dict]:
        """Get statistics for all models"""
        stats = {}
        for name in self.model_names:
            w = self.model_weights[name]
            stats[name] = {
                'weight': w.weight,
                'accuracy': w.get_accuracy(),
                'recent_accuracy': w.get_recent_accuracy(),
                'total_predictions': w.total_predictions
            }
        return stats


class TradingEnsemble:
    """Complete trading ensemble system"""

    def __init__(self):
        self.models = {
            'deep_learning': None,
            'reinforcement_learning': None,
            'nlp_sentiment': None,
            'pattern_recognition': None,
            'regime_classifier': None,
            'technical_analysis': None
        }

        self.ensemble = ModelEnsemble(list(self.models.keys()))
        self.last_predictions: Dict[str, ModelPrediction] = {}

        # Market context
        self.market_regime = "normal"
        self.volatility_level = "normal"

    def set_model(self, name: str, model: Any):
        """Set a model component"""
        if name in self.models:
            self.models[name] = model

    def get_prediction(self, market_data: Dict[str, Any]) -> EnsemblePrediction:
        """Get ensemble prediction from all models"""
        predictions = []

        # Deep Learning prediction
        if self.models['deep_learning']:
            try:
                dl_pred = self._get_deep_learning_prediction(market_data)
                predictions.append(dl_pred)
                self.last_predictions['deep_learning'] = dl_pred
            except Exception:
                pass

        # RL prediction
        if self.models['reinforcement_learning']:
            try:
                rl_pred = self._get_rl_prediction(market_data)
                predictions.append(rl_pred)
                self.last_predictions['reinforcement_learning'] = rl_pred
            except Exception:
                pass

        # NLP sentiment
        if self.models['nlp_sentiment'] and 'news' in market_data:
            try:
                nlp_pred = self._get_nlp_prediction(market_data)
                predictions.append(nlp_pred)
                self.last_predictions['nlp_sentiment'] = nlp_pred
            except Exception:
                pass

        # Pattern recognition
        if self.models['pattern_recognition'] and 'ohlcv' in market_data:
            try:
                pattern_pred = self._get_pattern_prediction(market_data)
                predictions.append(pattern_pred)
                self.last_predictions['pattern_recognition'] = pattern_pred
            except Exception:
                pass

        # Regime classifier
        if self.models['regime_classifier'] and 'prices' in market_data:
            try:
                regime_pred = self._get_regime_prediction(market_data)
                predictions.append(regime_pred)
                self.last_predictions['regime_classifier'] = regime_pred
            except Exception:
                pass

        # Technical analysis (always available)
        if 'prices' in market_data:
            try:
                ta_pred = self._get_technical_prediction(market_data)
                predictions.append(ta_pred)
                self.last_predictions['technical_analysis'] = ta_pred
            except Exception:
                pass

        # Update correlations
        self.ensemble.update_correlations(predictions)

        # Combine predictions
        return self.ensemble.combine(predictions)

    def _get_deep_learning_prediction(self, data: Dict) -> ModelPrediction:
        model = self.models['deep_learning']
        prices = np.array(data.get('prices', []))

        if len(prices) < 20:
            return ModelPrediction('deep_learning', 0, 0.3, reasoning="Insufficient data")

        # Normalize and predict
        normalized = (prices - np.mean(prices)) / (np.std(prices) + 1e-10)
        prediction = model.predict(normalized[-20:].reshape(1, -1))

        signal = float(np.tanh(prediction[0][0] if hasattr(prediction[0], '__len__') else prediction[0]))
        confidence = min(0.9, 0.5 + abs(signal) * 0.4)

        return ModelPrediction('deep_learning', signal, confidence,
                               reasoning=f"DL prediction: {signal:.3f}")

    def _get_rl_prediction(self, data: Dict) -> ModelPrediction:
        model = self.models['reinforcement_learning']
        state = data.get('state', np.zeros(14))

        action = model.select_action(state, training=False)

        # Map action to signal
        action_to_signal = {0: -1, 1: -0.5, 2: 0, 3: 0.5, 4: 1}
        signal = action_to_signal.get(action, 0)
        confidence = 0.7

        return ModelPrediction('reinforcement_learning', signal, confidence,
                               reasoning=f"RL action: {action}")

    def _get_nlp_prediction(self, data: Dict) -> ModelPrediction:
        model = self.models['nlp_sentiment']
        news = data.get('news', [])

        if not news:
            return ModelPrediction('nlp_sentiment', 0, 0.3, reasoning="No news")

        # Aggregate sentiment from all news
        sentiments = []
        for article in news:
            result = model.analyze_sentiment(article)
            sentiments.append(result.sentiment.value / 2)  # Normalize to -1 to 1

        signal = np.mean(sentiments)
        confidence = min(0.9, 0.5 + len(news) * 0.05)

        return ModelPrediction('nlp_sentiment', signal, confidence,
                               reasoning=f"Sentiment from {len(news)} articles")

    def _get_pattern_prediction(self, data: Dict) -> ModelPrediction:
        model = self.models['pattern_recognition']
        ohlcv = np.array(data.get('ohlcv', []))

        if len(ohlcv) < 10:
            return ModelPrediction('pattern_recognition', 0, 0.3, reasoning="Insufficient data")

        result = model.analyze(ohlcv)
        patterns = result.get('patterns', [])

        if not patterns:
            return ModelPrediction('pattern_recognition', 0, 0.4, reasoning="No patterns found")

        # Aggregate pattern signals
        signal = 0
        for p in patterns:
            if p.direction.value == 'bullish':
                signal += p.confidence
            elif p.direction.value == 'bearish':
                signal -= p.confidence

        signal = np.tanh(signal / max(len(patterns), 1))
        confidence = result.get('confidence', 0.5)

        return ModelPrediction('pattern_recognition', signal, confidence,
                               target_price=patterns[0].target_price if patterns else None,
                               reasoning=f"{len(patterns)} patterns: {result.get('direction', 'neutral')}")

    def _get_regime_prediction(self, data: Dict) -> ModelPrediction:
        model = self.models['regime_classifier']
        prices = np.array(data.get('prices', []))

        if len(prices) < 20:
            return ModelPrediction('regime_classifier', 0, 0.3, reasoning="Insufficient data")

        state = model.classify(prices)
        bias = model.get_trading_bias()

        # Map bias to signal
        bias_to_signal = {'long': 0.5, 'short': -0.5, 'neutral': 0}
        signal = bias_to_signal.get(bias['bias'], 0) * bias.get('position_size', 1)

        self.market_regime = state.primary_regime.value
        self.volatility_level = state.volatility_regime.value

        return ModelPrediction('regime_classifier', signal, state.confidence,
                               metadata={'regime': self.market_regime, 'volatility': self.volatility_level},
                               reasoning=f"Regime: {self.market_regime}, Vol: {self.volatility_level}")

    def _get_technical_prediction(self, data: Dict) -> ModelPrediction:
        prices = np.array(data.get('prices', []))

        if len(prices) < 20:
            return ModelPrediction('technical_analysis', 0, 0.3, reasoning="Insufficient data")

        # Simple technical indicators
        returns = np.diff(prices) / prices[:-1]

        # Momentum
        momentum = (prices[-1] / prices[-20] - 1) * 10

        # RSI
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_signal = (50 - rsi) / 50  # Negative when overbought, positive when oversold

        # MACD
        ema12 = prices[-12:].mean()
        ema26 = prices[-26:].mean() if len(prices) >= 26 else prices.mean()
        macd = (ema12 - ema26) / ema26 * 10

        # Combine signals
        signal = np.tanh(momentum * 0.3 + rsi_signal * 0.3 + macd * 0.4)
        confidence = 0.6

        return ModelPrediction('technical_analysis', signal, confidence,
                               reasoning=f"RSI: {rsi:.0f}, MACD: {macd:.3f}")

    def update_on_outcome(self, actual_return: float):
        """Update ensemble based on trade outcome"""
        if self.ensemble.prediction_history:
            last_pred = self.ensemble.prediction_history[-1]
            self.ensemble.update_weights(last_pred, actual_return)

    def get_status(self) -> Dict[str, Any]:
        """Get ensemble status"""
        return {
            'models_active': sum(1 for m in self.models.values() if m is not None),
            'total_models': len(self.models),
            'market_regime': self.market_regime,
            'volatility': self.volatility_level,
            'model_stats': self.ensemble.get_model_stats(),
            'ensemble_method': self.ensemble.method.value,
            'n_predictions': len(self.ensemble.prediction_history)
        }
