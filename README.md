# Trading System Universe — Final

Streamlit Cloud-ready scanner with the supplied stock universe and India indexes.

## Timeframe
Use one toggle: Daily, Weekly, or Daily + Weekly. Comparison mode shows both statuses and alignment.

## Status
Strong Bullish / Bullish / Neutral / Bearish / Strong Bearish based on Close/EMA20, SMA10/EMA20, EMA20/SMA50, Close/SMA50.

## Screens
Bullish Universe, Bearish Universe, Bullish Reclaim, Bullish Pullback, Bearish Breakdown, Bearish Pullback.

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Edit `data/Trading_Universe.xlsx` to change the universe.


## V2 fixes

- Yahoo failures are isolated per ticker; one missing symbol cannot stop the UI.
- Added ticker fallback/alias handling for changed Yahoo symbols.
- Added **RUN SCANNER NOW** manual refresh button.
- Every Plotly chart receives a unique Streamlit `key`, preventing `StreamlitDuplicateElementId`.
- Added **Complete Stocks List** tab with every configured stock and all Daily/Weekly screener results.
- Added CSV export from the complete list.
- A failed Yahoo symbol is skipped instead of crashing the application.


## Final V3 additions

- Added **Formula & Strategy Guide** as a dedicated tab.
- Each screener has its own formula section and plain-English explanation.
- Added indicator definitions and market-regime explanation.
- Added Daily vs Weekly comparison explanation.
- Added stock-level **Why? / calculation details** inspection.
- Added all-condition PASS/FAIL visibility for each stock and screener.
- Kept the manual **RUN SCANNER NOW** button.
- Kept unique Plotly keys and Yahoo Finance failure isolation.
- The optional price filter is now passed into the actual scan calculation.


## V4 scan-period requirements

The final design uses date-aware scanning:
- Daily: latest/today, yesterday, previous days, or custom date.
- Weekly: current week to current date, last completed week, or custom date range.
- Exact scan start/end dates and LIVE/COMPLETED status are shown in the UI.
- No Price > 200 or amount filter is used.
- Historical data before the selected period is retained for EMA20/SMA10/SMA50 and volume-average calculations.
