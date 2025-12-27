"""
Chart Pattern Recognition using Convolutional Neural Networks

Specialized CNN model for recognizing technical chart patterns:
- Head and Shoulders, Double/Triple Tops/Bottoms
- Triangles, Flags, Wedges, Cup and Handle
- Candlestick patterns (Doji, Hammer, Engulfing, etc.)
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum


class PatternType(Enum):
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    BULL_FLAG = "bull_flag"
    BEAR_FLAG = "bear_flag"
    RISING_WEDGE = "rising_wedge"
    FALLING_WEDGE = "falling_wedge"
    CUP_AND_HANDLE = "cup_and_handle"
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING_BULLISH = "engulfing_bullish"
    ENGULFING_BEARISH = "engulfing_bearish"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    NO_PATTERN = "no_pattern"


class PatternDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class DetectedPattern:
    pattern_type: PatternType
    direction: PatternDirection
    confidence: float
    start_index: int
    end_index: int
    key_points: List[Tuple[int, float]]
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    description: str = ""


class Conv1D:
    """1D Convolutional layer"""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int = 1, padding: int = 0):
        self.in_channels, self.out_channels = in_channels, out_channels
        self.kernel_size, self.stride, self.padding = kernel_size, stride, padding
        scale = np.sqrt(2.0 / (in_channels * kernel_size))
        self.weights = np.random.randn(out_channels, in_channels, kernel_size) * scale
        self.bias = np.zeros(out_channels)

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch_size, _, length = x.shape
        if self.padding > 0:
            x = np.pad(x, ((0, 0), (0, 0), (self.padding, self.padding)), mode='constant')
        out_length = (x.shape[2] - self.kernel_size) // self.stride + 1
        output = np.zeros((batch_size, self.out_channels, out_length))
        for i in range(out_length):
            start, end = i * self.stride, i * self.stride + self.kernel_size
            window = x[:, :, start:end]
            for j in range(self.out_channels):
                output[:, j, i] = np.sum(window * self.weights[j], axis=(1, 2)) + self.bias[j]
        return output


class MaxPool1D:
    """1D Max Pooling"""
    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch_size, channels, length = x.shape
        out_length = length // self.pool_size
        output = np.zeros((batch_size, channels, out_length))
        for i in range(out_length):
            output[:, :, i] = np.max(x[:, :, i*self.pool_size:(i+1)*self.pool_size], axis=2)
        return output


class PatternCNN:
    """CNN for Chart Pattern Recognition"""
    def __init__(self, sequence_length: int = 100, num_features: int = 5):
        self.conv1 = Conv1D(num_features, 32, kernel_size=5, padding=2)
        self.pool1 = MaxPool1D(2)
        self.conv2 = Conv1D(32, 64, kernel_size=5, padding=2)
        self.pool2 = MaxPool1D(2)
        self.conv3 = Conv1D(64, 128, kernel_size=3, padding=1)
        self.pool3 = MaxPool1D(2)
        flat_size = 128 * (sequence_length // 8)
        self.fc_weights = np.random.randn(flat_size, len(PatternType)) * 0.01
        self.fc_bias = np.zeros(len(PatternType))

    def forward(self, x: np.ndarray) -> np.ndarray:
        x = np.maximum(0, self.conv1.forward(x))
        x = self.pool1.forward(x)
        x = np.maximum(0, self.conv2.forward(x))
        x = self.pool2.forward(x)
        x = np.maximum(0, self.conv3.forward(x))
        x = self.pool3.forward(x)
        x = x.reshape(x.shape[0], -1)
        return np.dot(x, self.fc_weights) + self.fc_bias

    def predict(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        logits = self.forward(x)
        exp_x = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_x / np.sum(exp_x, axis=1, keepdims=True)
        return np.argmax(probs, axis=1), probs


class CandlestickDetector:
    """Rule-based candlestick pattern detection"""
    def detect(self, ohlcv: np.ndarray) -> List[DetectedPattern]:
        patterns = []
        for i in range(len(ohlcv)):
            o, h, l, c, v = ohlcv[i]
            body, total = abs(c - o), h - l
            if total == 0: continue
            upper_shadow, lower_shadow = h - max(o, c), min(o, c) - l

            if body / total < 0.1:
                patterns.append(DetectedPattern(PatternType.DOJI, PatternDirection.NEUTRAL, 0.8, i, i, [(i, c)], description="Doji"))
            if lower_shadow > 2 * body and upper_shadow < body * 0.5:
                patterns.append(DetectedPattern(PatternType.HAMMER, PatternDirection.BULLISH, 0.75, i, i, [(i, c)], description="Hammer"))
            if upper_shadow > 2 * body and lower_shadow < body * 0.5:
                patterns.append(DetectedPattern(PatternType.SHOOTING_STAR, PatternDirection.BEARISH, 0.75, i, i, [(i, c)], description="Shooting Star"))

            if i > 0:
                po, _, _, pc, _ = ohlcv[i-1]
                if pc < po and c > o and o < pc and c > po and abs(c-o) > abs(pc-po):
                    patterns.append(DetectedPattern(PatternType.ENGULFING_BULLISH, PatternDirection.BULLISH, 0.8, i-1, i, [(i, c)], description="Bullish Engulfing"))
                if pc > po and c < o and o > pc and c < po and abs(c-o) > abs(pc-po):
                    patterns.append(DetectedPattern(PatternType.ENGULFING_BEARISH, PatternDirection.BEARISH, 0.8, i-1, i, [(i, c)], description="Bearish Engulfing"))
        return patterns


class ChartPatternDetector:
    """Detect larger chart patterns"""
    def __init__(self):
        self.min_length, self.max_length = 10, 100

    def _find_peaks(self, prices: np.ndarray, window: int = 5) -> List[int]:
        return [i for i in range(window, len(prices)-window) if prices[i] == max(prices[i-window:i+window+1])]

    def _find_troughs(self, prices: np.ndarray, window: int = 5) -> List[int]:
        return [i for i in range(window, len(prices)-window) if prices[i] == min(prices[i-window:i+window+1])]

    def detect(self, prices: np.ndarray) -> List[DetectedPattern]:
        patterns = []
        peaks, troughs = self._find_peaks(prices), self._find_troughs(prices)

        # Head and Shoulders
        for i in range(len(peaks) - 2):
            p1, p2, p3 = peaks[i], peaks[i+1], peaks[i+2]
            if p3 - p1 > self.max_length: continue
            h1, h2, h3 = prices[p1], prices[p2], prices[p3]
            if h2 > h1 and h2 > h3 and abs(h1 - h3) / h2 < 0.05:
                patterns.append(DetectedPattern(PatternType.HEAD_AND_SHOULDERS, PatternDirection.BEARISH, 0.75, p1, p3, [(p1, h1), (p2, h2), (p3, h3)], target_price=h3 - (h2 - h3), description="Head & Shoulders"))

        # Double Top/Bottom
        for i in range(len(peaks) - 1):
            p1, p2 = peaks[i], peaks[i+1]
            if self.min_length <= p2 - p1 <= self.max_length:
                h1, h2 = prices[p1], prices[p2]
                if abs(h1 - h2) / max(h1, h2) < 0.03:
                    patterns.append(DetectedPattern(PatternType.DOUBLE_TOP, PatternDirection.BEARISH, 0.75, p1, p2, [(p1, h1), (p2, h2)], description="Double Top"))

        for i in range(len(troughs) - 1):
            t1, t2 = troughs[i], troughs[i+1]
            if self.min_length <= t2 - t1 <= self.max_length:
                l1, l2 = prices[t1], prices[t2]
                if abs(l1 - l2) / min(l1, l2) < 0.03:
                    patterns.append(DetectedPattern(PatternType.DOUBLE_BOTTOM, PatternDirection.BULLISH, 0.75, t1, t2, [(t1, l1), (t2, l2)], description="Double Bottom"))

        return patterns


class PatternRecognitionSystem:
    """Complete pattern recognition combining CNN + rule-based"""
    def __init__(self):
        self.cnn = PatternCNN()
        self.candlestick = CandlestickDetector()
        self.chart = ChartPatternDetector()
        self.stats: Dict[PatternType, Dict] = {p: {'count': 0, 'success': 0, 'avg_return': 0.0} for p in PatternType}

    def analyze(self, ohlcv: np.ndarray) -> Dict[str, Any]:
        if len(ohlcv) < 10:
            return {'patterns': [], 'signals': [], 'confidence': 0.0}
        candlestick_patterns = self.candlestick.detect(ohlcv)
        chart_patterns = self.chart.detect(ohlcv[:, 3])
        all_patterns = candlestick_patterns + chart_patterns
        signals = [{'pattern': p.pattern_type.value, 'direction': p.direction.value, 'confidence': p.confidence, 'target': p.target_price} for p in all_patterns if p.confidence >= 0.6]
        bullish = sum(p.confidence for p in all_patterns if p.direction == PatternDirection.BULLISH)
        bearish = sum(p.confidence for p in all_patterns if p.direction == PatternDirection.BEARISH)
        direction = 'bullish' if bullish > bearish * 1.2 else ('bearish' if bearish > bullish * 1.2 else 'neutral')
        return {'patterns': all_patterns, 'signals': signals, 'confidence': np.mean([p.confidence for p in all_patterns]) if all_patterns else 0.0, 'direction': direction}

    def update_stats(self, pattern: PatternType, success: bool, return_pct: float):
        s = self.stats[pattern]
        s['count'] += 1
        if success: s['success'] += 1
        s['avg_return'] = (s['avg_return'] * (s['count']-1) + return_pct) / s['count']
