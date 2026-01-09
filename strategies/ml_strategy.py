"""
Machine Learning Trading Strategies

Strategies that use ML models for predictions:
- LSTM/Transformer predictions
- Ensemble ML models
- Reinforcement learning
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from api.strategy import Strategy, StrategyConfig, Signal, StrategyContext


@dataclass
class MLStrategyConfig(StrategyConfig):
    """Configuration for ML strategy"""
    prediction_horizon: int = 5  # Days ahead to predict
    confidence_threshold: float = 0.6  # Minimum confidence to trade
    model_path: Optional[str] = None  # Path to saved model
    retrain_frequency: int = 30  # Days between retraining


class MLPredictionStrategy(Strategy):
    """
    Machine Learning Prediction Strategy

    Logic:
    1. Use trained ML model to predict future returns
    2. Trade based on predictions with sufficient confidence
    3. Periodically retrain model on new data

    Models used:
    - Temporal Fusion Transformer
    - LSTM with Attention
    - Ensemble methods
    """

    def __init__(self, config: MLStrategyConfig):
        super().__init__(config)
        self.config = config
        self.model = None
        self.feature_history: Dict[str, List] = {s: [] for s in config.symbols}
        self.last_retrain = None

    def on_start(self):
        """Initialize and load model"""
        self.log("ML Prediction strategy started")
        self._load_model()

    def _load_model(self):
        """Load pre-trained model"""
        try:
            from ai.networks.temporal_fusion import TemporalFusionNetwork

            self.model = TemporalFusionNetwork(
                input_dim=64,
                hidden_dim=128,
                num_heads=4,
                num_layers=2,
                dropout=0.1,
                forecast_horizons=[1, 5, 21]
            )

            if self.config.model_path:
                # Load saved weights
                import torch
                self.model.load_state_dict(torch.load(self.config.model_path))
                self.log(f"Loaded model from {self.config.model_path}")
            else:
                self.log("Using untrained model - predictions may be unreliable")

        except Exception as e:
            self.log(f"Error loading model: {e}")
            self.model = None

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate ML-based signals"""
        if self.model is None:
            return []

        signals = []

        for symbol in self.symbols:
            # Generate features
            features = self._generate_features(symbol, context)
            if features is None:
                continue

            # Get model prediction
            prediction = self._predict(features)
            if prediction is None:
                continue

            # Generate signal if confident
            signal = self._create_signal_from_prediction(
                symbol, prediction, context
            )
            if signal:
                signals.append(signal)

        # Check if we need to retrain
        if self._should_retrain(context):
            self._retrain_model(context)

        return signals

    def _generate_features(
        self,
        symbol: str,
        context: StrategyContext
    ) -> Optional[np.ndarray]:
        """Generate features for ML model"""
        # Placeholder - in production would generate comprehensive features:
        # - Technical indicators (RSI, MACD, Bollinger Bands)
        # - Price/volume patterns
        # - Market regime indicators
        # - Sentiment scores
        # - Macro indicators

        price = context.get_price(symbol)
        if price is None:
            return None

        # Simple features for demo
        features = np.array([
            price,
            context.get_position(symbol),
            context.equity,
            # ... would add many more features
        ])

        return features

    def _predict(self, features: np.ndarray) -> Optional[Dict]:
        """Get prediction from model"""
        try:
            import torch

            # Convert to tensor
            x = torch.FloatTensor(features).unsqueeze(0)

            # Get prediction
            with torch.no_grad():
                output = self.model(x)

            # Extract predictions
            # Format: {
            #   'direction': float (-1 to 1),
            #   'magnitude': float (expected return),
            #   'confidence': float (0 to 1)
            # }
            prediction = {
                'direction': float(torch.tanh(output[0, 0])),
                'magnitude': float(torch.sigmoid(output[0, 1])),
                'confidence': float(torch.sigmoid(output[0, 2]))
            }

            return prediction

        except Exception as e:
            self.log(f"Prediction error: {e}")
            return None

    def _create_signal_from_prediction(
        self,
        symbol: str,
        prediction: Dict,
        context: StrategyContext
    ) -> Optional[Signal]:
        """Create trading signal from ML prediction"""

        confidence = prediction['confidence']
        direction = prediction['direction']
        magnitude = prediction['magnitude']

        # Only trade if confidence above threshold
        if confidence < self.config.confidence_threshold:
            return None

        # Determine position size based on confidence and magnitude
        strength = magnitude * confidence

        return Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            metadata={
                'reason': 'ml_prediction',
                'model': 'temporal_fusion',
                'predicted_return': magnitude,
                'horizon': self.config.prediction_horizon
            }
        )

    def _should_retrain(self, context: StrategyContext) -> bool:
        """Check if model should be retrained"""
        if self.last_retrain is None:
            return False

        days_since_retrain = (context.timestamp - self.last_retrain).days
        return days_since_retrain >= self.config.retrain_frequency

    def _retrain_model(self, context: StrategyContext):
        """Retrain model on new data"""
        self.log("Retraining model...")
        # In production, would:
        # 1. Collect recent data
        # 2. Generate features
        # 3. Train model
        # 4. Validate performance
        # 5. Update model if performance improved
        self.last_retrain = context.timestamp

    def on_stop(self):
        """Cleanup"""
        self.log("ML Prediction strategy stopped")


class EnsembleMLStrategy(Strategy):
    """
    Ensemble Machine Learning Strategy

    Combines predictions from multiple ML models:
    - LSTM
    - Transformer
    - Random Forest
    - Gradient Boosting

    Uses weighted voting based on recent performance.
    """

    def __init__(self, config: MLStrategyConfig):
        super().__init__(config)
        self.config = config
        self.models: Dict[str, any] = {}
        self.model_weights: Dict[str, float] = {}
        self.model_performance: Dict[str, List[float]] = {}

    def on_start(self):
        """Initialize ensemble"""
        self.log("Ensemble ML strategy started")
        self._load_models()
        self._initialize_weights()

    def _load_models(self):
        """Load all models in ensemble"""
        try:
            from ai.networks.temporal_fusion import TemporalFusionNetwork
            from ai.networks.lstm import LSTMPredictor
            # from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

            # Model 1: Temporal Fusion Transformer
            self.models['tft'] = TemporalFusionNetwork(
                input_dim=64, hidden_dim=128, num_heads=4
            )

            # Model 2: LSTM with Attention
            self.models['lstm'] = LSTMPredictor(
                input_dim=64, hidden_dim=128, num_layers=2
            )

            # Model 3 & 4: Tree-based models (would be loaded from disk)
            # self.models['rf'] = RandomForestRegressor()
            # self.models['gbm'] = GradientBoostingRegressor()

            self.log(f"Loaded {len(self.models)} models")

        except Exception as e:
            self.log(f"Error loading models: {e}")

    def _initialize_weights(self):
        """Initialize model weights (equal initially)"""
        n_models = len(self.models)
        if n_models > 0:
            initial_weight = 1.0 / n_models
            for model_name in self.models:
                self.model_weights[model_name] = initial_weight
                self.model_performance[model_name] = []

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate ensemble signals"""
        signals = []

        for symbol in self.symbols:
            # Get predictions from all models
            predictions = self._get_ensemble_predictions(symbol, context)

            if not predictions:
                continue

            # Combine predictions
            combined = self._combine_predictions(predictions)

            # Create signal
            signal = self._create_signal(symbol, combined, context)
            if signal:
                signals.append(signal)

        return signals

    def _get_ensemble_predictions(
        self,
        symbol: str,
        context: StrategyContext
    ) -> Dict[str, Dict]:
        """Get predictions from all models"""
        predictions = {}

        # Generate features (same for all models)
        features = self._generate_features(symbol, context)
        if features is None:
            return predictions

        # Get prediction from each model
        for model_name, model in self.models.items():
            try:
                pred = self._predict_with_model(model, features)
                if pred:
                    predictions[model_name] = pred
            except Exception as e:
                self.log(f"Error with model {model_name}: {e}")

        return predictions

    def _combine_predictions(self, predictions: Dict[str, Dict]) -> Dict:
        """Combine predictions using weighted average"""
        if not predictions:
            return {}

        # Weighted average of each component
        total_weight = sum(
            self.model_weights.get(name, 0)
            for name in predictions.keys()
        )

        if total_weight == 0:
            return {}

        combined_direction = 0.0
        combined_magnitude = 0.0
        combined_confidence = 0.0

        for model_name, pred in predictions.items():
            weight = self.model_weights[model_name] / total_weight

            combined_direction += pred['direction'] * weight
            combined_magnitude += pred['magnitude'] * weight
            combined_confidence += pred['confidence'] * weight

        return {
            'direction': combined_direction,
            'magnitude': combined_magnitude,
            'confidence': combined_confidence,
            'num_models': len(predictions)
        }

    def _create_signal(
        self,
        symbol: str,
        combined: Dict,
        context: StrategyContext
    ) -> Optional[Signal]:
        """Create signal from combined prediction"""

        if combined['confidence'] < self.config.confidence_threshold:
            return None

        strength = combined['magnitude'] * combined['confidence']

        # Higher confidence when models agree
        confidence_boost = min(0.1, combined['num_models'] * 0.02)
        final_confidence = min(0.95, combined['confidence'] + confidence_boost)

        return Signal(
            symbol=symbol,
            direction=combined['direction'],
            strength=strength,
            confidence=final_confidence,
            metadata={
                'reason': 'ensemble_ml',
                'num_models': combined['num_models'],
                'avg_confidence': combined['confidence']
            }
        )

    def _generate_features(self, symbol: str, context: StrategyContext) -> Optional[np.ndarray]:
        """Generate features"""
        # Placeholder
        return np.random.randn(64)

    def _predict_with_model(self, model: any, features: np.ndarray) -> Optional[Dict]:
        """Get prediction from a single model"""
        # Placeholder
        return {
            'direction': np.random.randn(),
            'magnitude': abs(np.random.randn() * 0.02),
            'confidence': np.random.rand() * 0.5 + 0.5
        }

    def on_stop(self):
        """Cleanup"""
        self.log("Ensemble ML strategy stopped")
