"""
Ensemble Methods for Trading

Ensemble methods combine multiple models to improve:
1. Prediction accuracy (bias reduction)
2. Robustness (variance reduction)
3. Adaptability (regime handling)

This module implements:
- Model stacking (meta-learning)
- Boosting for financial time series
- Mixture of experts
- Dynamic model selection
"""

import numpy as np
import torch
import torch.nn as nn
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ModelPrediction:
    """Prediction from a single model."""
    model_name: str
    prediction: np.ndarray
    confidence: float
    features_used: List[str]


@dataclass
class EnsemblePrediction:
    """Combined prediction from ensemble."""
    prediction: np.ndarray
    confidence: float
    model_weights: Dict[str, float]
    individual_predictions: List[ModelPrediction]
    disagreement: float  # Variance across models


class BaseModel(ABC):
    """Abstract base model for ensemble."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fit model to data."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability predictions."""
        pass


class ModelStacker:
    """
    Stacking ensemble (meta-learning).

    Level 1: Base models generate predictions
    Level 2: Meta-model combines predictions

    Advantages:
    - Learns optimal combination weights
    - Can capture non-linear relationships
    - Handles model correlations

    For trading:
    - Combine momentum, mean-reversion, and ML models
    - Meta-model learns when each works best
    """

    def __init__(
        self,
        base_models: List[BaseModel],
        meta_model: BaseModel,
        use_features: bool = True,
        cv_folds: int = 5
    ):
        """
        Initialize stacker.

        Args:
            base_models: List of level-1 models
            meta_model: Level-2 model
            use_features: Include original features in meta-model
            cv_folds: Cross-validation folds for generating meta-features
        """
        self.base_models = base_models
        self.meta_model = meta_model
        self.use_features = use_features
        self.cv_folds = cv_folds

        self.base_model_names = [f"model_{i}" for i in range(len(base_models))]

    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Fit stacking ensemble.

        Uses out-of-fold predictions to train meta-model.
        """
        n_samples = len(X)
        n_models = len(self.base_models)

        # Generate out-of-fold predictions
        oof_predictions = np.zeros((n_samples, n_models))
        fold_size = n_samples // self.cv_folds

        for fold in range(self.cv_folds):
            val_start = fold * fold_size
            val_end = (fold + 1) * fold_size if fold < self.cv_folds - 1 else n_samples

            train_idx = list(range(0, val_start)) + list(range(val_end, n_samples))
            val_idx = list(range(val_start, val_end))

            X_train, X_val = X[train_idx], X[val_idx]
            y_train = y[train_idx]

            for i, model in enumerate(self.base_models):
                model.fit(X_train, y_train)
                oof_predictions[val_idx, i] = model.predict(X_val)

        # Fit base models on full data
        for model in self.base_models:
            model.fit(X, y)

        # Prepare meta-features
        if self.use_features:
            meta_features = np.hstack([X, oof_predictions])
        else:
            meta_features = oof_predictions

        # Fit meta-model
        self.meta_model.fit(meta_features, y)

    def predict(self, X: np.ndarray) -> EnsemblePrediction:
        """Generate ensemble prediction."""
        n_samples = len(X)
        n_models = len(self.base_models)

        # Get base model predictions
        base_predictions = np.zeros((n_samples, n_models))
        individual_preds = []

        for i, model in enumerate(self.base_models):
            pred = model.predict(X)
            base_predictions[:, i] = pred

            individual_preds.append(ModelPrediction(
                model_name=self.base_model_names[i],
                prediction=pred,
                confidence=1.0,  # Would need model-specific confidence
                features_used=[]
            ))

        # Prepare meta-features
        if self.use_features:
            meta_features = np.hstack([X, base_predictions])
        else:
            meta_features = base_predictions

        # Get meta-model prediction
        final_pred = self.meta_model.predict(meta_features)

        # Compute disagreement
        disagreement = np.mean(np.std(base_predictions, axis=1))

        # Compute approximate model weights (correlation with final prediction)
        weights = {}
        for i, name in enumerate(self.base_model_names):
            corr = np.corrcoef(base_predictions[:, i], final_pred)[0, 1]
            weights[name] = max(0, corr)

        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}

        return EnsemblePrediction(
            prediction=final_pred,
            confidence=1 - disagreement,
            model_weights=weights,
            individual_predictions=individual_preds,
            disagreement=disagreement
        )


class MixtureOfExperts(nn.Module):
    """
    Mixture of Experts for adaptive model selection.

    Different "expert" networks specialize in different regimes.
    A gating network learns to select the appropriate expert.

    For trading:
    - Expert 1: Momentum specialist
    - Expert 2: Mean-reversion specialist
    - Expert 3: High-volatility specialist
    - Gating: Learns which expert to use based on market features
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
        n_experts: int = 4,
        dropout: float = 0.1
    ):
        """
        Initialize Mixture of Experts.

        Args:
            input_dim: Input feature dimension
            hidden_dim: Hidden layer dimension
            output_dim: Output dimension
            n_experts: Number of expert networks
            dropout: Dropout rate
        """
        super().__init__()

        self.n_experts = n_experts

        # Expert networks
        self.experts = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, output_dim)
            )
            for _ in range(n_experts)
        ])

        # Gating network
        self.gating = nn.Sequential(
            nn.Linear(input_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, n_experts),
            nn.Softmax(dim=-1)
        )

        # Load balancing loss coefficient
        self.load_balance_coef = 0.01

    def forward(
        self,
        x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Input features (batch, input_dim)

        Returns:
            Tuple of (output, gating_weights, auxiliary_loss)
        """
        batch_size = x.shape[0]

        # Get gating weights
        gating_weights = self.gating(x)  # (batch, n_experts)

        # Get expert outputs
        expert_outputs = torch.stack([
            expert(x) for expert in self.experts
        ], dim=1)  # (batch, n_experts, output_dim)

        # Weighted combination
        output = torch.sum(
            gating_weights.unsqueeze(-1) * expert_outputs,
            dim=1
        )  # (batch, output_dim)

        # Load balancing loss (encourage even expert usage)
        # Importance: mean gating weight per expert
        importance = gating_weights.mean(dim=0)
        # Load: fraction of batch where expert is max
        max_experts = gating_weights.argmax(dim=1)
        load = torch.zeros(self.n_experts, device=x.device)
        for i in range(self.n_experts):
            load[i] = (max_experts == i).float().mean()

        # Coefficient of variation
        cv_importance = importance.std() / (importance.mean() + 1e-8)
        cv_load = load.std() / (load.mean() + 1e-8)

        aux_loss = self.load_balance_coef * (cv_importance + cv_load)

        return output, gating_weights, aux_loss

    def get_expert_specialization(self, X: torch.Tensor) -> Dict[int, Dict]:
        """
        Analyze what each expert has specialized in.

        Returns dictionary with expert characteristics.
        """
        with torch.no_grad():
            gating_weights = self.gating(X)

        specialization = {}
        for i in range(self.n_experts):
            # Find inputs where this expert is dominant
            is_dominant = gating_weights[:, i] > 0.5
            dominant_indices = is_dominant.nonzero().squeeze()

            if len(dominant_indices) > 0:
                dominant_features = X[dominant_indices]
                specialization[i] = {
                    'usage_rate': is_dominant.float().mean().item(),
                    'mean_features': dominant_features.mean(dim=0).numpy(),
                    'std_features': dominant_features.std(dim=0).numpy()
                }
            else:
                specialization[i] = {
                    'usage_rate': 0,
                    'mean_features': None,
                    'std_features': None
                }

        return specialization


class AdaptiveEnsemble:
    """
    Ensemble with adaptive weighting based on recent performance.

    Weights models based on their recent accuracy.
    Similar to online learning / bandit algorithms.

    Advantages:
    - Adapts to changing market conditions
    - Down-weights models when they stop working
    - No need for regime detection (learned implicitly)
    """

    def __init__(
        self,
        models: List[BaseModel],
        model_names: List[str],
        lookback: int = 50,
        learning_rate: float = 0.1
    ):
        """
        Initialize adaptive ensemble.

        Args:
            models: List of models
            model_names: Names for models
            lookback: Window for evaluating performance
            learning_rate: How fast to adapt weights
        """
        self.models = models
        self.model_names = model_names
        self.lookback = lookback
        self.learning_rate = learning_rate

        n_models = len(models)
        self.weights = np.ones(n_models) / n_models  # Start with equal weights
        self.performance_history: List[np.ndarray] = []

    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fit all models."""
        for model in self.models:
            model.fit(X, y)

    def predict(self, X: np.ndarray) -> EnsemblePrediction:
        """Generate weighted ensemble prediction."""
        predictions = np.array([model.predict(X) for model in self.models])

        # Weighted average
        weighted_pred = np.average(predictions, axis=0, weights=self.weights)

        # Prepare output
        individual_preds = [
            ModelPrediction(
                model_name=name,
                prediction=pred,
                confidence=self.weights[i],
                features_used=[]
            )
            for i, (name, pred) in enumerate(zip(self.model_names, predictions))
        ]

        return EnsemblePrediction(
            prediction=weighted_pred,
            confidence=1 - np.std(predictions, axis=0).mean(),
            model_weights=dict(zip(self.model_names, self.weights)),
            individual_predictions=individual_preds,
            disagreement=np.std(predictions, axis=0).mean()
        )

    def update_weights(self, y_true: np.ndarray, predictions: np.ndarray):
        """
        Update model weights based on performance.

        Uses exponential weighting of recent errors.
        """
        n_models = len(self.models)

        # Compute errors for each model
        errors = np.array([
            np.mean((predictions[i] - y_true) ** 2)
            for i in range(n_models)
        ])

        # Convert errors to performance scores (lower error = higher score)
        scores = 1 / (errors + 1e-8)

        # Store in history
        self.performance_history.append(scores)
        if len(self.performance_history) > self.lookback:
            self.performance_history.pop(0)

        # Compute average recent performance
        avg_scores = np.mean(self.performance_history, axis=0)

        # Update weights using exponential moving average
        target_weights = avg_scores / avg_scores.sum()
        self.weights = (
            (1 - self.learning_rate) * self.weights +
            self.learning_rate * target_weights
        )

        # Ensure weights sum to 1
        self.weights = self.weights / self.weights.sum()


class BaggingTimeSeriesEnsemble:
    """
    Bagging ensemble adapted for time series.

    Standard bagging doesn't work for time series (violates temporal order).
    This implementation uses:
    - Block bootstrap (sample blocks of consecutive data)
    - Moving block bootstrap
    - Temporal cross-validation

    Reduces variance while respecting temporal structure.
    """

    def __init__(
        self,
        base_model_factory: Callable,
        n_estimators: int = 10,
        block_size: int = 20,
        sample_fraction: float = 0.8
    ):
        """
        Initialize time series bagging ensemble.

        Args:
            base_model_factory: Function that creates a new model instance
            n_estimators: Number of ensemble members
            block_size: Size of blocks for block bootstrap
            sample_fraction: Fraction of data to sample for each model
        """
        self.base_model_factory = base_model_factory
        self.n_estimators = n_estimators
        self.block_size = block_size
        self.sample_fraction = sample_fraction

        self.models: List = []

    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fit bagging ensemble with block bootstrap."""
        n_samples = len(X)
        n_blocks = n_samples // self.block_size
        n_sample_blocks = int(n_blocks * self.sample_fraction)

        self.models = []

        for _ in range(self.n_estimators):
            # Block bootstrap
            sampled_indices = []
            sampled_block_starts = np.random.choice(
                n_blocks, size=n_sample_blocks, replace=True
            )

            for block_start in sorted(sampled_block_starts):
                start_idx = block_start * self.block_size
                end_idx = min(start_idx + self.block_size, n_samples)
                sampled_indices.extend(range(start_idx, end_idx))

            # Remove duplicates and sort
            sampled_indices = sorted(set(sampled_indices))

            # Create and fit model
            model = self.base_model_factory()
            model.fit(X[sampled_indices], y[sampled_indices])
            self.models.append(model)

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate predictions with uncertainty.

        Returns:
            Tuple of (mean_prediction, std_prediction)
        """
        predictions = np.array([model.predict(X) for model in self.models])

        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)

        return mean_pred, std_pred


class BoostingFinancial:
    """
    Gradient boosting adapted for financial prediction.

    Key adaptations:
    - Uses financial loss functions (Sharpe, asymmetric)
    - Regularization for non-stationarity
    - Early stopping based on forward validation
    """

    def __init__(
        self,
        base_model_factory: Callable,
        n_estimators: int = 100,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
        loss: str = 'mse'
    ):
        """
        Initialize financial boosting.

        Args:
            base_model_factory: Creates weak learners
            n_estimators: Maximum number of boosting rounds
            learning_rate: Shrinkage parameter
            subsample: Fraction to subsample each round
            loss: Loss function ('mse', 'sharpe', 'asymmetric')
        """
        self.base_model_factory = base_model_factory
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.loss = loss

        self.models: List = []
        self.model_weights: List[float] = []
        self.initial_prediction = 0

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
        early_stopping_rounds: int = 10
    ):
        """Fit boosting ensemble."""
        n_samples = len(X)
        self.initial_prediction = np.mean(y)
        predictions = np.full(n_samples, self.initial_prediction)

        best_val_loss = float('inf')
        rounds_without_improvement = 0

        for round_idx in range(self.n_estimators):
            # Compute residuals (negative gradient)
            residuals = self._compute_gradient(y, predictions)

            # Subsample
            if self.subsample < 1.0:
                subsample_idx = np.random.choice(
                    n_samples,
                    size=int(n_samples * self.subsample),
                    replace=False
                )
            else:
                subsample_idx = np.arange(n_samples)

            # Fit weak learner to residuals
            model = self.base_model_factory()
            model.fit(X[subsample_idx], residuals[subsample_idx])
            self.models.append(model)
            self.model_weights.append(self.learning_rate)

            # Update predictions
            predictions += self.learning_rate * model.predict(X)

            # Validation
            if X_val is not None and y_val is not None:
                val_pred = self.predict(X_val)
                val_loss = np.mean((y_val - val_pred) ** 2)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    rounds_without_improvement = 0
                else:
                    rounds_without_improvement += 1

                if rounds_without_improvement >= early_stopping_rounds:
                    # Early stopping
                    break

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        predictions = np.full(len(X), self.initial_prediction)

        for model, weight in zip(self.models, self.model_weights):
            predictions += weight * model.predict(X)

        return predictions

    def _compute_gradient(self, y: np.ndarray, pred: np.ndarray) -> np.ndarray:
        """Compute negative gradient (residuals) based on loss function."""
        if self.loss == 'mse':
            return y - pred

        elif self.loss == 'asymmetric':
            # Penalize under-predictions more (conservative)
            residuals = y - pred
            weights = np.where(residuals > 0, 2.0, 1.0)  # 2x weight on under-prediction
            return residuals * weights

        elif self.loss == 'sharpe':
            # Gradient of Sharpe-like loss
            # Encourages predictions that would lead to high Sharpe
            returns = y  # Assume y is returns
            positions = np.sign(pred)  # Position from predictions
            strategy_returns = positions * returns

            # Adjust gradient to maximize Sharpe
            mean_ret = np.mean(strategy_returns)
            std_ret = np.std(strategy_returns) + 1e-8

            # dSharpe/dpred ≈ (y - mean) / std for correct direction
            gradient = (returns - mean_ret) / std_ret * np.sign(pred)
            return gradient

        else:
            return y - pred
