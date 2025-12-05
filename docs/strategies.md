# Trading Strategies

This document describes the trading strategies implemented in QuantumFlow.

## Order Flow Imbalance Strategy

### Overview

The primary strategy exploits temporary imbalances in the order book to predict short-term price movements. When there's significantly more volume on the bid side than the ask side, buying pressure is likely to push prices up.

### Theory

Order book imbalance measures the relative difference between bid and ask volumes:

```
Imbalance = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
```

- Imbalance > 0: More bid volume (bullish pressure)
- Imbalance < 0: More ask volume (bearish pressure)

### Weighted Imbalance

Simple imbalance treats all levels equally, but prices closer to the mid are more relevant. We use exponential decay:

```
Weighted Imbalance = Σ(volume_i * decay^i) for bids vs asks
```

where `decay` is typically 0.9, giving more weight to top-of-book levels.

### Signal Generation

A signal is generated when:

1. **Threshold Exceeded**: |imbalance| > 0.3
2. **Persistence**: Imbalance in same direction for 3+ ticks
3. **Volatility Filter**: Normalized volatility not extreme
4. **Spread Filter**: Spread < 10 bps
5. **Momentum Confirmation**: Price momentum aligns with imbalance

### Confidence Calculation

```python
confidence = (
    0.4 * min(abs(imbalance), 1.0) +           # Imbalance strength
    0.2 * min(abs(weighted_imbalance), 1.0) +  # Weighted strength
    0.2 * min(persistence / 10, 1.0) +         # Persistence score
    0.1 * volatility_bonus +                    # Low vol bonus
    0.1 * momentum_alignment                    # Momentum bonus
)
```

### Position Sizing

Position size scales with:
- Confidence level
- Inverse of volatility (smaller in volatile markets)
- Available balance

```python
base_size = balance * 0.1  # 10% of balance
if low_volatility:
    size = base_size * 1.5
elif high_volatility:
    size = base_size * 0.5
```

### Risk Management

1. **Position Limits**: Max 1 BTC equivalent per symbol
2. **Drawdown Circuit Breaker**: Pause at 5% drawdown
3. **Rate Limiting**: Max 60 orders per minute
4. **Stop Loss**: 2x ATR below entry

### Performance Characteristics

- **Expected Win Rate**: 50-55%
- **Average Holding Time**: 1-5 minutes
- **Trades per Day**: 10-50 (market dependent)
- **Target Sharpe**: > 1.0

## Future Strategy Ideas

### Mean Reversion
- Trade deviations from moving averages
- Works well in ranging markets

### Momentum
- Follow strong price trends
- Requires trend detection algorithms

### Statistical Arbitrage
- Cross-symbol correlation trading
- Requires multiple symbol support

### Machine Learning
- Feature-based prediction models
- Requires historical data collection
