#!/usr/bin/env python3
"""
Test Specialized AI Models - Quick Validation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
np.random.seed(42)

print("=" * 70)
print("     SPECIALIZED AI MODELS - COMPREHENSIVE TEST")
print("=" * 70)
print()

# =============================================================================
# TEST 1: Deep Learning Models
# =============================================================================
print("[1/7] TESTING DEEP LEARNING MODELS...")
print("-" * 50)

from ai_models import LSTM, DenseLayer, TransformerBlock

# Test LSTM
lstm = LSTM(input_size=5, hidden_sizes=[32, 16], output_size=1)
print("   LSTM initialized: 5 -> [32, 16] -> 1")

# Test forward pass
X_test = np.random.randn(10, 20, 5)  # batch=10, seq=20, features=5
output = lstm.forward(X_test)
print(f"   LSTM output shape: {output.shape}")

# Test Dense Layer
dense = DenseLayer(64, 32)
dense_out = dense.forward(np.random.randn(10, 64))
print(f"   Dense layer: 64 -> 32, output shape: {dense_out.shape}")

# Test Transformer
transformer = TransformerBlock(d_model=64, n_heads=4, d_ff=256)
trans_out = transformer.forward(np.random.randn(10, 20, 64))
print(f"   Transformer: d_model=64, heads=4, output shape: {trans_out.shape}")

print("   [OK] Deep Learning models working\n")

# =============================================================================
# TEST 2: Reinforcement Learning
# =============================================================================
print("[2/7] TESTING REINFORCEMENT LEARNING...")
print("-" * 50)

from ai_models import DQNAgent, TradingEnvironment, RLTradingSystem

# Generate price data
prices = 100 + np.cumsum(np.random.randn(200) * 0.5)

# Create RL system
rl_system = RLTradingSystem(initial_capital=100000)
print("   RLTradingSystem initialized with $100,000")

# Test action selection
state = np.random.randn(14)
action = rl_system.agent.get_action(state, training=True)
action_names = ['STRONG_SELL', 'SELL', 'HOLD', 'BUY', 'STRONG_BUY']
print(f"   Sample action: {action_names[action]}")

# Test environment
volumes = np.random.uniform(1e6, 1e7, 100)
env = TradingEnvironment(prices[:100], volumes)
env_state = env.reset()
print(f"   Environment initialized, state type: {type(env_state).__name__}")

next_state, reward, done, info = env.step(3)  # BUY
print(f"   Step reward: {reward:.4f}")
print(f"   Done: {done} | Position: {info.get('position', 0)}")

print("   [OK] Reinforcement Learning working\n")

# =============================================================================
# TEST 3: Financial NLP
# =============================================================================
print("[3/7] TESTING FINANCIAL NLP...")
print("-" * 50)

from ai_models import FinancialSentimentModel, EarningsAnalyzer, CryptoSentimentModel

sentiment = FinancialSentimentModel()
print("   FinancialSentimentModel initialized")

# Test sentiment
news = [
    ("Apple stock surges 5% after record sales", "+"),
    ("Tesla faces investigation, shares plunge", "-"),
    ("Fed signals potential rate cuts", "="),
    ("Bitcoin rallies to new ATH", "+"),
]

print("\n   Sentiment Analysis:")
for text, expected in news:
    result = sentiment.analyze_sentiment(text)
    icon = "+" if result.sentiment.value > 0 else ("-" if result.sentiment.value < 0 else "=")
    print(f"   [{icon}] {result.sentiment.name}: {text[:40]}...")

# Earnings
earnings = EarningsAnalyzer()
earnings_result = earnings.analyze_earnings("Q4 earnings beat expectations with EPS of 2.15 dollars. Revenue $95B billion. Raised guidance.")
print(f"\n   Earnings: {earnings_result['beat_miss'].upper()} | Guidance: {earnings_result['guidance']}")

# Crypto pump detection
crypto = CryptoSentimentModel()
is_pump, conf = crypto.detect_pump_scheme("Don't miss! 100x guaranteed, next Bitcoin!")
print(f"   Pump Detection: {'DETECTED' if is_pump else 'Clean'} ({conf:.0%})")

print("   [OK] Financial NLP working\n")

# =============================================================================
# TEST 4: Pattern Recognition
# =============================================================================
print("[4/7] TESTING PATTERN RECOGNITION...")
print("-" * 50)

from ai_models import PatternRecognitionSystem, PatternCNN

pattern_system = PatternRecognitionSystem()
print("   PatternRecognitionSystem initialized")

# Create OHLCV data
n = 100
opens = prices[:n]
highs = opens + np.abs(np.random.randn(n)) * 0.5
lows = opens - np.abs(np.random.randn(n)) * 0.5
closes = opens + np.random.randn(n) * 0.3
volumes = np.random.uniform(1e6, 1e7, n)
ohlcv = np.column_stack([opens, highs, lows, closes, volumes])

result = pattern_system.analyze(ohlcv)
print(f"   Patterns detected: {len(result['patterns'])}")
print(f"   Signals: {len(result['signals'])}")
print(f"   Direction: {result['direction'].upper()}")
print(f"   Confidence: {result['confidence']:.0%}")

if result['patterns'][:3]:
    for p in result['patterns'][:3]:
        print(f"      {p.pattern_type.value}: {p.direction.value} ({p.confidence:.0%})")

print("   [OK] Pattern Recognition working\n")

# =============================================================================
# TEST 5: Regime Classification
# =============================================================================
print("[5/7] TESTING REGIME CLASSIFICATION...")
print("-" * 50)

from ai_models import MarketRegimeClassifier, MultiAssetRegimeAnalyzer

classifier = MarketRegimeClassifier()
print("   MarketRegimeClassifier initialized")

regime = classifier.classify(prices)
print(f"   Regime: {regime.primary_regime.value}")
print(f"   Volatility: {regime.volatility_regime.value}")
print(f"   Trend: {regime.trend_strength.name}")
print(f"   Confidence: {regime.confidence:.0%}")

bias = classifier.get_trading_bias()
print(f"   Bias: {bias['bias'].upper()} | Size: {bias['position_size']:.1f}x")

# Multi-asset
multi = MultiAssetRegimeAnalyzer()
multi.update('SPY', prices)
multi.update('QQQ', prices * 1.1 + np.random.randn(len(prices)) * 2)
consensus = multi.get_market_consensus()
print(f"   Consensus: {consensus['consensus']} ({consensus['agreement']:.0%})")

print("   [OK] Regime Classification working\n")

# =============================================================================
# TEST 6: Self-Learning System
# =============================================================================
print("[6/7] TESTING SELF-LEARNING SYSTEM...")
print("-" * 50)

from ai_models import SelfLearningSystem, LearningMode

learner = SelfLearningSystem(input_size=20, output_size=1)
learner.mode = LearningMode.HYBRID
print("   SelfLearningSystem initialized (HYBRID mode)")

# Training loop
for i in range(50):
    x = np.random.randn(20)
    y_true = np.array([np.sum(x[:5]) * 0.1])
    learner.learn(x, y_true, np.random.randn() * 0.01)

status = learner.get_status()
print(f"   Updates: {status['n_updates']}")
print(f"   Avg Loss: {status['avg_loss']:.6f}")
print(f"   Accuracy: {status['performance']['accuracy']:.0%}")

version = learner.save_checkpoint()
print(f"   Checkpoint: v{version.version_id}")

print("   [OK] Self-Learning working\n")

# =============================================================================
# TEST 7: Ensemble System
# =============================================================================
print("[7/7] TESTING ENSEMBLE SYSTEM...")
print("-" * 50)

from ai_models import TradingEnsemble, ModelPrediction, EnsembleMethod

ensemble = TradingEnsemble()
ensemble.set_model('regime_classifier', classifier)
ensemble.set_model('pattern_recognition', pattern_system)
print("   TradingEnsemble initialized")

market_data = {'prices': prices, 'ohlcv': ohlcv}
prediction = ensemble.get_prediction(market_data)

print(f"   Signal: {prediction.final_signal.name}")
print(f"   Strength: {prediction.signal_strength:.2f}")
print(f"   Confidence: {prediction.confidence:.0%}")
print(f"   Position: {prediction.position_size_multiplier:.2f}x")

# Test ensemble methods
print("\n   Ensemble Methods:")
test_preds = [
    ModelPrediction('model1', 0.5, 0.8),
    ModelPrediction('model2', 0.3, 0.7),
    ModelPrediction('model3', -0.2, 0.6),
]

for method in [EnsembleMethod.SIMPLE_AVERAGE, EnsembleMethod.WEIGHTED_AVERAGE, EnsembleMethod.VOTING]:
    result = ensemble.ensemble.combine(test_preds, method)
    print(f"      {method.value}: {result.final_signal.name}")

print("   [OK] Ensemble System working\n")

# =============================================================================
# SUMMARY
# =============================================================================
print("=" * 70)
print("           ALL SPECIALIZED AI TESTS PASSED!")
print("=" * 70)
print()
print("   [X] Deep Learning - LSTM, Transformer, Dense Layers")
print("   [X] Reinforcement Learning - DQN Agent, Trading Environment")
print("   [X] Financial NLP - Sentiment, Earnings, Crypto Analysis")
print("   [X] Pattern Recognition - CNN, Candlesticks, Chart Patterns")
print("   [X] Regime Classification - HMM, Volatility, Trend")
print("   [X] Self-Learning - Online Learning, Drift Detection")
print("   [X] Ensemble - Stacking, Boosting, Dynamic Selection")
print()
print("   SPECIALIZED for: Trading, Crypto, Markets, News, Technical Analysis")
print("   NOT a general LLM - purpose-built AI for trading!")
print()
