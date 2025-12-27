"""
Data Pipeline

ETL and data flow management:
- Data ingestion from multiple sources
- Transformation and normalization
- Feature engineering pipeline
- Data validation and quality checks
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Iterator
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from collections import deque
import threading
import time


@dataclass
class DataRecord:
    """Generic data record."""
    data: Any
    timestamp: datetime
    source: str
    metadata: Dict = field(default_factory=dict)


class DataSource(ABC):
    """
    Abstract data source.

    Sources provide data to the pipeline.
    """

    @abstractmethod
    def connect(self):
        """Connect to the data source."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the data source."""
        pass

    @abstractmethod
    def read(self) -> Iterator[DataRecord]:
        """Read data from the source."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Source name."""
        pass


class DataSink(ABC):
    """
    Abstract data sink.

    Sinks receive processed data.
    """

    @abstractmethod
    def connect(self):
        """Connect to the sink."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the sink."""
        pass

    @abstractmethod
    def write(self, record: DataRecord):
        """Write a record to the sink."""
        pass

    @abstractmethod
    def flush(self):
        """Flush buffered data."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Sink name."""
        pass


class Transform(ABC):
    """
    Data transformation.

    Transforms modify data as it flows through the pipeline.
    """

    @abstractmethod
    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        """
        Transform a record.

        Returns None to filter out the record.
        """
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


class DataPipeline:
    """
    Data processing pipeline.

    Connects sources, transforms, and sinks.
    """

    def __init__(self, name: str):
        self.name = name
        self.sources: List[DataSource] = []
        self.transforms: List[Transform] = []
        self.sinks: List[DataSink] = []

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {
            'records_read': 0,
            'records_written': 0,
            'records_filtered': 0,
            'errors': 0
        }

    def add_source(self, source: DataSource):
        """Add a data source."""
        self.sources.append(source)

    def add_transform(self, transform: Transform):
        """Add a transformation."""
        self.transforms.append(transform)

    def add_sink(self, sink: DataSink):
        """Add a data sink."""
        self.sinks.append(sink)

    def start(self):
        """Start the pipeline."""
        if self._running:
            return

        # Connect all components
        for source in self.sources:
            source.connect()

        for sink in self.sinks:
            sink.connect()

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the pipeline."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=5)

        # Flush and disconnect
        for sink in self.sinks:
            sink.flush()
            sink.disconnect()

        for source in self.sources:
            source.disconnect()

    def _run_loop(self):
        """Main processing loop."""
        while self._running:
            for source in self.sources:
                try:
                    for record in source.read():
                        self._process_record(record)
                except Exception as e:
                    self._stats['errors'] += 1

            time.sleep(0.001)  # Small sleep to prevent busy loop

    def _process_record(self, record: DataRecord):
        """Process a single record through the pipeline."""
        self._stats['records_read'] += 1

        # Apply transforms
        current = record
        for transform in self.transforms:
            try:
                current = transform.transform(current)
                if current is None:
                    self._stats['records_filtered'] += 1
                    return
            except Exception as e:
                self._stats['errors'] += 1
                return

        # Write to sinks
        for sink in self.sinks:
            try:
                sink.write(current)
                self._stats['records_written'] += 1
            except Exception as e:
                self._stats['errors'] += 1

    def process_batch(self, records: List[DataRecord]) -> List[DataRecord]:
        """Process a batch of records synchronously."""
        results = []

        for record in records:
            current = record
            skip = False

            for transform in self.transforms:
                current = transform.transform(current)
                if current is None:
                    skip = True
                    break

            if not skip:
                results.append(current)

        return results

    def get_stats(self) -> Dict:
        """Get pipeline statistics."""
        return self._stats.copy()


# Common Transforms

class FilterTransform(Transform):
    """Filter records based on a condition."""

    def __init__(self, condition: Callable[[DataRecord], bool]):
        self.condition = condition

    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        if self.condition(record):
            return record
        return None


class MapTransform(Transform):
    """Apply a function to record data."""

    def __init__(self, map_fn: Callable[[Any], Any]):
        self.map_fn = map_fn

    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        try:
            new_data = self.map_fn(record.data)
            return DataRecord(
                data=new_data,
                timestamp=record.timestamp,
                source=record.source,
                metadata=record.metadata
            )
        except Exception:
            return None


class EnrichTransform(Transform):
    """Enrich records with additional data."""

    def __init__(self, enrich_fn: Callable[[DataRecord], Dict]):
        self.enrich_fn = enrich_fn

    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        try:
            additional = self.enrich_fn(record)
            new_metadata = {**record.metadata, **additional}
            return DataRecord(
                data=record.data,
                timestamp=record.timestamp,
                source=record.source,
                metadata=new_metadata
            )
        except Exception:
            return record


class ValidateTransform(Transform):
    """Validate records against a schema."""

    def __init__(self, validator: Callable[[Any], bool]):
        self.validator = validator

    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        if self.validator(record.data):
            return record
        return None


class AggregateTransform(Transform):
    """Aggregate records over a window."""

    def __init__(
        self,
        window_size: int,
        agg_fn: Callable[[List[Any]], Any]
    ):
        self.window_size = window_size
        self.agg_fn = agg_fn
        self.buffer: deque = deque(maxlen=window_size)

    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        self.buffer.append(record.data)

        if len(self.buffer) < self.window_size:
            return None

        aggregated = self.agg_fn(list(self.buffer))
        return DataRecord(
            data=aggregated,
            timestamp=record.timestamp,
            source=record.source,
            metadata={'aggregated': True, 'window_size': self.window_size}
        )


# Common Sources

class MemorySource(DataSource):
    """In-memory data source for testing."""

    def __init__(self, name: str, data: List[Any] = None):
        self._name = name
        self._data = deque(data or [])
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def read(self) -> Iterator[DataRecord]:
        while self._data:
            item = self._data.popleft()
            yield DataRecord(
                data=item,
                timestamp=datetime.now(),
                source=self._name
            )

    def add(self, data: Any):
        """Add data to the source."""
        self._data.append(data)


class MemorySink(DataSink):
    """In-memory data sink for testing."""

    def __init__(self, name: str):
        self._name = name
        self._data: List[DataRecord] = []
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def write(self, record: DataRecord):
        self._data.append(record)

    def flush(self):
        pass

    def get_data(self) -> List[DataRecord]:
        """Get all written data."""
        return self._data.copy()

    def clear(self):
        """Clear stored data."""
        self._data.clear()


class BatchSource(DataSource):
    """Source that yields data in batches."""

    def __init__(
        self,
        name: str,
        batch_generator: Callable[[], List[Any]],
        interval_seconds: float = 1.0
    ):
        self._name = name
        self.batch_generator = batch_generator
        self.interval = interval_seconds
        self._connected = False
        self._last_fetch = None

    @property
    def name(self) -> str:
        return self._name

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def read(self) -> Iterator[DataRecord]:
        now = datetime.now()

        if self._last_fetch and (now - self._last_fetch).total_seconds() < self.interval:
            return

        self._last_fetch = now

        try:
            batch = self.batch_generator()
            for item in batch:
                yield DataRecord(
                    data=item,
                    timestamp=now,
                    source=self._name
                )
        except Exception:
            pass


class BufferedSink(DataSink):
    """Sink that buffers writes."""

    def __init__(
        self,
        name: str,
        inner_sink: DataSink,
        buffer_size: int = 100,
        flush_interval_seconds: float = 5.0
    ):
        self._name = name
        self.inner = inner_sink
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval_seconds
        self._buffer: List[DataRecord] = []
        self._last_flush = datetime.now()
        self._connected = False

    @property
    def name(self) -> str:
        return self._name

    def connect(self):
        self.inner.connect()
        self._connected = True

    def disconnect(self):
        self.flush()
        self.inner.disconnect()
        self._connected = False

    def write(self, record: DataRecord):
        self._buffer.append(record)

        if len(self._buffer) >= self.buffer_size:
            self.flush()
        elif (datetime.now() - self._last_flush).total_seconds() > self.flush_interval:
            self.flush()

    def flush(self):
        for record in self._buffer:
            self.inner.write(record)
        self.inner.flush()
        self._buffer.clear()
        self._last_flush = datetime.now()


class FeatureEngineeringPipeline:
    """
    Specialized pipeline for feature engineering.

    Computes features from raw market data.
    """

    def __init__(self):
        self.feature_functions: Dict[str, Callable] = {}
        self.feature_cache: Dict[str, deque] = {}
        self.window_size = 100

    def register_feature(
        self,
        name: str,
        compute_fn: Callable[[np.ndarray], float]
    ):
        """Register a feature computation function."""
        self.feature_functions[name] = compute_fn
        self.feature_cache[name] = deque(maxlen=self.window_size)

    def compute_features(
        self,
        prices: np.ndarray,
        volumes: np.ndarray = None
    ) -> Dict[str, float]:
        """Compute all registered features."""
        features = {}

        for name, compute_fn in self.feature_functions.items():
            try:
                value = compute_fn(prices, volumes) if volumes is not None else compute_fn(prices)
                features[name] = value
                self.feature_cache[name].append(value)
            except Exception:
                features[name] = np.nan

        return features

    def get_feature_history(self, name: str) -> np.ndarray:
        """Get historical values for a feature."""
        if name in self.feature_cache:
            return np.array(self.feature_cache[name])
        return np.array([])

    # Standard features
    @staticmethod
    def returns(prices: np.ndarray, periods: int = 1) -> float:
        if len(prices) < periods + 1:
            return np.nan
        return (prices[-1] - prices[-periods - 1]) / prices[-periods - 1]

    @staticmethod
    def volatility(prices: np.ndarray, window: int = 20) -> float:
        if len(prices) < window + 1:
            return np.nan
        returns = np.diff(np.log(prices[-window - 1:]))
        return np.std(returns) * np.sqrt(252)

    @staticmethod
    def sma(prices: np.ndarray, window: int = 20) -> float:
        if len(prices) < window:
            return np.nan
        return np.mean(prices[-window:])

    @staticmethod
    def ema(prices: np.ndarray, window: int = 20) -> float:
        if len(prices) < window:
            return np.nan
        alpha = 2 / (window + 1)
        ema = prices[-window]
        for price in prices[-window + 1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    @staticmethod
    def rsi(prices: np.ndarray, window: int = 14) -> float:
        if len(prices) < window + 1:
            return np.nan

        deltas = np.diff(prices[-window - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
