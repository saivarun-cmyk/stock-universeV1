# Fixes in this build

- Fixed the critical Yahoo download bug caused by treating `logging.disable()`
  as a context manager. This was the main reason all rows became
  `DATA UNAVAILABLE`.
- Yahoo downloads are now explicitly bounded by the selected daily scan date.
- Enough historical data is downloaded for SMA50 and all 20-period indicators.
- Index entries are explicitly typed as indexes.
- Known stale Yahoo sector-index symbols are disabled cleanly instead of
  generating repeated HTTP 404 messages.
- The actual market candle used is shown as `Scan End`.
- No price/amount filters.
- Daily timeframe only.
- Plotly charts already use unique keys.
- All symbols remain configurable in `config/universe.yaml`.
