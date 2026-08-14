"""
Multi-provider daily OHLCV data fetching.

Yahoo Finance (via the `yfinance` library) is unreliable for a lot of NSE
sector/thematic indexes and occasionally for individual stocks too (rate
limiting, symbol changes, empty responses, etc.). Instead of failing
straight to "DATA UNAVAILABLE", each symbol is tried against a small chain
of providers, in order, until one returns usable daily bars:

    1. yfinance.download()               (existing behaviour)
    2. Yahoo Finance "chart" JSON API     (raw HTTP call, independent of the
                                            yfinance library's own parsing,
                                            so it succeeds in some cases
                                            where yfinance itself returns
                                            an empty frame)
    3. NSE India official API             (nseindia.com) - the authoritative
                                            source for NSE equities *and*
                                            NSE sector/thematic indexes, and
                                            the one place that reliably has
                                            data for indexes Yahoo doesn't
                                            carry (Nifty MidCap 100, Nifty
                                            India Defence, etc).

Every function below returns a plain OHLCV DataFrame indexed by date
(columns: Open, High, Low, Close, Volume) or an empty DataFrame on failure.
Network/parsing errors are swallowed here; the caller decides what to do
with an empty result.
"""

import logging
import time
import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover - yfinance should always be installed
    yf = None

NEEDED_COLS = ["Open", "High", "Low", "Close", "Volume"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# A single, reused NSE session (NSE requires cookies from a normal page
# visit before its API endpoints will respond).
_nse_session = None
_nse_session_ts = 0
_NSE_SESSION_TTL = 600  # seconds


def _clean_frame(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    if not all(c in df.columns for c in NEEDED_COLS):
        return pd.DataFrame()
    df = df[NEEDED_COLS].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["Close"])
    if df.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


# ---------------------------------------------------------------------------
# Provider 1: yfinance library
# ---------------------------------------------------------------------------
def fetch_yfinance(symbol, start_ts, end_ts):
    if not symbol or yf is None:
        return pd.DataFrame()
    try:
        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            df = yf.download(
                symbol,
                start=start_ts.strftime("%Y-%m-%d"),
                end=(end_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        finally:
            logging.disable(previous_disable)
    except Exception:
        return pd.DataFrame()
    return _clean_frame(df)


# ---------------------------------------------------------------------------
# Provider 2: Yahoo "chart" JSON API, called directly over HTTP.
# This bypasses the yfinance library entirely, so it is a genuinely
# independent second attempt rather than a retry of the same code path.
# ---------------------------------------------------------------------------
def fetch_yahoo_chart_api(symbol, start_ts, end_ts):
    if not symbol:
        return pd.DataFrame()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": int(pd.Timestamp(start_ts).timestamp()),
        "period2": int((pd.Timestamp(end_ts) + pd.Timedelta(days=1)).timestamp()),
        "interval": "1d",
        "events": "div,splits",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return pd.DataFrame()
        result = result[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps or not quote:
            return pd.DataFrame()
        df = pd.DataFrame({
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
        }, index=pd.to_datetime(timestamps, unit="s"))
        return _clean_frame(df)
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Provider 3: NSE India official API (nseindia.com).
# This is the authoritative source and the only reliable place to get
# history for NSE sector/thematic indexes that Yahoo does not carry.
# ---------------------------------------------------------------------------
def _nse_get_session():
    global _nse_session, _nse_session_ts
    now = time.time()
    if _nse_session is not None and (now - _nse_session_ts) < _NSE_SESSION_TTL:
        return _nse_session
    session = requests.Session()
    session.headers.update(_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
        session.get("https://www.nseindia.com/get-quotes/equity?symbol=SBIN", timeout=10)
    except Exception:
        pass
    _nse_session = session
    _nse_session_ts = now
    return session


def fetch_nse_equity(symbol, start_ts, end_ts):
    """Daily history for an NSE-listed stock (bare symbol, no .NS)."""
    if not symbol:
        return pd.DataFrame()
    try:
        session = _nse_get_session()
        url = "https://www.nseindia.com/api/historical/cm/equity"
        params = {
            "symbol": symbol,
            "series": '["EQ"]',
            "from": start_ts.strftime("%d-%m-%Y"),
            "to": end_ts.strftime("%d-%m-%Y"),
        }
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame()
        rows = (resp.json() or {}).get("data") or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["CH_TIMESTAMP"])
        df = df.rename(columns={
            "CH_OPENING_PRICE": "Open",
            "CH_TRADE_HIGH_PRICE": "High",
            "CH_TRADE_LOW_PRICE": "Low",
            "CH_CLOSING_PRICE": "Close",
            "CH_TOT_TRADED_QTY": "Volume",
        }).set_index("date")
        return _clean_frame(df)
    except Exception:
        return pd.DataFrame()


def fetch_nse_index(index_name, start_ts, end_ts):
    """Daily history for an official NSE index name, e.g. 'NIFTY MIDCAP 100'."""
    if not index_name:
        return pd.DataFrame()
    try:
        session = _nse_get_session()
        url = "https://www.nseindia.com/api/historical/indicesHistory"
        params = {
            "indexType": index_name,
            "from": start_ts.strftime("%d-%m-%Y"),
            "to": end_ts.strftime("%d-%m-%Y"),
        }
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame()
        payload = (resp.json() or {}).get("data", {}).get("indexCloseOnlineRecords") or []
        if not payload:
            return pd.DataFrame()
        df = pd.DataFrame(payload)
        df["date"] = pd.to_datetime(df["EOD_TIMESTAMP"], format="%d-%b-%Y", errors="coerce")
        df = df.rename(columns={
            "EOD_OPEN_INDEX_VAL": "Open",
            "EOD_HIGH_INDEX_VAL": "High",
            "EOD_LOW_INDEX_VAL": "Low",
            "EOD_CLOSE_INDEX_VAL": "Close",
        })
        df["Volume"] = 0
        df = df.dropna(subset=["date"]).set_index("date")
        return _clean_frame(df)
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def fetch_daily(item, start_ts, end_ts, use_dhan=False):
    """
    Try providers in order for a single universe item.
    `item` is the dict from the universe config (with 'type' set to
    'stock' or 'index', and 'market' set to 'India' or 'USA').
    When use_dhan=True and the item is an Indian symbol, DHAN's broker API
    is tried first (see services/dhan_provider.py), before Yahoo/NSE.
    Returns (df, source_label, resolved_symbol, error_message).
    """
    is_index = item.get("type") == "index"
    is_india = item.get("market", "India") == "India"
    yahoo_symbol = str(item.get("ticker", "")).strip()
    nse_symbol = str(item.get("nse_symbol", "")).strip()

    attempts = []
    if use_dhan and is_india and nse_symbol:
        from services.dhan_provider import fetch_dhan
        def _dhan_attempt():
            df, err = fetch_dhan(item, start_ts, end_ts)
            _dhan_attempt.last_error = err
            return df
        _dhan_attempt.last_error = ""
        attempts.append(("DHAN API", _dhan_attempt))
    if yahoo_symbol:
        attempts.append(("Yahoo Finance", lambda: fetch_yfinance(yahoo_symbol, start_ts, end_ts)))
        attempts.append(("Yahoo Finance (direct)", lambda: fetch_yahoo_chart_api(yahoo_symbol, start_ts, end_ts)))
    if nse_symbol and is_india:
        if is_index:
            attempts.append(("NSE India", lambda: fetch_nse_index(nse_symbol, start_ts, end_ts)))
        else:
            attempts.append(("NSE India", lambda: fetch_nse_equity(nse_symbol, start_ts, end_ts)))

    if not attempts:
        return pd.DataFrame(), "", "", "No data source configured for this symbol."

    last_error = "No data returned by any configured data source."
    for label, fn in attempts:
        try:
            df = fn()
        except Exception as exc:
            last_error = str(exc)
            continue
        if df is not None and not df.empty:
            resolved = yahoo_symbol if "Yahoo" in label else nse_symbol
            return df, label, resolved, ""
        if hasattr(fn, "last_error") and fn.last_error:
            last_error = fn.last_error
    return pd.DataFrame(), "", (yahoo_symbol or nse_symbol), last_error
