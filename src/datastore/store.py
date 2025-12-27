"""
Data Storage

Efficient storage for time-series and feature data:
- Time-series storage with compression
- Feature store for ML features
- Caching layer
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import pickle
import gzip
import json


@dataclass
class TimeSeriesChunk:
    """Chunk of time-series data."""
    start_time: datetime
    end_time: datetime
    timestamps: np.ndarray
    values: np.ndarray
    metadata: Dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.timestamps)


class TimeSeriesStore:
    """
    Efficient time-series data storage.

    Features:
    - In-memory storage with chunking
    - Compression for historical data
    - Fast range queries
    - Downsampling support
    """

    def __init__(
        self,
        chunk_size: int = 10000,
        max_memory_mb: float = 1000.0
    ):
        """
        Initialize time-series store.

        Args:
            chunk_size: Records per chunk
            max_memory_mb: Maximum memory usage
        """
        self.chunk_size = chunk_size
        self.max_memory = max_memory_mb * 1024 * 1024

        # Data by symbol -> list of chunks
        self.data: Dict[str, List[TimeSeriesChunk]] = {}

        # Current (active) chunk for writes
        self.current_chunks: Dict[str, Dict] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Stats
        self._stats = {
            'writes': 0,
            'reads': 0,
            'chunks_created': 0
        }

    def write(
        self,
        symbol: str,
        timestamp: datetime,
        value: float,
        **metadata
    ):
        """Write a single data point."""
        with self._lock:
            if symbol not in self.current_chunks:
                self.current_chunks[symbol] = {
                    'timestamps': [],
                    'values': [],
                    'metadata': []
                }

            chunk = self.current_chunks[symbol]
            chunk['timestamps'].append(timestamp)
            chunk['values'].append(value)
            chunk['metadata'].append(metadata)

            self._stats['writes'] += 1

            # Check if chunk is full
            if len(chunk['timestamps']) >= self.chunk_size:
                self._flush_chunk(symbol)

    def write_batch(
        self,
        symbol: str,
        timestamps: List[datetime],
        values: List[float]
    ):
        """Write a batch of data points."""
        for ts, val in zip(timestamps, values):
            self.write(symbol, ts, val)

    def _flush_chunk(self, symbol: str):
        """Flush current chunk to storage."""
        if symbol not in self.current_chunks:
            return

        chunk_data = self.current_chunks[symbol]
        if not chunk_data['timestamps']:
            return

        timestamps = np.array([ts.timestamp() for ts in chunk_data['timestamps']])
        values = np.array(chunk_data['values'])

        chunk = TimeSeriesChunk(
            start_time=chunk_data['timestamps'][0],
            end_time=chunk_data['timestamps'][-1],
            timestamps=timestamps,
            values=values
        )

        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].append(chunk)

        self._stats['chunks_created'] += 1

        # Clear current chunk
        self.current_chunks[symbol] = {
            'timestamps': [],
            'values': [],
            'metadata': []
        }

    def read(
        self,
        symbol: str,
        start: datetime = None,
        end: datetime = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Read time-series data.

        Returns (timestamps, values) arrays.
        """
        with self._lock:
            self._stats['reads'] += 1

            # Flush current chunk to ensure we get latest data
            if symbol in self.current_chunks and self.current_chunks[symbol]['timestamps']:
                self._flush_chunk(symbol)

            if symbol not in self.data:
                return np.array([]), np.array([])

            all_timestamps = []
            all_values = []

            start_ts = start.timestamp() if start else 0
            end_ts = end.timestamp() if end else float('inf')

            for chunk in self.data[symbol]:
                # Skip chunks outside range
                if chunk.end_time.timestamp() < start_ts:
                    continue
                if chunk.start_time.timestamp() > end_ts:
                    continue

                # Filter data within chunk
                mask = (chunk.timestamps >= start_ts) & (chunk.timestamps <= end_ts)
                all_timestamps.extend(chunk.timestamps[mask])
                all_values.extend(chunk.values[mask])

            if not all_timestamps:
                return np.array([]), np.array([])

            return np.array(all_timestamps), np.array(all_values)

    def get_latest(self, symbol: str, n: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """Get the latest n data points."""
        timestamps, values = self.read(symbol)

        if len(timestamps) == 0:
            return np.array([]), np.array([])

        return timestamps[-n:], values[-n:]

    def get_symbols(self) -> List[str]:
        """Get all symbols in the store."""
        with self._lock:
            return list(self.data.keys())

    def get_stats(self) -> Dict:
        """Get store statistics."""
        with self._lock:
            total_points = sum(
                sum(len(chunk) for chunk in chunks)
                for chunks in self.data.values()
            )

            return {
                **self._stats,
                'symbols': len(self.data),
                'total_points': total_points,
                'chunks': sum(len(chunks) for chunks in self.data.values())
            }

    def resample(
        self,
        symbol: str,
        interval: timedelta,
        agg_fn: str = 'last'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Resample data to a lower frequency.

        Args:
            symbol: Symbol to resample
            interval: Target interval
            agg_fn: Aggregation function ('last', 'first', 'mean', 'sum', 'min', 'max')
        """
        timestamps, values = self.read(symbol)

        if len(timestamps) == 0:
            return np.array([]), np.array([])

        interval_seconds = interval.total_seconds()
        start_ts = timestamps[0]
        end_ts = timestamps[-1]

        new_timestamps = []
        new_values = []

        current_ts = start_ts
        while current_ts <= end_ts:
            next_ts = current_ts + interval_seconds

            mask = (timestamps >= current_ts) & (timestamps < next_ts)
            bucket = values[mask]

            if len(bucket) > 0:
                if agg_fn == 'last':
                    agg_value = bucket[-1]
                elif agg_fn == 'first':
                    agg_value = bucket[0]
                elif agg_fn == 'mean':
                    agg_value = np.mean(bucket)
                elif agg_fn == 'sum':
                    agg_value = np.sum(bucket)
                elif agg_fn == 'min':
                    agg_value = np.min(bucket)
                elif agg_fn == 'max':
                    agg_value = np.max(bucket)
                else:
                    agg_value = bucket[-1]

                new_timestamps.append(current_ts)
                new_values.append(agg_value)

            current_ts = next_ts

        return np.array(new_timestamps), np.array(new_values)


class FeatureStore:
    """
    Feature store for ML models.

    Stores and serves computed features:
    - Point-in-time correct feature retrieval
    - Feature versioning
    - Feature lineage tracking
    """

    def __init__(
        self,
        max_history: int = 100000,
        cache_size: int = 1000
    ):
        """
        Initialize feature store.

        Args:
            max_history: Maximum feature history per symbol
            cache_size: LRU cache size
        """
        self.max_history = max_history
        self.cache_size = cache_size

        # Features: symbol -> feature_name -> list of (timestamp, value)
        self.features: Dict[str, Dict[str, List[Tuple[datetime, Any]]]] = {}

        # Feature metadata
        self.feature_metadata: Dict[str, Dict] = {}

        # LRU cache for recent queries
        self._cache: OrderedDict = OrderedDict()

        self._lock = threading.RLock()

    def register_feature(
        self,
        name: str,
        description: str = "",
        dtype: str = "float",
        version: str = "1.0"
    ):
        """Register a feature definition."""
        self.feature_metadata[name] = {
            'name': name,
            'description': description,
            'dtype': dtype,
            'version': version,
            'created_at': datetime.now()
        }

    def write_feature(
        self,
        symbol: str,
        feature_name: str,
        value: Any,
        timestamp: datetime = None
    ):
        """Write a feature value."""
        timestamp = timestamp or datetime.now()

        with self._lock:
            if symbol not in self.features:
                self.features[symbol] = {}

            if feature_name not in self.features[symbol]:
                self.features[symbol][feature_name] = []

            feature_list = self.features[symbol][feature_name]
            feature_list.append((timestamp, value))

            # Trim if too long
            if len(feature_list) > self.max_history:
                self.features[symbol][feature_name] = feature_list[-self.max_history:]

            # Invalidate cache
            cache_key = (symbol, feature_name)
            if cache_key in self._cache:
                del self._cache[cache_key]

    def write_features(
        self,
        symbol: str,
        features: Dict[str, Any],
        timestamp: datetime = None
    ):
        """Write multiple features at once."""
        for name, value in features.items():
            self.write_feature(symbol, name, value, timestamp)

    def get_feature(
        self,
        symbol: str,
        feature_name: str,
        timestamp: datetime = None
    ) -> Optional[Any]:
        """
        Get a feature value.

        If timestamp provided, returns point-in-time correct value.
        """
        with self._lock:
            if symbol not in self.features:
                return None

            if feature_name not in self.features[symbol]:
                return None

            feature_list = self.features[symbol][feature_name]

            if not feature_list:
                return None

            if timestamp is None:
                # Return latest
                return feature_list[-1][1]

            # Find point-in-time correct value
            for ts, value in reversed(feature_list):
                if ts <= timestamp:
                    return value

            return None

    def get_features(
        self,
        symbol: str,
        feature_names: List[str] = None,
        timestamp: datetime = None
    ) -> Dict[str, Any]:
        """Get multiple features."""
        with self._lock:
            if symbol not in self.features:
                return {}

            if feature_names is None:
                feature_names = list(self.features[symbol].keys())

            return {
                name: self.get_feature(symbol, name, timestamp)
                for name in feature_names
                if name in self.features[symbol]
            }

    def get_feature_history(
        self,
        symbol: str,
        feature_name: str,
        start: datetime = None,
        end: datetime = None
    ) -> List[Tuple[datetime, Any]]:
        """Get feature history."""
        with self._lock:
            if symbol not in self.features:
                return []

            if feature_name not in self.features[symbol]:
                return []

            feature_list = self.features[symbol][feature_name]

            if start is None and end is None:
                return feature_list.copy()

            result = []
            for ts, value in feature_list:
                if start and ts < start:
                    continue
                if end and ts > end:
                    continue
                result.append((ts, value))

            return result

    def get_feature_vector(
        self,
        symbol: str,
        feature_names: List[str],
        timestamp: datetime = None
    ) -> np.ndarray:
        """Get features as a numpy array."""
        features = self.get_features(symbol, feature_names, timestamp)

        vector = []
        for name in feature_names:
            value = features.get(name)
            if value is None:
                vector.append(np.nan)
            else:
                vector.append(float(value))

        return np.array(vector)

    def get_all_symbols(self) -> List[str]:
        """Get all symbols with features."""
        with self._lock:
            return list(self.features.keys())

    def get_all_features(self, symbol: str = None) -> List[str]:
        """Get all feature names."""
        with self._lock:
            if symbol:
                if symbol in self.features:
                    return list(self.features[symbol].keys())
                return []
            else:
                return list(self.feature_metadata.keys())

    def get_stats(self) -> Dict:
        """Get store statistics."""
        with self._lock:
            total_features = sum(
                len(features)
                for features in self.features.values()
            )

            total_values = sum(
                sum(len(values) for values in symbol_features.values())
                for symbol_features in self.features.values()
            )

            return {
                'symbols': len(self.features),
                'total_features': total_features,
                'total_values': total_values,
                'registered_features': len(self.feature_metadata),
                'cache_size': len(self._cache)
            }


class DataCache:
    """
    LRU cache for data access.

    Reduces repeated data fetches.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300):
        """
        Initialize cache.

        Args:
            max_size: Maximum cache entries
            ttl_seconds: Time-to-live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl_seconds

        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, datetime] = {}
        self._lock = threading.Lock()

        self._stats = {
            'hits': 0,
            'misses': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None

            # Check TTL
            if (datetime.now() - self._timestamps[key]).total_seconds() > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                self._stats['misses'] += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._stats['hits'] += 1
            return self._cache[key]

    def set(self, key: str, value: Any):
        """Set a cached value."""
        with self._lock:
            # Remove oldest if full
            while len(self._cache) >= self.max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                del self._timestamps[oldest]

            self._cache[key] = value
            self._timestamps[key] = datetime.now()

    def invalidate(self, key: str):
        """Invalidate a cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]

    def clear(self):
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._stats['hits'] + self._stats['misses']
        return self._stats['hits'] / total if total > 0 else 0
