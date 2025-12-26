"""
Attention Mechanisms for Trading

Custom attention layers designed for financial applications:
- Volatility-aware attention: Focus more during high-vol periods
- Market-regime attention: Different patterns for different regimes
- Cross-asset attention: Learn inter-market relationships
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import math


class VolatilityAttention(nn.Module):
    """
    Volatility-Aware Attention Mechanism.

    Key insight: High-volatility periods contain more information.
    This attention mechanism upweights observations during vol spikes.

    How it works:
    1. Standard attention scores query-key similarity
    2. Volatility modifier scales scores by local volatility
    3. Higher vol periods get more attention weight
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int = 4,
        dropout: float = 0.1,
        vol_scale: float = 1.0
    ):
        """
        Initialize volatility attention.

        Args:
            d_model: Model dimension
            n_heads: Number of attention heads
            dropout: Dropout rate
            vol_scale: How much to weight volatility (1.0 = moderate)
        """
        super().__init__()

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.vol_scale = vol_scale

        # Standard attention projections
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        # Volatility projection (learns to extract vol signal from input)
        self.vol_proj = nn.Linear(d_model, 1)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_head)

    def forward(
        self,
        x: torch.Tensor,
        volatility: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Input tensor (batch, seq_len, d_model)
            volatility: Optional explicit volatility (batch, seq_len)
            mask: Optional attention mask

        Returns:
            Tuple of (output, attention_weights)
        """
        batch_size, seq_len, _ = x.shape

        # Project Q, K, V
        Q = self.q_proj(x).view(batch_size, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        K = self.k_proj(x).view(batch_size, seq_len, self.n_heads, self.d_head).transpose(1, 2)
        V = self.v_proj(x).view(batch_size, seq_len, self.n_heads, self.d_head).transpose(1, 2)

        # Compute attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Compute or use volatility weights
        if volatility is None:
            # Learn volatility from input
            vol_logits = self.vol_proj(x).squeeze(-1)  # (batch, seq_len)
            volatility = torch.sigmoid(vol_logits)

        # Scale scores by volatility (higher vol = higher attention)
        # Expand volatility for keys: (batch, 1, 1, seq_len)
        vol_weights = (1 + self.vol_scale * volatility).unsqueeze(1).unsqueeze(2)
        scores = scores * vol_weights

        # Apply mask if provided
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))

        # Softmax
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Apply attention to values
        output = torch.matmul(attn_weights, V)

        # Reshape and project
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        output = self.out_proj(output)

        # Average attention weights across heads for interpretability
        avg_attn = attn_weights.mean(dim=1)

        return output, avg_attn


class MarketAttention(nn.Module):
    """
    Market-Regime Aware Attention.

    Different market regimes (trending, mean-reverting, volatile, calm)
    require different attention patterns.

    This layer:
    1. Detects the current regime
    2. Applies regime-specific attention heads
    3. Combines with learned regime weights
    """

    def __init__(
        self,
        d_model: int,
        n_regimes: int = 4,
        n_heads_per_regime: int = 2,
        dropout: float = 0.1
    ):
        """
        Initialize market attention.

        Args:
            d_model: Model dimension
            n_regimes: Number of market regimes to model
            n_heads_per_regime: Attention heads per regime
            dropout: Dropout rate
        """
        super().__init__()

        self.d_model = d_model
        self.n_regimes = n_regimes
        self.n_heads = n_heads_per_regime
        self.d_head = d_model // (n_regimes * n_heads_per_regime)

        # Regime detection network
        self.regime_detector = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Linear(d_model, n_regimes),
            nn.Softmax(dim=-1)
        )

        # Separate attention heads for each regime
        self.regime_attention = nn.ModuleList([
            nn.MultiheadAttention(d_model, n_heads_per_regime, dropout=dropout, batch_first=True)
            for _ in range(n_regimes)
        ])

        # Output projection
        self.out_proj = nn.Linear(d_model * n_regimes, d_model)

        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, dict]:
        """
        Forward pass.

        Args:
            x: Input tensor (batch, seq_len, d_model)
            mask: Optional attention mask

        Returns:
            Tuple of (output, info_dict with regime weights and attentions)
        """
        batch_size, seq_len, _ = x.shape

        # Detect regime (use last timestep for current regime)
        regime_probs = self.regime_detector(x[:, -1, :])  # (batch, n_regimes)

        # Apply each regime's attention
        regime_outputs = []
        regime_attentions = []

        for i, attn_layer in enumerate(self.regime_attention):
            out, attn_weights = attn_layer(x, x, x, attn_mask=mask)
            regime_outputs.append(out)
            regime_attentions.append(attn_weights)

        # Stack regime outputs: (batch, seq_len, d_model, n_regimes)
        stacked = torch.stack(regime_outputs, dim=-1)

        # Weight by regime probabilities
        regime_weights = regime_probs.view(batch_size, 1, 1, self.n_regimes)
        weighted = (stacked * regime_weights).sum(dim=-1)

        # Alternatively, concatenate and project (richer representation)
        concatenated = torch.cat(regime_outputs, dim=-1)
        output = self.out_proj(concatenated)

        info = {
            "regime_probabilities": regime_probs,
            "regime_attentions": regime_attentions
        }

        return output, info


class CrossAssetAttention(nn.Module):
    """
    Cross-Asset Attention for multi-asset relationships.

    Key insight: Assets are correlated. News about one asset
    affects related assets. This attention learns these relationships.

    Applications:
    - Factor models (learn latent factors)
    - Lead-lag relationships
    - Contagion effects
    - Sector rotation signals
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int = 4,
        dropout: float = 0.1
    ):
        """
        Initialize cross-asset attention.

        Args:
            d_model: Feature dimension per asset
            n_heads: Number of attention heads
            dropout: Dropout rate
        """
        super().__init__()

        self.attention = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )

        self.layer_norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        asset_features: torch.Tensor,
        asset_mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            asset_features: (batch, n_assets, d_model)
            asset_mask: Optional mask for certain assets

        Returns:
            Tuple of (enhanced_features, cross_asset_attention)
        """
        # Self-attention across assets
        attended, attn_weights = self.attention(
            asset_features, asset_features, asset_features,
            key_padding_mask=asset_mask
        )

        # Residual connection
        output = self.layer_norm(asset_features + self.dropout(attended))

        return output, attn_weights


class TemporalCrossAttention(nn.Module):
    """
    Temporal Cross-Attention between different time scales.

    Fuses information from multiple time resolutions:
    - Fast (tick/minute): Microstructure, execution signals
    - Medium (hourly/daily): Momentum, sentiment
    - Slow (weekly/monthly): Fundamentals, macro

    The fast scale attends to slow for context.
    The slow scale attends to fast for leading indicators.
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()

        # Fast-to-slow attention (fast queries, slow keys/values)
        self.fast_to_slow = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )

        # Slow-to-fast attention (slow queries, fast keys/values)
        self.slow_to_fast = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )

        self.layer_norm_fast = nn.LayerNorm(d_model)
        self.layer_norm_slow = nn.LayerNorm(d_model)

        # Fusion layer
        self.fusion = nn.Linear(d_model * 2, d_model)

    def forward(
        self,
        fast_features: torch.Tensor,
        slow_features: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, dict]:
        """
        Forward pass.

        Args:
            fast_features: High-frequency features (batch, fast_seq_len, d_model)
            slow_features: Low-frequency features (batch, slow_seq_len, d_model)

        Returns:
            Tuple of (enhanced_fast, enhanced_slow, attention_info)
        """
        # Fast attends to slow (get context)
        fast_attended, f2s_attn = self.fast_to_slow(
            fast_features, slow_features, slow_features
        )
        fast_enhanced = self.layer_norm_fast(fast_features + fast_attended)

        # Slow attends to fast (get leading signals)
        slow_attended, s2f_attn = self.slow_to_fast(
            slow_features, fast_features, fast_features
        )
        slow_enhanced = self.layer_norm_slow(slow_features + slow_attended)

        info = {
            "fast_to_slow_attention": f2s_attn,
            "slow_to_fast_attention": s2f_attn
        }

        return fast_enhanced, slow_enhanced, info
