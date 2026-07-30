# Scan Period Specification — V4

## Daily
- Latest / Today
- Yesterday
- 2 Days Ago
- 3 Days Ago
- Custom Date

The selected daily trading date is the candle evaluated by all Daily screeners.

## Weekly
- Current Week → Current Date
- Last Completed Week
- Custom Date Range

For Current Week → Current Date, the weekly candle is built from the first
trading day of the current week through the current date.

For Last Completed Week, the previous completed Monday–Friday trading period
is evaluated.

For Custom Date Range, the weekly candle is built exactly from the selected
start date through the selected end date.

## Historical indicator calculation

The app must download enough history before the selected period to calculate:
- EMA20
- SMA10
- SMA50
- 20-period average volume

The selected candle is then evaluated using those indicators.

## UI metadata

Every scan must display:
- Scan timeframe
- Start date
- End date
- LIVE vs COMPLETED
- Last scan time
- Number of stocks scanned
- Number of indexes scanned
- Failed Yahoo Finance symbols
- Scan duration

## Removed

The application must NOT contain:
- Price > 200
- Any arbitrary amount/price filter
