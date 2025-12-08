"""Order Flow Imbalance Strategy.

This strategy generates trading signals based on order book imbalance,
with filtering based on volatility and momentum confirmation.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from ..config import get_settings
from ..features.microstructure import FeatureSnapshot
from ..models import Signal, Side

logger = structlog.get_logger()


@dataclass
class StrategyConfig:
    """Configuration for the imbalance strategy."""

    # Imbalance thresholds
    imbalance_threshold: float = 0.3  # Minimum imbalance to generate signal
    min_confidence: float = 0.6  # Minimum confidence for signal

    # Volatility adjustment
    low_vol_multiplier: float = 1.5  # Increase size in low volatility
    high_vol_multiplier: float = 0.5  # Decrease size in high volatility
    vol_threshold_low: float = -1.0  # Z-score threshold for low vol
    vol_threshold_high: float = 1.0  # Z-score threshold for high vol

    # Momentum confirmation
    require_momentum_confirm: bool = True
    momentum_threshold: float = 0.0001  # Minimum momentum for confirmation

    # Imbalance persistence
    persistence_required: int = 3  # Number of ticks imbalance must persist
    persistence_decay: float = 0.9  # Decay factor for persistence score

    # Position sizing
    base_position_pct: float = 0.1  # Base position size as % of balance

    # Spread filter
    max_spread_bps: float = 10.0  # Maximum spread to trade


class ImbalanceStrategy:
    """Order flow imbalance trading strategy.

    This strategy looks for significant imbalance between bid and ask
    volumes in the order book. When imbalance is high and persistent,
    it generates a signal in the direction of the imbalance.
    """

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        """Initialize the strategy."""
        self.config = config or StrategyConfig()
        settings = get_settings()

        # Override config from settings
        self.config.imbalance_threshold = settings.imbalance_threshold
        self.config.min_confidence = settings.min_confidence
        self.config.base_position_pct = settings.position_size_pct

        # Persistence tracking per symbol
        self._imbalance_streak: dict[str, int] = {}
        self._last_imbalance_sign: dict[str, int] = {}

        logger.info(
            "strategy_initialized",
            imbalance_threshold=self.config.imbalance_threshold,
            min_confidence=self.config.min_confidence,
        )

    def evaluate(
        self,
        features: FeatureSnapshot,
        account_balance: Decimal,
        current_position: Optional[Decimal] = None,
    ) -> Optional[Signal]:
        """Evaluate market conditions and generate trading signal.

        Args:
            features: Current market microstructure features
            account_balance: Current account balance for position sizing
            current_position: Current position in the symbol

        Returns:
            Signal if conditions are met, None otherwise
        """
        symbol = features.symbol

        # Check basic conditions
        if features.imbalance is None or features.mid_price is None:
            return None

        # Spread filter
        if features.spread_bps is not None:
            if float(features.spread_bps) > self.config.max_spread_bps:
                logger.debug("spread_too_wide", symbol=symbol, spread=float(features.spread_bps))
                return None

        # Update persistence tracking
        imbalance = features.imbalance
        imbalance_sign = 1 if imbalance > 0 else -1

        if symbol not in self._last_imbalance_sign:
            self._last_imbalance_sign[symbol] = imbalance_sign
            self._imbalance_streak[symbol] = 1
        elif self._last_imbalance_sign[symbol] == imbalance_sign:
            self._imbalance_streak[symbol] += 1
        else:
            self._last_imbalance_sign[symbol] = imbalance_sign
            self._imbalance_streak[symbol] = 1

        # Check if imbalance is significant
        if abs(imbalance) < self.config.imbalance_threshold:
            return None

        # Check persistence
        if self._imbalance_streak[symbol] < self.config.persistence_required:
            logger.debug(
                "imbalance_not_persistent",
                symbol=symbol,
                streak=self._imbalance_streak[symbol],
                required=self.config.persistence_required,
            )
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(features)

        if confidence < self.config.min_confidence:
            logger.debug(
                "confidence_too_low",
                symbol=symbol,
                confidence=confidence,
                min_required=self.config.min_confidence,
            )
            return None

        # Momentum confirmation
        if self.config.require_momentum_confirm:
            if features.momentum is not None:
                expected_momentum_sign = 1 if imbalance > 0 else -1
                if (features.momentum * expected_momentum_sign) < self.config.momentum_threshold:
                    logger.debug(
                        "momentum_not_confirmed",
                        symbol=symbol,
                        momentum=features.momentum,
                        expected_sign=expected_momentum_sign,
                    )
                    return None

        # Imbalance momentum should be in same direction
        if features.imbalance_momentum is not None:
            if features.imbalance_momentum * imbalance_sign < 0:
                logger.debug(
                    "imbalance_momentum_diverging",
                    symbol=symbol,
                    imbalance_momentum=features.imbalance_momentum,
                )
                return None

        # Calculate position size
        size = self._calculate_position_size(
            features, account_balance, current_position
        )

        if size <= 0:
            return None

        # Generate signal
        side = Side.BUY if imbalance > 0 else Side.SELL
        reason = self._generate_reason(features)

        signal = Signal(
            symbol=symbol,
            side=side,
            confidence=confidence,
            suggested_size=Decimal(str(size)),
            reason=reason,
            timestamp=datetime.utcnow(),
        )

        logger.info(
            "signal_generated",
            symbol=symbol,
            side=side.value,
            confidence=confidence,
            size=size,
            imbalance=imbalance,
        )

        return signal

    def _calculate_confidence(self, features: FeatureSnapshot) -> float:
        """Calculate signal confidence based on features."""
        confidence = 0.0

        # Base confidence from imbalance strength
        if features.imbalance is not None:
            imbalance_strength = min(abs(features.imbalance), 1.0)
            confidence += 0.4 * imbalance_strength

        # Weighted imbalance contribution
        if features.weighted_imbalance is not None:
            weighted_strength = min(abs(features.weighted_imbalance), 1.0)
            confidence += 0.2 * weighted_strength

        # Persistence bonus
        symbol = features.symbol
        streak = self._imbalance_streak.get(symbol, 0)
        persistence_score = min(streak / 10.0, 1.0)  # Max out at 10 ticks
        confidence += 0.2 * persistence_score

        # Volatility adjustment (lower vol = higher confidence)
        if features.volatility_z is not None:
            if features.volatility_z < self.config.vol_threshold_low:
                confidence += 0.1  # Low volatility bonus
            elif features.volatility_z > self.config.vol_threshold_high:
                confidence -= 0.1  # High volatility penalty

        # Imbalance momentum bonus
        if features.imbalance_momentum is not None and features.imbalance is not None:
            imbalance_sign = 1 if features.imbalance > 0 else -1
            if features.imbalance_momentum * imbalance_sign > 0:
                confidence += 0.1

        return max(0.0, min(1.0, confidence))

    def _calculate_position_size(
        self,
        features: FeatureSnapshot,
        account_balance: Decimal,
        current_position: Optional[Decimal],
    ) -> float:
        """Calculate position size based on confidence and volatility."""
        base_size = float(account_balance) * self.config.base_position_pct

        # Adjust for volatility
        if features.volatility_z is not None:
            if features.volatility_z < self.config.vol_threshold_low:
                base_size *= self.config.low_vol_multiplier
            elif features.volatility_z > self.config.vol_threshold_high:
                base_size *= self.config.high_vol_multiplier

        # Convert to quantity based on mid price
        if features.mid_price is None or features.mid_price == 0:
            return 0.0

        quantity = base_size / float(features.mid_price)

        # Adjust if we already have a position
        if current_position is not None and current_position != 0:
            # Reduce size if adding to position
            if features.imbalance is not None:
                imbalance_sign = 1 if features.imbalance > 0 else -1
                position_sign = 1 if current_position > 0 else -1
                if imbalance_sign == position_sign:
                    quantity *= 0.5  # Halve size when adding to position

        return round(quantity, 6)

    def _generate_reason(self, features: FeatureSnapshot) -> str:
        """Generate human-readable reason for the signal."""
        parts = []

        if features.imbalance is not None:
            direction = "bid" if features.imbalance > 0 else "ask"
            parts.append(f"Order book {direction} imbalance: {features.imbalance:.3f}")

        streak = self._imbalance_streak.get(features.symbol, 0)
        if streak >= self.config.persistence_required:
            parts.append(f"Persistent for {streak} ticks")

        if features.volatility_z is not None:
            if features.volatility_z < self.config.vol_threshold_low:
                parts.append("Low volatility environment")
            elif features.volatility_z > self.config.vol_threshold_high:
                parts.append("High volatility (reduced size)")

        return "; ".join(parts) if parts else "Imbalance signal"

    def reset(self, symbol: Optional[str] = None) -> None:
        """Reset strategy state."""
        if symbol:
            self._imbalance_streak.pop(symbol, None)
            self._last_imbalance_sign.pop(symbol, None)
        else:
            self._imbalance_streak.clear()
            self._last_imbalance_sign.clear()
