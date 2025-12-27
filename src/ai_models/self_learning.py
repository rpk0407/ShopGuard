"""
Self-Learning Adaptation System

Enables models to learn and adapt in real-time:
- Online learning from new data
- Performance monitoring and model selection
- Automatic hyperparameter tuning
- Concept drift detection
- Model versioning and rollback
- A/B testing for model improvements
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import time
import hashlib


class LearningMode(Enum):
    PASSIVE = "passive"  # Learn but don't update live model
    ACTIVE = "active"  # Update model in real-time
    BATCH = "batch"  # Update periodically in batches
    HYBRID = "hybrid"  # Combination of active and batch


class DriftType(Enum):
    NONE = "none"
    GRADUAL = "gradual"
    SUDDEN = "sudden"
    RECURRING = "recurring"


@dataclass
class ModelVersion:
    version_id: str
    created_at: float
    performance_metrics: Dict[str, float]
    parameters: Dict[str, Any]
    is_active: bool = False


@dataclass
class LearningEvent:
    timestamp: float
    event_type: str
    old_value: Any
    new_value: Any
    reason: str


@dataclass
class PerformanceWindow:
    predictions: List[float] = field(default_factory=list)
    actuals: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)


class OnlineLearner:
    """Online learning with stochastic gradient descent"""

    def __init__(self, input_size: int, output_size: int, learning_rate: float = 0.01):
        self.input_size = input_size
        self.output_size = output_size
        self.lr = learning_rate

        # Simple linear model for online updates
        self.weights = np.random.randn(input_size, output_size) * 0.01
        self.bias = np.zeros(output_size)

        # Momentum
        self.momentum = 0.9
        self.v_weights = np.zeros_like(self.weights)
        self.v_bias = np.zeros_like(self.bias)

        # Adaptive learning rate (AdaGrad-style)
        self.cache_weights = np.zeros_like(self.weights) + 1e-8
        self.cache_bias = np.zeros_like(self.bias) + 1e-8

        # Statistics
        self.n_updates = 0
        self.cumulative_loss = 0

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.dot(x, self.weights) + self.bias

    def update(self, x: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray):
        """Single sample update"""
        # Compute gradients
        error = y_pred - y_true
        d_weights = np.outer(x, error)
        d_bias = error

        # AdaGrad
        self.cache_weights += d_weights ** 2
        self.cache_bias += d_bias ** 2

        # Momentum update
        self.v_weights = self.momentum * self.v_weights - self.lr * d_weights / np.sqrt(self.cache_weights)
        self.v_bias = self.momentum * self.v_bias - self.lr * d_bias / np.sqrt(self.cache_bias)

        self.weights += self.v_weights
        self.bias += self.v_bias

        # Update statistics
        self.n_updates += 1
        self.cumulative_loss += np.mean(error ** 2)

    def get_average_loss(self) -> float:
        if self.n_updates == 0:
            return 0
        return self.cumulative_loss / self.n_updates


class ConceptDriftDetector:
    """Detect when data distribution changes"""

    def __init__(self, window_size: int = 100, threshold: float = 2.0):
        self.window_size = window_size
        self.threshold = threshold
        self.reference_window = deque(maxlen=window_size)
        self.current_window = deque(maxlen=window_size)
        self.drift_detected = False
        self.drift_type = DriftType.NONE

    def add_error(self, error: float):
        """Add prediction error"""
        if len(self.reference_window) < self.window_size:
            self.reference_window.append(error)
        else:
            self.current_window.append(error)

    def check_drift(self) -> Tuple[bool, DriftType, float]:
        """Check for concept drift using Page-Hinkley test"""
        if len(self.current_window) < self.window_size // 2:
            return False, DriftType.NONE, 0

        ref_mean = np.mean(list(self.reference_window))
        ref_std = np.std(list(self.reference_window)) + 1e-10
        curr_mean = np.mean(list(self.current_window))

        # Z-score for drift detection
        z_score = abs(curr_mean - ref_mean) / ref_std

        if z_score > self.threshold:
            # Determine drift type
            if z_score > self.threshold * 2:
                drift_type = DriftType.SUDDEN
            else:
                drift_type = DriftType.GRADUAL

            self.drift_detected = True
            self.drift_type = drift_type
            return True, drift_type, z_score

        self.drift_detected = False
        self.drift_type = DriftType.NONE
        return False, DriftType.NONE, z_score

    def reset_reference(self):
        """Reset reference window with current data"""
        self.reference_window = deque(list(self.current_window), maxlen=self.window_size)
        self.current_window.clear()
        self.drift_detected = False


class PerformanceMonitor:
    """Monitor and track model performance"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.predictions = deque(maxlen=window_size)
        self.actuals = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)
        self.returns = deque(maxlen=window_size)  # For financial metrics

        # Historical performance
        self.daily_pnl: List[float] = []
        self.cumulative_return = 0

    def record(self, prediction: float, actual: float, pnl: float = 0):
        t = time.time()
        self.predictions.append(prediction)
        self.actuals.append(actual)
        self.timestamps.append(t)
        self.returns.append(pnl)

    def get_accuracy(self, threshold: float = 0.5) -> float:
        """Classification accuracy (for directional predictions)"""
        if len(self.predictions) == 0:
            return 0.5

        pred_dir = np.sign(np.array(list(self.predictions)))
        actual_dir = np.sign(np.array(list(self.actuals)))
        return np.mean(pred_dir == actual_dir)

    def get_mse(self) -> float:
        if len(self.predictions) == 0:
            return 0
        preds = np.array(list(self.predictions))
        acts = np.array(list(self.actuals))
        return np.mean((preds - acts) ** 2)

    def get_mae(self) -> float:
        if len(self.predictions) == 0:
            return 0
        preds = np.array(list(self.predictions))
        acts = np.array(list(self.actuals))
        return np.mean(np.abs(preds - acts))

    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio from returns"""
        if len(self.returns) < 2:
            return 0

        returns = np.array(list(self.returns))
        excess_returns = returns - risk_free_rate / 252

        if np.std(returns) == 0:
            return 0
        return np.sqrt(252) * np.mean(excess_returns) / np.std(returns)

    def get_max_drawdown(self) -> float:
        if len(self.returns) == 0:
            return 0

        cumulative = np.cumsum(list(self.returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return np.max(drawdown) if len(drawdown) > 0 else 0

    def get_metrics(self) -> Dict[str, float]:
        return {
            'accuracy': self.get_accuracy(),
            'mse': self.get_mse(),
            'mae': self.get_mae(),
            'sharpe_ratio': self.get_sharpe_ratio(),
            'max_drawdown': self.get_max_drawdown(),
            'n_samples': len(self.predictions)
        }


class HyperparameterTuner:
    """Automatic hyperparameter optimization"""

    def __init__(self):
        self.param_history: List[Tuple[Dict, float]] = []
        self.best_params: Optional[Dict] = None
        self.best_score = float('-inf')

    def random_search(self, param_space: Dict[str, Tuple], n_trials: int = 20) -> Dict:
        """Random search over parameter space"""
        for _ in range(n_trials):
            params = {}
            for name, (low, high, is_int) in param_space.items():
                if is_int:
                    params[name] = np.random.randint(low, high + 1)
                else:
                    params[name] = np.random.uniform(low, high)
            yield params

    def bayesian_update(self, params: Dict, score: float):
        """Record trial result for Bayesian optimization"""
        self.param_history.append((params, score))
        if score > self.best_score:
            self.best_score = score
            self.best_params = params.copy()

    def suggest_next(self, param_space: Dict[str, Tuple]) -> Dict:
        """Suggest next parameters using acquisition function"""
        if len(self.param_history) < 5:
            # Exploration phase: random
            params = {}
            for name, (low, high, is_int) in param_space.items():
                if is_int:
                    params[name] = np.random.randint(low, high + 1)
                else:
                    params[name] = np.random.uniform(low, high)
            return params

        # Simple exploitation: perturb best params
        params = self.best_params.copy()
        for name, (low, high, is_int) in param_space.items():
            noise = np.random.normal(0, (high - low) * 0.1)
            if is_int:
                params[name] = int(np.clip(params[name] + noise, low, high))
            else:
                params[name] = np.clip(params[name] + noise, low, high)

        return params


class ModelVersionManager:
    """Manage model versions with rollback capability"""

    def __init__(self, max_versions: int = 10):
        self.max_versions = max_versions
        self.versions: List[ModelVersion] = []
        self.active_version: Optional[ModelVersion] = None

    def create_version(self, parameters: Dict, metrics: Dict) -> ModelVersion:
        """Create a new model version"""
        version_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

        version = ModelVersion(
            version_id=version_id,
            created_at=time.time(),
            performance_metrics=metrics.copy(),
            parameters=parameters.copy()
        )

        self.versions.append(version)

        # Remove old versions
        if len(self.versions) > self.max_versions:
            # Keep best performing versions
            self.versions.sort(key=lambda v: v.performance_metrics.get('sharpe_ratio', 0), reverse=True)
            self.versions = self.versions[:self.max_versions]

        return version

    def activate_version(self, version_id: str) -> bool:
        """Activate a specific version"""
        for v in self.versions:
            if v.version_id == version_id:
                if self.active_version:
                    self.active_version.is_active = False
                v.is_active = True
                self.active_version = v
                return True
        return False

    def rollback(self) -> Optional[ModelVersion]:
        """Rollback to previous version"""
        if len(self.versions) < 2:
            return None

        # Find current active version index
        active_idx = -1
        for i, v in enumerate(self.versions):
            if v.is_active:
                active_idx = i
                break

        if active_idx <= 0:
            return None

        # Activate previous version
        self.versions[active_idx].is_active = False
        self.versions[active_idx - 1].is_active = True
        self.active_version = self.versions[active_idx - 1]
        return self.active_version

    def get_best_version(self, metric: str = 'sharpe_ratio') -> Optional[ModelVersion]:
        """Get best performing version"""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.performance_metrics.get(metric, 0))


class ABTestManager:
    """A/B testing for model improvements"""

    def __init__(self):
        self.experiments: Dict[str, Dict] = {}

    def create_experiment(self, name: str, control_model: Any, treatment_model: Any, traffic_split: float = 0.5):
        """Create A/B test experiment"""
        self.experiments[name] = {
            'control': {'model': control_model, 'predictions': [], 'actuals': [], 'returns': []},
            'treatment': {'model': treatment_model, 'predictions': [], 'actuals': [], 'returns': []},
            'traffic_split': traffic_split,
            'start_time': time.time(),
            'n_samples': 0
        }

    def get_assignment(self, experiment_name: str) -> str:
        """Get model assignment (control or treatment)"""
        if experiment_name not in self.experiments:
            return 'control'

        exp = self.experiments[experiment_name]
        return 'treatment' if np.random.random() < exp['traffic_split'] else 'control'

    def record_result(self, experiment_name: str, variant: str, prediction: float, actual: float, pnl: float = 0):
        """Record experiment result"""
        if experiment_name not in self.experiments:
            return

        exp = self.experiments[experiment_name][variant]
        exp['predictions'].append(prediction)
        exp['actuals'].append(actual)
        exp['returns'].append(pnl)
        self.experiments[experiment_name]['n_samples'] += 1

    def get_results(self, experiment_name: str) -> Dict[str, Any]:
        """Get experiment results with statistical significance"""
        if experiment_name not in self.experiments:
            return {}

        exp = self.experiments[experiment_name]
        control = exp['control']
        treatment = exp['treatment']

        def calc_metrics(data: Dict) -> Dict:
            if not data['returns']:
                return {'sharpe': 0, 'accuracy': 0.5, 'n': 0}

            returns = np.array(data['returns'])
            preds = np.array(data['predictions'])
            acts = np.array(data['actuals'])

            sharpe = np.sqrt(252) * np.mean(returns) / (np.std(returns) + 1e-10)
            accuracy = np.mean(np.sign(preds) == np.sign(acts))

            return {'sharpe': sharpe, 'accuracy': accuracy, 'n': len(returns)}

        control_metrics = calc_metrics(control)
        treatment_metrics = calc_metrics(treatment)

        # Simple statistical test (t-test approximation)
        n_c, n_t = len(control['returns']), len(treatment['returns'])
        if n_c > 10 and n_t > 10:
            mean_diff = treatment_metrics['sharpe'] - control_metrics['sharpe']
            pooled_std = np.sqrt((np.var(control['returns']) + np.var(treatment['returns'])) / 2)
            t_stat = mean_diff / (pooled_std * np.sqrt(1/n_c + 1/n_t) + 1e-10)
            is_significant = abs(t_stat) > 1.96  # 95% confidence
        else:
            is_significant = False
            t_stat = 0

        winner = 'treatment' if treatment_metrics['sharpe'] > control_metrics['sharpe'] else 'control'

        return {
            'control': control_metrics,
            'treatment': treatment_metrics,
            'winner': winner,
            'is_significant': is_significant,
            't_statistic': t_stat,
            'n_samples': exp['n_samples'],
            'duration_hours': (time.time() - exp['start_time']) / 3600
        }


class SelfLearningSystem:
    """Complete self-learning system integrating all components"""

    def __init__(self, input_size: int = 20, output_size: int = 1):
        self.online_learner = OnlineLearner(input_size, output_size)
        self.drift_detector = ConceptDriftDetector()
        self.performance_monitor = PerformanceMonitor()
        self.hyperparameter_tuner = HyperparameterTuner()
        self.version_manager = ModelVersionManager()
        self.ab_tester = ABTestManager()

        self.mode = LearningMode.HYBRID
        self.learning_events: List[LearningEvent] = []

        # Batch learning buffer
        self.batch_buffer_x: List[np.ndarray] = []
        self.batch_buffer_y: List[np.ndarray] = []
        self.batch_size = 32

        # Adaptation thresholds
        self.drift_adaptation_threshold = 2.0
        self.performance_degradation_threshold = 0.2

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Make prediction"""
        return self.online_learner.predict(x)

    def learn(self, x: np.ndarray, y_true: np.ndarray, pnl: float = 0):
        """Learn from new data point"""
        y_pred = self.predict(x)

        # Record performance
        self.performance_monitor.record(float(y_pred[0] if y_pred.ndim > 0 else y_pred),
                                         float(y_true[0] if y_true.ndim > 0 else y_true), pnl)

        # Calculate error
        error = float(np.mean((y_pred - y_true) ** 2))
        self.drift_detector.add_error(error)

        # Check for drift
        drift_detected, drift_type, z_score = self.drift_detector.check_drift()

        if drift_detected:
            self._handle_drift(drift_type, z_score)

        # Update based on learning mode
        if self.mode == LearningMode.ACTIVE:
            self.online_learner.update(x, y_true, y_pred)
        elif self.mode == LearningMode.BATCH:
            self.batch_buffer_x.append(x)
            self.batch_buffer_y.append(y_true)
            if len(self.batch_buffer_x) >= self.batch_size:
                self._batch_update()
        elif self.mode == LearningMode.HYBRID:
            # Active update with reduced learning rate
            self.online_learner.lr *= 0.5
            self.online_learner.update(x, y_true, y_pred)
            self.online_learner.lr *= 2

            # Also buffer for periodic batch updates
            self.batch_buffer_x.append(x)
            self.batch_buffer_y.append(y_true)

    def _batch_update(self):
        """Perform batch update"""
        if not self.batch_buffer_x:
            return

        X = np.array(self.batch_buffer_x)
        Y = np.array(self.batch_buffer_y)

        # Multiple passes over batch
        for _ in range(3):
            indices = np.random.permutation(len(X))
            for i in indices:
                y_pred = self.online_learner.predict(X[i])
                self.online_learner.update(X[i], Y[i], y_pred)

        self.batch_buffer_x.clear()
        self.batch_buffer_y.clear()

    def _handle_drift(self, drift_type: DriftType, z_score: float):
        """Handle detected concept drift"""
        event = LearningEvent(
            timestamp=time.time(),
            event_type='drift_detected',
            old_value=drift_type.value,
            new_value=z_score,
            reason=f"Concept drift detected: {drift_type.value} (z={z_score:.2f})"
        )
        self.learning_events.append(event)

        if drift_type == DriftType.SUDDEN:
            # Reset learning rate and potentially model
            self.online_learner.lr *= 2  # Increase learning rate for faster adaptation
            self.drift_detector.reset_reference()

            # Create new version
            metrics = self.performance_monitor.get_metrics()
            self.version_manager.create_version(
                {'lr': self.online_learner.lr},
                metrics
            )

        elif drift_type == DriftType.GRADUAL:
            # Gentle adaptation
            self.online_learner.lr *= 1.2

    def adapt_hyperparameters(self):
        """Adapt hyperparameters based on performance"""
        metrics = self.performance_monitor.get_metrics()

        # Record for tuner
        params = {'lr': self.online_learner.lr, 'momentum': self.online_learner.momentum}
        score = metrics['sharpe_ratio']
        self.hyperparameter_tuner.bayesian_update(params, score)

        # Get suggestion for next params
        param_space = {
            'lr': (0.0001, 0.1, False),
            'momentum': (0.8, 0.99, False)
        }
        suggested = self.hyperparameter_tuner.suggest_next(param_space)

        # Gradually move towards suggested
        self.online_learner.lr = 0.9 * self.online_learner.lr + 0.1 * suggested['lr']
        self.online_learner.momentum = 0.9 * self.online_learner.momentum + 0.1 * suggested['momentum']

    def save_checkpoint(self) -> ModelVersion:
        """Save current model state"""
        metrics = self.performance_monitor.get_metrics()
        params = {
            'weights': self.online_learner.weights.tolist(),
            'bias': self.online_learner.bias.tolist(),
            'lr': self.online_learner.lr
        }
        version = self.version_manager.create_version(params, metrics)
        self.version_manager.activate_version(version.version_id)
        return version

    def load_checkpoint(self, version_id: str) -> bool:
        """Load model from checkpoint"""
        for v in self.version_manager.versions:
            if v.version_id == version_id:
                params = v.parameters
                self.online_learner.weights = np.array(params['weights'])
                self.online_learner.bias = np.array(params['bias'])
                self.online_learner.lr = params['lr']
                return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            'mode': self.mode.value,
            'n_updates': self.online_learner.n_updates,
            'avg_loss': self.online_learner.get_average_loss(),
            'drift_detected': self.drift_detector.drift_detected,
            'drift_type': self.drift_detector.drift_type.value,
            'performance': self.performance_monitor.get_metrics(),
            'n_versions': len(self.version_manager.versions),
            'active_version': self.version_manager.active_version.version_id if self.version_manager.active_version else None,
            'n_events': len(self.learning_events),
            'last_event': self.learning_events[-1].reason if self.learning_events else None
        }
