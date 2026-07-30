import logging
from datetime import date
import pandas as pd
import yfinance as yf
import streamlit as st

# Yahoo symbols that have changed over time. Only the preferred symbol is
# requested, so stale symbols do not generate noisy 404 messages.
TICKER_ALIASES = {
    "TATAMOTORS.NS": "TMPV.NS",
    "LTIM.NS": "LTM.NS",
    "UNITEDSPIRITS.NS": "UNITDSPR.NS",
}

# Yahoo has inconsistent coverage for several NSE sector indices. Keep only
# symbols known to be usable; unsupported configured indexes are reported in
# the UI instead of repeatedly requesting dead Yahoo symbols.
INDEX_ALIASES = {
    # Yahoo coverage for several NSE sector indexes is inconsistent.
    # None means "do not request this stale symbol"; the UI will report it
    # cleanly rather than emitting repeated HTTP 404 messages.
    "^CNXFINANCE": None,
    "^CNXHEALTHCARE": None,
    "^CNXCONSUMER": None,
    "^CNXOILGAS": None,
}

SCREENER_NAMES = [
    "Bullish Universe", "Bearish Universe", "Bullish Reclaim",
    "Bullish Pullback", "Bearish Breakdown", "Bearish Pullback",
    "Bearish Continuation", "Darvas",
]

FORMULAS = {
    "Bullish Universe": [
        "Close > SMA(10)",
        "SMA(10) > EMA(20)",
        "EMA(20) > SMA(50)",
        "Close >= Highest High(20) × 0.98",
        "Volume > SMA(Volume,20)",
    ],
    "Bearish Universe": [
        "Close < SMA(10)",
        "SMA(10) < EMA(20)",
        "EMA(20) < SMA(50)",
        "Close <= Lowest Low(20) × 1.02",
        "Volume > SMA(Volume,20)",
    ],
    "Bullish Reclaim": [
        "Daily Close > Daily EMA(20)",
        "1 day ago Close <= 1 day ago EMA(20)",
        "Daily SMA(10) > Daily EMA(20)",
        "Daily Volume > Daily SMA(Daily Volume,20)",
    ],
    "Bullish Pullback": [
        "Daily EMA(20) > Daily SMA(50)",
        "Daily Low <= Daily EMA(20)",
        "Daily Close > Daily EMA(20)",
        "Daily Volume > Daily SMA(Daily Volume,20)",
    ],
    "Bearish Breakdown": [
        "Daily Close < Daily EMA(20)",
        "1 day ago Close >= 1 day ago EMA(20)",
        "Daily SMA(10) < Daily EMA(20)",
        "Daily Volume > Daily SMA(Daily Volume,20)",
    ],
    "Bearish Pullback": [
        "Daily Close < Daily EMA(20)",
        "1 day ago Close >= 1 day ago EMA(20)",
        "Daily SMA(10) < Daily EMA(20)",
        "Daily Volume > Daily SMA(Daily Volume,20)",
    ],
    "Bearish Continuation": [
        "Daily Close < 1 day ago Close",
        "Daily Close < Daily EMA(20)",
        "Daily EMA(20) < Daily SMA(50)",
        "Daily Volume > Daily SMA(Daily Volume,20)",
    ],
    "Darvas": [
        "Latest Close > Latest SMA(10)",
        "Latest SMA(10) > Latest EMA(20)",
        "Latest EMA(20) > Latest SMA(50)",
        "Latest High >= Highest High(20)",
        "Latest Volume > Latest SMA(20, Volume)",
    ],
}

def _symbol(item):
    ticker = str(item.get("ticker", "")).strip()
    if item.get("type") == "index":
        return INDEX_ALIASES.get(ticker, ticker)
    return TICKER_ALIASES.get(ticker, ticker)

def _download_one(symbol, end=None):
    if not symbol:
        return pd.DataFrame()

    # Download enough history for SMA50/EMA20/20-day volume and explicitly
    # bound the request by the selected scan date.  The previous version used
    # `with logging.disable(...)`, but logging.disable() is not a context
    # manager; that exception was silently caught and every symbol became
    # DATA UNAVAILABLE.
    try:
        end_ts = pd.Timestamp(end).normalize() if end is not None else pd.Timestamp.today().normalize()
        start_ts = end_ts - pd.Timedelta(days=900)
        request_end = end_ts + pd.Timedelta(days=1)

        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            df = yf.download(
                symbol,
                start=start_ts.strftime("%Y-%m-%d"),
                end=request_end.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        finally:
            logging.disable(previous_disable)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()
    df = df[needed].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["Close"])
    if df.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    return df

@st.cache_data(ttl=900, show_spinner=False)
def download(ticker, is_index=False, end=None):
    item = {"ticker": ticker, "type": "index" if is_index else "stock"}
    symbol = _symbol(item)
    if symbol is None:
        return pd.DataFrame(), None, "Yahoo Finance symbol is intentionally disabled for this index."
    df = _download_one(symbol, end)
    if df.empty:
        return pd.DataFrame(), symbol, "No Yahoo Finance data available for this symbol."
    return df, symbol, ""

def indicators(df):
    x = df.copy()
    x["SMA10"] = x["Close"].rolling(10, min_periods=10).mean()
    x["EMA20"] = x["Close"].ewm(span=20, adjust=False, min_periods=20).mean()
    x["SMA50"] = x["Close"].rolling(50, min_periods=50).mean()
    x["HighestHigh20"] = x["High"].rolling(20, min_periods=20).max()
    x["LowestLow20"] = x["Low"].rolling(20, min_periods=20).min()
    x["AvgVolume20"] = x["Volume"].rolling(20, min_periods=20).mean()
    return x

def daily_bars(raw, end):
    return indicators(raw[raw.index <= pd.Timestamp(end)].copy())

def regime(df):
    if df.empty or len(df) < 55:
        return "DATA UNAVAILABLE", 0
    r = df.iloc[-1]
    checks = [
        bool(r.Close > r.SMA10),
        bool(r.SMA10 > r.EMA20),
        bool(r.EMA20 > r.SMA50),
        bool(r.Close >= r.HighestHigh20 * 0.98),
        bool(r.Volume > r.AvgVolume20),
    ]
    score = sum(checks)
    # Trend strength is deliberately based on the same technical stack used
    # by the universe, not on an arbitrary price threshold.
    if score >= 5:
        return "STRONG BULLISH", 100
    if score == 4:
        return "BULLISH", 80
    if score == 3:
        return "NEUTRAL", 60
    if score == 2:
        return "BEARISH", 40
    return "STRONG BEARISH", 20

def _checks(df, name):
    if df.empty or len(df) < 55:
        return False, {}
    r, p = df.iloc[-1], df.iloc[-2]
    if name == "Bullish Universe":
        c = {
            "Close > SMA10": r.Close > r.SMA10,
            "SMA10 > EMA20": r.SMA10 > r.EMA20,
            "EMA20 > SMA50": r.EMA20 > r.SMA50,
            "Close >= Highest High(20) × 0.98": r.Close >= r.HighestHigh20 * 0.98,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name == "Bearish Universe":
        c = {
            "Close < SMA10": r.Close < r.SMA10,
            "SMA10 < EMA20": r.SMA10 < r.EMA20,
            "EMA20 < SMA50": r.EMA20 < r.SMA50,
            "Close <= Lowest Low(20) × 1.02": r.Close <= r.LowestLow20 * 1.02,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name == "Bullish Reclaim":
        c = {
            "Close > EMA20": r.Close > r.EMA20,
            "Previous Close <= Previous EMA20": p.Close <= p.EMA20,
            "SMA10 > EMA20": r.SMA10 > r.EMA20,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name == "Bullish Pullback":
        c = {
            "EMA20 > SMA50": r.EMA20 > r.SMA50,
            "Low <= EMA20": r.Low <= r.EMA20,
            "Close > EMA20": r.Close > r.EMA20,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name in ("Bearish Breakdown", "Bearish Pullback"):
        c = {
            "Close < EMA20": r.Close < r.EMA20,
            "Previous Close >= Previous EMA20": p.Close >= p.EMA20,
            "SMA10 < EMA20": r.SMA10 < r.EMA20,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name == "Bearish Continuation":
        c = {
            "Close < Previous Close": r.Close < p.Close,
            "Close < EMA20": r.Close < r.EMA20,
            "EMA20 < SMA50": r.EMA20 < r.SMA50,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    elif name == "Darvas":
        c = {
            "Close > SMA10": r.Close > r.SMA10,
            "SMA10 > EMA20": r.SMA10 > r.EMA20,
            "EMA20 > SMA50": r.EMA20 > r.SMA50,
            "High >= Highest High(20)": r.High >= r.HighestHigh20,
            "Volume > SMA(Volume,20)": r.Volume > r.AvgVolume20,
        }
    else:
        return False, {}
    c = {k: bool(v) and pd.notna(v) for k, v in c.items()}
    return all(c.values()), c

def _build(item, end):
    ticker = item.get("ticker", "")
    raw, resolved, error = download(
        ticker,
        item.get("type") == "index",
        end,
    )
    if raw.empty:
        return {
            "Sector": item.get("sector", "Index"),
            "Stock": item.get("stock", item.get("symbol", ticker)),
            "Ticker": ticker,
            "Symbol": item.get("symbol", item.get("stock", ticker)),
            "Resolved Ticker": resolved or "",
            "Error": error,
            "Status": "DATA UNAVAILABLE",
            "Score": 0,
            "Frame": pd.DataFrame(),
            "Scan Start": "",
            "Scan End": str(pd.Timestamp(end).date()),
            "Screens": {},
        }
    df = daily_bars(raw, end)
    if df.empty:
        return None
    status, score = regime(df)
    screens = {}
    for name in SCREENER_NAMES:
        matched, conditions = _checks(df, name)
        screens[name] = {"signal": matched, "conditions": conditions}
    return {
        "Sector": item.get("sector", "Index"),
        "Stock": item.get("stock", item.get("symbol", ticker)),
        "Ticker": ticker,
        "Symbol": item.get("symbol", item.get("stock", ticker)),
        "Resolved Ticker": resolved,
        "Status": status,
        "Score": score,
        "Frame": df,
        "Screens": screens,
        "Scan Start": str(df.index[0].date()),
        # The selected date is an upper bound. If the market was closed or
        # today's candle is not published yet, show the actual candle used.
        "Scan End": str(df.index[-1].date()),
        "Error": "",
    }

@st.cache_data(ttl=900, show_spinner=False)
def scan(items, end):
    rows = []
    for item in items:
        try:
            # Indexes() marks its entries with type=index.  This fallback also
            # supports older config files without requiring code edits.
            item = dict(item)
            item.setdefault("type", "index" if item.get("category") == "index" else "stock")
            row = _build(item, end)
            if row is not None:
                rows.append(row)
        except Exception as exc:
            rows.append({
                "Sector": item.get("sector", "Index"),
                "Stock": item.get("stock", item.get("symbol", item.get("ticker", ""))),
                "Ticker": item.get("ticker", ""),
                "Symbol": item.get("symbol", item.get("stock", "")),
                "Resolved Ticker": "",
                "Status": "DATA UNAVAILABLE", "Score": 0,
                "Frame": pd.DataFrame(), "Screens": {},
                "Scan Start": "", "Scan End": str(pd.Timestamp(end).date()),
                "Error": str(exc),
            })
    return rows

def clear_scan_cache():
    try: scan.clear()
    except Exception: pass
    try: download.clear()
    except Exception: pass
