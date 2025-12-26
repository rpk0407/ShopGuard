"""
Temporal Neural Networks for Financial Time Series

This module implements architectures specifically designed for:
1. Multi-horizon forecasting
2. Volatility regime detection
3. Non-stationary time series
4. Multi-modal data fusion (price + volume + sentiment + macro)

Architecture Philosophy:
- LSTMs: Good at learning long-term dependencies
- Transformers: Good at learning attention patterns
- Hybrid: Combine strengths of both
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, Dict
import math


class LSTMEncoder(nn.Module):
    """
    LSTM Encoder for temporal feature extraction.

    LSTMs (Long Short-Term Memory) are recurrent networks that can
    learn to store and forget information over long sequences.

    Key components:
    - Input gate: What new information to store
    - Forget gate: What old information to discard
    - Output gate: What to output from cell state

    For trading:
    - Captures momentum/mean-reversion patterns over time
    - Learns seasonal effects automatically
    - Handles variable-length sequences
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = False
    ):
        """
        Initialize LSTM encoder.

        Args:
            input_dim: Number of input features per timestep
            hidden_dim: LSTM hidden state dimension
            num_layers: Number of stacked LSTM layers
            dropout: Dropout between layers
            bidirectional: Use bidirectional LSTM (for backtesting only!)
        """
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional

        # Input projection
        self.input_projection = nn.Linear(input_dim, hidden_dim)

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
            bidirectional=bidirectional
        )

        # Layer normalization for stability
        self.layer_norm = nn.LayerNorm(hidden_dim * (2 if bidirectional else 1))

    def forward(
        self,
        x: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass.

        Args:
            x: Input tensor (batch, seq_len, input_dim)
            hidden: Optional initial hidden state

        Returns:
            Tuple of (output sequence, final hidden state)
        """
        # Project input
        x = self.input_projection(x)

        # LSTM forward
        output, hidden = self.lstm(x, hidden)

        # Normalize
        output = self.layer_norm(output)

        return output, hidden

    def get_final_encoding(self, x: torch.Tensor) -> torch.Tensor:
        """Get the final hidden state as a fixed-size encoding."""
        output, (h_n, c_n) = self.forward(x)

        if self.bidirectional:
            # Concatenate forward and backward final states
            final = torch.cat([h_n[-2], h_n[-1]], dim=-1)
        else:
            final = h_n[-1]

        return final


class TransformerEncoder(nn.Module):
    """
    Transformer Encoder for attention-based temporal modeling.

    Transformers use self-attention to weigh the importance of
    different time steps when making predictions.

    Key advantages for trading:
    - Explicit attention: See WHICH past events matter
    - Parallel computation: Faster than RNNs
    - Variable context: Adapt attention based on market regime

    Key design choices:
    - Causal masking: Can only attend to past (no future leakage!)
    - Relative position encoding: Better for variable-length sequences
    - Sparse attention: Focus on important time points
    """

    def __init__(
        self,
        input_dim: int,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 256,
        dropout: float = 0.1,
        max_seq_len: int = 512
    ):
        """
        Initialize Transformer encoder.

        Args:
            input_dim: Input feature dimension
            d_model: Model dimension (must be divisible by nhead)
            nhead: Number of attention heads
            num_layers: Number of transformer layers
            dim_feedforward: Feedforward network dimension
            dropout: Dropout rate
            max_seq_len: Maximum sequence length
        """
        super().__init__()

        self.d_model = d_model
        self.max_seq_len = max_seq_len

        # Input projection
        self.input_projection = nn.Linear(input_dim, d_model)

        # Positional encoding
        self.positional_encoding = self._create_positional_encoding(max_seq_len, d_model)
        self.register_buffer('pos_encoding', self.positional_encoding)

        # Transformer layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Output layer norm
        self.output_norm = nn.LayerNorm(d_model)

    def _create_positional_encoding(self, max_len: int, d_model: int) -> torch.Tensor:
        """
        Create sinusoidal positional encodings.

        PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
        PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
        """
        position = torch.arange(max_len).unsqueeze(1).float()
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )

        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        return pe.unsqueeze(0)  # (1, max_len, d_model)

    def _create_causal_mask(self, seq_len: int) -> torch.Tensor:
        """
        Create causal mask to prevent attending to future.

        CRITICAL: Without this, the model would cheat by looking ahead.
        """
        mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1)
        mask = mask.masked_fill(mask == 1, float('-inf'))
        return mask

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input tensor (batch, seq_len, input_dim)

        Returns:
            Encoded sequence (batch, seq_len, d_model)
        """
        batch_size, seq_len, _ = x.shape

        # Project input
        x = self.input_projection(x)

        # Add positional encoding
        x = x + self.pos_encoding[:, :seq_len, :]

        # Create causal mask
        causal_mask = self._create_causal_mask(seq_len).to(x.device)

        # Transformer forward
        output = self.transformer(x, mask=causal_mask)

        # Normalize
        output = self.output_norm(output)

        return output

    def get_attention_weights(self, x: torch.Tensor) -> torch.Tensor:
        """
        Extract attention weights for interpretability.

        Returns attention matrix showing which time steps
        the model focuses on.
        """
        # This requires modifying the forward pass to return attention
        # For now, return placeholder
        batch_size, seq_len, _ = x.shape
        return torch.zeros(batch_size, seq_len, seq_len)


class TemporalFusionNetwork(nn.Module):
    """
    Temporal Fusion Transformer for multi-modal trading signals.

    Inspired by Google's TFT paper, adapted for trading:
    - Fuses multiple data modalities (price, volume, sentiment, macro)
    - Variable selection: Learns which features matter
    - Multi-horizon output: Predict multiple future time points
    - Interpretable attention: See what the model focuses on

    Architecture:
    1. Variable Selection Networks (per modality)
    2. LSTM encoder for temporal dynamics
    3. Multi-head attention for long-range dependencies
    4. Gated residual connections for gradient flow
    5. Multi-horizon decoder
    """

    def __init__(
        self,
        price_dim: int,           # Price features (OHLCV, returns, volatility)
        orderbook_dim: int = 0,   # Order book features (bid/ask, depth)
        sentiment_dim: int = 0,   # News/social sentiment features
        macro_dim: int = 0,       # Macro indicators (rates, VIX, etc.)
        hidden_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        forecast_horizons: list = None
    ):
        """
        Initialize TFN.

        Args:
            price_dim: Dimension of price features
            orderbook_dim: Dimension of order book features
            sentiment_dim: Dimension of sentiment features
            macro_dim: Dimension of macro features
            hidden_dim: Hidden layer dimension
            num_heads: Attention heads
            num_layers: Number of layers
            dropout: Dropout rate
            forecast_horizons: List of forecast horizons [1, 5, 21]
        """
        super().__init__()

        self.hidden_dim = hidden_dim
        self.forecast_horizons = forecast_horizons or [1, 5, 21]

        # Calculate total input dimension
        total_dim = price_dim + orderbook_dim + sentiment_dim + macro_dim

        # Variable selection networks (gated feature selection)
        self.variable_selection = VariableSelectionNetwork(
            total_dim, hidden_dim, dropout
        )

        # LSTM for temporal encoding
        self.lstm_encoder = LSTMEncoder(
            hidden_dim, hidden_dim, num_layers, dropout
        )

        # Multi-head attention for long-range dependencies
        self.attention = nn.MultiheadAttention(
            hidden_dim, num_heads, dropout=dropout, batch_first=True
        )

        # Gated residual network
        self.gated_residual = GatedResidualNetwork(hidden_dim, hidden_dim, dropout)

        # Multi-horizon output heads
        self.output_heads = nn.ModuleDict({
            f"horizon_{h}": nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 3)  # [direction, magnitude, confidence]
            )
            for h in self.forecast_horizons
        })

    def forward(
        self,
        price_features: torch.Tensor,
        orderbook_features: Optional[torch.Tensor] = None,
        sentiment_features: Optional[torch.Tensor] = None,
        macro_features: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.

        Args:
            price_features: (batch, seq_len, price_dim)
            orderbook_features: (batch, seq_len, orderbook_dim) optional
            sentiment_features: (batch, seq_len, sentiment_dim) optional
            macro_features: (batch, seq_len, macro_dim) optional

        Returns:
            Dict with predictions for each horizon
        """
        # Concatenate all features
        features = [price_features]
        if orderbook_features is not None:
            features.append(orderbook_features)
        if sentiment_features is not None:
            features.append(sentiment_features)
        if macro_features is not None:
            features.append(macro_features)

        x = torch.cat(features, dim=-1)

        # Variable selection
        x, var_weights = self.variable_selection(x)

        # LSTM encoding
        lstm_out, _ = self.lstm_encoder(x)

        # Self-attention
        attn_out, attn_weights = self.attention(lstm_out, lstm_out, lstm_out)

        # Gated residual
        fused = self.gated_residual(attn_out, lstm_out)

        # Get final representation (last timestep)
        final_repr = fused[:, -1, :]

        # Generate predictions for each horizon
        outputs = {}
        for horizon in self.forecast_horizons:
            pred = self.output_heads[f"horizon_{horizon}"](final_repr)
            outputs[f"horizon_{horizon}"] = {
                "direction": torch.tanh(pred[:, 0]),      # [-1, 1]
                "magnitude": torch.exp(pred[:, 1]),       # [0, inf)
                "confidence": torch.sigmoid(pred[:, 2])   # [0, 1]
            }

        outputs["attention_weights"] = attn_weights
        outputs["variable_weights"] = var_weights

        return outputs


class VariableSelectionNetwork(nn.Module):
    """
    Gated variable selection for feature importance.

    Learns to weight different input features, providing:
    1. Automatic feature selection
    2. Interpretability (which features matter)
    3. Regularization (ignores irrelevant features)
    """

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float = 0.1):
        super().__init__()

        self.input_projection = nn.Linear(input_dim, hidden_dim)

        # Gating network
        self.gate_network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, input_dim),
            nn.Softmax(dim=-1)  # Weights sum to 1
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Returns:
            Tuple of (selected features, selection weights)
        """
        # Calculate importance weights
        weights = self.gate_network(x)

        # Apply weights element-wise
        weighted = x * weights

        # Project to hidden dim
        output = self.input_projection(weighted)

        return output, weights


class GatedResidualNetwork(nn.Module):
    """
    Gated Residual Network for controlled information flow.

    Uses gating to control how much of the residual to add,
    allowing the network to learn when skip connections help.
    """

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float = 0.1):
        super().__init__()

        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)

        # Gate
        self.gate = nn.Linear(hidden_dim * 2, hidden_dim)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor, residual: torch.Tensor = None) -> torch.Tensor:
        """Forward with optional residual."""
        if residual is None:
            residual = x

        # Transform
        h = F.elu(self.fc1(x))
        h = self.dropout(h)
        h = self.fc2(h)

        # Gate
        gate_input = torch.cat([h, residual], dim=-1)
        gate = torch.sigmoid(self.gate(gate_input))

        # Gated residual
        output = gate * h + (1 - gate) * residual
        output = self.layer_norm(output)

        return output
