# ADR 001: Multi-Language Architecture

## Status
Accepted

## Context
We need to build a high-frequency paper trading system that demonstrates competence across multiple domains:
- Low-latency market data processing
- Type-safe financial calculations
- Rapid strategy iteration
- Portfolio demonstration value

## Decision
We will use three languages, each for its strengths:

### Rust for Market Data
- Zero-cost abstractions for parsing
- Memory safety without GC pauses
- Excellent async ecosystem (tokio)
- Predictable latency characteristics

### OCaml for Risk Engine
- Algebraic data types prevent invalid states
- Exhaustive pattern matching catches edge cases
- Immutable-by-default for correctness
- Strong type inference reduces boilerplate

### Python for Strategy
- Rapid prototyping and iteration
- Rich data science ecosystem
- FastAPI for clean APIs
- Easy debugging and modification

## Consequences

### Positive
- Each component uses the best tool for its job
- Demonstrates breadth of skills
- Forces clean interfaces between components
- Showcases systems engineering thinking

### Negative
- Higher complexity in build/deploy
- Need expertise in multiple languages
- IPC overhead between components
- More complex debugging across boundaries

## Notes
The multi-language approach is intentional for portfolio demonstration. In a production system, the added complexity might not be justified unless the team has expertise across all languages.
