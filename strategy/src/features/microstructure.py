"""Microstructure feature calculations.

This module implements various market microstructure features used by
trading strategies, including order book imbalance, volatility, and
volume profiles.
"""

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import numpy as np


@dataclass
class FeatureSnapshot:
    """Snapshot of calculated features at a point in time."""

    timestamp: int
    symbol: str

    # Order book features
    mid_price: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    imbalance: Optional[float] = None
    weighted_imbalance: Optional[float] = None

    # Volume features
    bid_depth: Optional[Decimal] = None
    ask_depth: Optional[Decimal] = None
    volume_ratio: Optional[float] = None

    # Derived features
    volatility: Optional[float] = None
    momentum: Optional[float] = None
    imbalance_momentum: Optional[float] = None

    # Normalized features for ML
    imbalance_z: Optional[float] = None
    volatility_z: Optional[float] = None


class MicrostructureFeatures:
    """Calculator for microstructure features.

    Maintains rolling windows of historical data to calculate
    time-series features like volatility and momentum.
    """

    def __init__(
        self,
        window_size: int = 100,
        volatility_window: int = 20,
        momentum_window: int = 10,
    ) -> None:
        """Initialize feature calculator.

        Args:
            window_size: Size of the main rolling window
            volatility_window: Window for volatility calculation
            momentum_window: Window for momentum calculation
        """
        self.window_size = window_size
        self.volatility_window = volatility_window
        self.momentum_window = momentum_window

        # Rolling windows per symbol
        self._mid_prices: dict[str, deque[float]] = {}
        self._imbalances: dict[str, deque[float]] = {}
        self._timestamps: dict[str, deque[int]] = {}

        # Statistics for normalization
        self._imbalance_mean: dict[str, float] = {}
        self._imbalance_std: dict[str, float] = {}
        self._volatility_mean: dict[str, float] = {}
        self._volatility_std: dict[str, float] = {}

    def _ensure_symbol(self, symbol: str) -> None:
        """Ensure data structures exist for a symbol."""
        if symbol not in self._mid_prices:
            self._mid_prices[symbol] = deque(maxlen=self.window_size)
            self._imbalances[symbol] = deque(maxlen=self.window_size)
            self._timestamps[symbol] = deque(maxlen=self.window_size)
            self._imbalance_mean[symbol] = 0.0
            self._imbalance_std[symbol] = 1.0
            self._volatility_mean[symbol] = 0.0
            self._volatility_std[symbol] = 1.0

    def update(
        self,
        symbol: str,
        timestamp: int,
        mid_price: Optional[Decimal],
        imbalance: Optional[Decimal],
        weighted_imbalance: Optional[Decimal],
        spread_bps: Optional[Decimal],
        bid_depth: Optional[Decimal],
        ask_depth: Optional[Decimal],
    ) -> FeatureSnapshot:
        """Update features with new order book data.

        Args:
            symbol: Trading symbol
            timestamp: Unix timestamp in milliseconds
            mid_price: Current mid price
            imbalance: Simple order book imbalance
            weighted_imbalance: Distance-weighted imbalance
            spread_bps: Spread in basis points
            bid_depth: Total bid volume
            ask_depth: Total ask volume

        Returns:
            FeatureSnapshot with all calculated features
        """
        self._ensure_symbol(symbol)

        # Update rolling windows
        if mid_price is not None:
            self._mid_prices[symbol].append(float(mid_price))
        if imbalance is not None:
            self._imbalances[symbol].append(float(imbalance))
        self._timestamps[symbol].append(timestamp)

        # Calculate derived features
        volatility = self._calculate_volatility(symbol)
        momentum = self._calculate_momentum(symbol)
        imbalance_momentum = self._calculate_imbalance_momentum(symbol)

        # Update normalization statistics
        self._update_statistics(symbol)

        # Calculate normalized features
        imbalance_z = self._normalize_imbalance(symbol, float(imbalance) if imbalance else None)
        volatility_z = self._normalize_volatility(symbol, volatility)

        # Volume ratio
        volume_ratio = None
        if bid_depth and ask_depth and ask_depth > 0:
            volume_ratio = float(bid_depth / ask_depth)

        return FeatureSnapshot(
            timestamp=timestamp,
            symbol=symbol,
            mid_price=mid_price,
            spread_bps=spread_bps,
            imbalance=float(imbalance) if imbalance else None,
            weighted_imbalance=float(weighted_imbalance) if weighted_imbalance else None,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            volume_ratio=volume_ratio,
            volatility=volatility,
            momentum=momentum,
            imbalance_momentum=imbalance_momentum,
            imbalance_z=imbalance_z,
            volatility_z=volatility_z,
        )

    def _calculate_volatility(self, symbol: str) -> Optional[float]:
        """Calculate rolling volatility using log returns."""
        prices = list(self._mid_prices[symbol])
        if len(prices) < self.volatility_window:
            return None

        recent_prices = prices[-self.volatility_window:]
        returns = np.diff(np.log(recent_prices))

        if len(returns) == 0:
            return None

        return float(np.std(returns) * np.sqrt(252 * 24 * 60))  # Annualized

    def _calculate_momentum(self, symbol: str) -> Optional[float]:
        """Calculate price momentum."""
        prices = list(self._mid_prices[symbol])
        if len(prices) < self.momentum_window:
            return None

        recent_prices = prices[-self.momentum_window:]
        if recent_prices[0] == 0:
            return None

        return (recent_prices[-1] - recent_prices[0]) / recent_prices[0]

    def _calculate_imbalance_momentum(self, symbol: str) -> Optional[float]:
        """Calculate momentum of imbalance."""
        imbalances = list(self._imbalances[symbol])
        if len(imbalances) < self.momentum_window:
            return None

        recent = imbalances[-self.momentum_window:]
        # Simple linear regression slope
        x = np.arange(len(recent))
        y = np.array(recent)

        if np.std(x) == 0 or np.std(y) == 0:
            return 0.0

        correlation = np.corrcoef(x, y)[0, 1]
        slope = correlation * np.std(y) / np.std(x)

        return float(slope)

    def _update_statistics(self, symbol: str) -> None:
        """Update rolling statistics for normalization."""
        imbalances = list(self._imbalances[symbol])
        if len(imbalances) >= 20:
            self._imbalance_mean[symbol] = float(np.mean(imbalances))
            self._imbalance_std[symbol] = max(float(np.std(imbalances)), 0.001)

        prices = list(self._mid_prices[symbol])
        if len(prices) >= self.volatility_window:
            returns = np.diff(np.log(prices[-self.volatility_window:]))
            if len(returns) > 0:
                vol = float(np.std(returns))
                if vol > 0:
                    self._volatility_mean[symbol] = vol
                    # Use a longer window for std of vol
                    all_returns = np.diff(np.log(prices))
                    if len(all_returns) >= self.volatility_window:
                        window_vols = [
                            np.std(all_returns[i:i+self.volatility_window])
                            for i in range(len(all_returns) - self.volatility_window + 1)
                        ]
                        self._volatility_std[symbol] = max(float(np.std(window_vols)), 0.0001)

    def _normalize_imbalance(self, symbol: str, imbalance: Optional[float]) -> Optional[float]:
        """Normalize imbalance to z-score."""
        if imbalance is None:
            return None
        mean = self._imbalance_mean[symbol]
        std = self._imbalance_std[symbol]
        return (imbalance - mean) / std

    def _normalize_volatility(self, symbol: str, volatility: Optional[float]) -> Optional[float]:
        """Normalize volatility to z-score."""
        if volatility is None:
            return None
        mean = self._volatility_mean.get(symbol, volatility)
        std = self._volatility_std.get(symbol, 1.0)
        return (volatility - mean) / std

    def get_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range (simplified using mid prices)."""
        prices = list(self._mid_prices[symbol])
        if len(prices) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(prices)):
            tr = abs(prices[i] - prices[i-1])
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return None

        return float(np.mean(true_ranges[-period:]))

    def reset(self, symbol: Optional[str] = None) -> None:
        """Reset feature state for a symbol or all symbols."""
        if symbol:
            self._mid_prices.pop(symbol, None)
            self._imbalances.pop(symbol, None)
            self._timestamps.pop(symbol, None)
            self._imbalance_mean.pop(symbol, None)
            self._imbalance_std.pop(symbol, None)
            self._volatility_mean.pop(symbol, None)
            self._volatility_std.pop(symbol, None)
        else:
            self._mid_prices.clear()
            self._imbalances.clear()
            self._timestamps.clear()
            self._imbalance_mean.clear()
            self._imbalance_std.clear()
            self._volatility_mean.clear()
            self._volatility_std.clear()
