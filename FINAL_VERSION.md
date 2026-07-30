# Trading System Universe — Daily Only

This version is **daily timeframe only**.

## Scanner controls

- Run Scanner Now
- Daily candle:
  - Latest / Today
  - Yesterday
  - 2 Days Ago
  - 3 Days Ago
  - Custom Date
- Sector filter
- No price filter
- No amount filter

## Tabs

1. Scanner Overview
2. Bullish Universe
3. Bearish Universe
4. Bullish Reclaim
5. Bullish Pullback
6. Bearish Breakdown
7. Bearish Pullback
8. Bearish Continuation
9. Darvas
10. Complete Stocks List
11. India Indexes
12. Formula Guide

## Data behavior

The scanner downloads sufficient daily history before the selected date to
calculate SMA10, EMA20, SMA50, Highest/Lowest 20 and Volume SMA20.

The selected date is an upper bound. The actual `Scan End` shown in the UI is
the latest market candle available on or before that date.

Yahoo Finance failures are handled per symbol. A failed symbol does not stop the
whole scan and stale/unsupported index symbols are not repeatedly requested.

## Configuration

All stocks and indexes are loaded from:

`config/universe.yaml`

Add or remove entries there and restart Streamlit. No Python changes are needed.
