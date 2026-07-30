# Trading System Universe — Daily Only

- Daily timeframe only.
- No weekly timeframe or Daily + Weekly mode.
- No price / $200 / minimum-price filter.
- Custom daily scan date supported.
- Manual RUN SCANNER NOW button.
- Screener tabs: Bullish Universe, Bearish Universe, Bullish Reclaim,
  Bullish Pullback, Bearish Breakdown, Bearish Pullback, Bearish Continuation, Darvas.
- Complete Stocks List, India Indexes, Formula Guide.
- Every result is ordered Strong Bullish → Bullish → Neutral → Bearish → Strong Bearish.
- Stocks/indexes remain configuration-driven in `config/universe.yaml`.
- Yahoo symbol changes for Tata Motors, LTIMindtree and United Spirits are handled without
  requesting the stale symbols that caused the 404 warnings.
- Unsupported Yahoo index symbols are displayed as DATA UNAVAILABLE rather than repeatedly
  producing 404 console noise.
