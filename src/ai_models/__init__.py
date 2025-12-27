"""
Specialized AI Models for Trading

Complete suite of machine learning models specifically trained for:
- Price prediction (Deep Learning)
- Trading decisions (Reinforcement Learning)
- News/sentiment analysis (Financial NLP)
- Chart pattern recognition (CNN)
- Market regime detection (HMM + Neural)
- Self-learning adaptation
- Ensemble prediction

These are SPECIALIZED models, not general LLMs - trained specifically for
trading, crypto, markets, news analysis, and technical analysis.
"""

# Deep Learning Models
from .deep_learning import (
    DenseLayer,
    LSTMCell,
    LSTM,
    TransformerBlock,
    PricePredictor,
    VolatilityForecaster,
    TrendClassifier
)

# Reinforcement Learning
from .reinforcement_learning import (
    NeuralNetwork,
    DQNAgent,
    TradingEnvironment,
    RLTradingSystem,
    Experience,
    PrioritizedReplayBuffer
)

# Financial NLP
from .financial_nlp import (
    FinancialSentiment,
    ImpactLevel,
    EntityType,
    FinancialEntity,
    SentimentResult,
    FinancialVocabulary,
    WordEmbedding,
    AttentionLayer,
    FinancialSentimentModel,
    EarningsAnalyzer,
    CryptoSentimentModel
)

# Pattern Recognition
from .pattern_recognition import (
    PatternType,
    PatternDirection,
    DetectedPattern,
    Conv1D,
    MaxPool1D,
    PatternCNN,
    CandlestickDetector,
    ChartPatternDetector,
    PatternRecognitionSystem
)

# Regime Classification
from .regime_classifier import (
    MarketRegime,
    VolatilityRegime,
    TrendStrength,
    RegimeState,
    HiddenMarkovModel,
    VolatilityEstimator,
    TrendDetector,
    RegimeNeuralNetwork,
    MarketRegimeClassifier,
    MultiAssetRegimeAnalyzer
)

# Self-Learning
from .self_learning import (
    LearningMode,
    DriftType,
    ModelVersion,
    LearningEvent,
    OnlineLearner,
    ConceptDriftDetector,
    PerformanceMonitor,
    HyperparameterTuner,
    ModelVersionManager,
    ABTestManager,
    SelfLearningSystem
)

# Ensemble
from .ensemble import (
    EnsembleMethod,
    SignalType,
    ModelPrediction,
    EnsemblePrediction,
    ModelWeight,
    StackingMetaLearner,
    BoostingEnsemble,
    DynamicModelSelector,
    ModelEnsemble,
    TradingEnsemble
)

__all__ = [
    # Deep Learning
    'DenseLayer', 'LSTMCell', 'LSTM', 'TransformerBlock', 'NeuralNetwork',
    'PricePredictor', 'VolatilityForecaster', 'TrendClassifier',

    # Reinforcement Learning
    'DQNAgent', 'TradingEnvironment', 'RLTradingSystem',
    'Experience', 'PrioritizedReplayBuffer',

    # Financial NLP
    'FinancialSentiment', 'ImpactLevel', 'EntityType', 'FinancialEntity',
    'SentimentResult', 'FinancialVocabulary', 'WordEmbedding', 'AttentionLayer',
    'FinancialSentimentModel', 'EarningsAnalyzer', 'CryptoSentimentModel',

    # Pattern Recognition
    'PatternType', 'PatternDirection', 'DetectedPattern',
    'Conv1D', 'MaxPool1D', 'PatternCNN',
    'CandlestickDetector', 'ChartPatternDetector', 'PatternRecognitionSystem',

    # Regime Classification
    'MarketRegime', 'VolatilityRegime', 'TrendStrength', 'RegimeState',
    'HiddenMarkovModel', 'VolatilityEstimator', 'TrendDetector',
    'RegimeNeuralNetwork', 'MarketRegimeClassifier', 'MultiAssetRegimeAnalyzer',

    # Self-Learning
    'LearningMode', 'DriftType', 'ModelVersion', 'LearningEvent',
    'OnlineLearner', 'ConceptDriftDetector', 'PerformanceMonitor',
    'HyperparameterTuner', 'ModelVersionManager', 'ABTestManager',
    'SelfLearningSystem',

    # Ensemble
    'EnsembleMethod', 'SignalType', 'ModelPrediction', 'EnsemblePrediction',
    'ModelWeight', 'StackingMetaLearner', 'BoostingEnsemble',
    'DynamicModelSelector', 'ModelEnsemble', 'TradingEnsemble',
]
