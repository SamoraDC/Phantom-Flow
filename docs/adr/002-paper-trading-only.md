# ADR 002: Paper Trading Only

## Status
Accepted

## Context
This system could theoretically execute real trades on Binance, but we need to decide whether to implement real trading capabilities.

## Decision
This system will be **paper trading only** and will not have any capability to execute real trades.

## Rationale

### Legal & Compliance
- Trading cryptocurrencies has regulatory implications
- Demonstrating a live trading system on a public portfolio could attract unwanted attention
- Paper trading avoids any compliance concerns

### Risk Management
- A portfolio project should not risk real money
- Bugs in demo code could cause real financial losses
- Paper trading allows aggressive experimentation

### Portfolio Value
- The technical implementation is the same either way
- Demonstrating systematic approach is more valuable than PnL
- Recruiters care about code quality, not trading profits

### Simplicity
- No need to handle API key security
- No need for withdrawal protection
- No need for fail-safes against real losses

## Consequences

### Positive
- Zero financial risk
- No API keys to secure
- Can be aggressive with position sizes for demonstration
- Open source without risk

### Negative
- Cannot prove real-world performance
- Paper fills may not reflect real execution quality
- Less "impressive" than a live trading system

## Implementation
- No Binance API keys required
- Paper broker simulates execution with configurable slippage
- Fees deducted as if real trades occurred
