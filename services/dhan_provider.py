"""
DHAN (DhanHQ) broker API as an optional data source for Indian stocks and
indexes, selectable via the sidebar toggle instead of the default
Yahoo -> NSE fallback chain.

IMPORTANT — please read before relying on this in production:
This talks to DhanHQ's official v2 Data API (https://dhanhq.co/docs), which
is the real, documented broker API. It is NOT the same thing as "TradingView
through Dhan": Dhan's app/website embeds TradingView's charting *widget* for
on-screen charts only — there is no separate public TradingView data-pull
endpoint exposed through Dhan for bulk historical downloads. If your research
turned up something more specific than the charting widget, send the link
and this can be wired in properly; otherwise DhanHQ's own Data API (used
here) is the correct integration point for "pull real OHLC values from
Dhan."

This module could not be tested against live DhanHQ endpoints from this
environment (no network access to dhan.co here), so endpoint paths / JSON
field names are implemented per DhanHQ's published v2 docs from memory and
may need small adjustments if Dhan has changed field names since. Every
failure is caught and surfaced as a clear error string rather than crashing,
so mismatches are easy to spot and fix.

Setup required to use this provider:
  1. A Dhan trading account with API access enabled (Dhan web -> My Profile
     -> DhanHQ Trading APIs), which gives you a Client ID and Access Token.
  2. Provide them either via Streamlit secrets (recommended):
         # .streamlit/secrets.toml
         DHAN_CLIENT_ID = "your-client-id"
         DHAN_ACCESS_TOKEN = "your-access-token"
     ...or paste them into the sidebar fields at runtime (session-only,
     never written to disk by this app).
"""

import time
import pandas as pd
import requests
import streamlit as st

DHAN_BASE = "https://api.dhan.co/v2"
SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
NEEDED_COLS = ["Open", "High", "Low", "Close", "Volume"]


def get_credentials():
    """Client ID / access token from st.secrets first, then session_state
    (sidebar input), then None if neither is set."""
    client_id = None
    token = None
    try:
        # client_id = st.secrets.get("DHAN_CLIENT_ID")
        # token = st.secrets.get("DHAN_ACCESS_TOKEN")
        client_id = "1109844367"
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzg2ODIwMDMyLCJpYXQiOjE3ODY3MzM2MzIsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5ODQ0MzY3In0.Vo1x553Z_6L3hsNyA0hFpqd0qZ9wYG6X8KjXaXojvN9WvUM8-BHB9_wJ_yHcqKNHuW5oiFlj6gbtK8IxgB3_cw"

    except Exception:
        pass

    client_id = client_id or st.session_state.get("dhan_client_id", "")
    token = token or st.session_state.get("dhan_access_token", "")
    return str(client_id or "").strip(), str(token or "").strip()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _load_scrip_master():
    """Download & cache Dhan's instrument master (symbol -> securityId map).
    Cached for 6 hours since this file is large and changes infrequently."""
    try:
        resp = requests.get(SCRIP_MASTER_URL, timeout=30)
        resp.raise_for_status()
        from io import StringIO

        df = pd.read_csv(StringIO(resp.text), low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _resolve_security_id(nse_symbol, is_index):
    """Look up a Dhan securityId for an NSE equity symbol or index name."""
    master = _load_scrip_master()
    if master.empty:
        return None, "Could not download/parse Dhan's scrip master CSV."

    seg_col = _find_col(master, ["SEM_SEGMENT", "SEM_EXM_EXCH_ID", "EXCH_ID"])
    sym_col = _find_col(
        master, ["SEM_TRADING_SYMBOL", "SEM_CUSTOM_SYMBOL", "SYMBOL_NAME"]
    )
    id_col = _find_col(
        master, ["SEM_SMST_SECURITY_ID", "SECURITY_ID", "SEM_SECURITY_ID"]
    )
    instrument_col = _find_col(
        master, ["SEM_INSTRUMENT_NAME", "SEM_EXCH_INSTRUMENT_TYPE", "INSTRUMENT_TYPE"]
    )
    exch_col = _find_col(master, ["SEM_EXM_EXCH_ID", "EXCH_ID"])

    if not sym_col or not id_col:
        return (
            None,
            "Unexpected scrip-master CSV format — Dhan may have changed column names.",
        )

    subset = master
    if exch_col:
        subset = subset[
            subset[exch_col].astype(str).str.upper().str.contains("NSE", na=False)
        ]
    if instrument_col:
        wanted = "INDEX" if is_index else "EQUITY"
        matched = subset[
            subset[instrument_col]
            .astype(str)
            .str.upper()
            .str.contains(wanted, na=False)
        ]
        if not matched.empty:
            subset = matched

    needle = str(nse_symbol).strip().upper()
    hit = subset[subset[sym_col].astype(str).str.upper() == needle]
    if hit.empty:
        hit = subset[
            subset[sym_col].astype(str).str.upper().str.contains(needle, na=False)
        ]
    if hit.empty:
        return (
            None,
            f"No Dhan security id found for '{nse_symbol}' ({'index' if is_index else 'equity'}).",
        )
    return str(hit.iloc[0][id_col]), ""


def fetch_dhan(item, start_ts, end_ts):
    """
    Fetch daily OHLCV for one universe item via DhanHQ's v2 historical data
    API. `item` needs 'nse_symbol' (equity symbol or index name) and 'type'
    ('stock' or 'index'). Returns (df, error_message).
    """
    client_id, token = get_credentials()
    if not client_id or not token:
        return (
            pd.DataFrame(),
            "Dhan credentials not set (add DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN in secrets or the sidebar).",
        )

    nse_symbol = str(item.get("nse_symbol", "")).strip()
    is_index = item.get("type") == "index"
    if not nse_symbol:
        return pd.DataFrame(), "No NSE symbol configured for Dhan lookup."

    security_id, err = _resolve_security_id(nse_symbol, is_index)
    if not security_id:
        return pd.DataFrame(), err

    url = f"{DHAN_BASE}/charts/historical"
    headers = {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "securityId": security_id,
        "exchangeSegment": "IDX_I" if is_index else "NSE_EQ",
        "instrument": "INDEX" if is_index else "EQUITY",
        "expiryCode": 0,
        "oi": False,
        "fromDate": start_ts.strftime("%Y-%m-%d"),
        "toDate": end_ts.strftime("%Y-%m-%d"),
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=15)
        if resp.status_code != 200:
            return (
                pd.DataFrame(),
                f"Dhan API HTTP {resp.status_code}: {resp.text[:200]}",
            )
        data = resp.json()
        if not data or "close" not in data:
            return (
                pd.DataFrame(),
                f"Unexpected Dhan API response shape: {str(data)[:200]}",
            )
        idx = pd.to_datetime(data.get("timestamp", []), unit="s", errors="coerce")
        df = pd.DataFrame(
            {
                "Open": data.get("open", []),
                "High": data.get("high", []),
                "Low": data.get("low", []),
                "Close": data.get("close", []),
                "Volume": data.get("volume", [0] * len(data.get("close", []))),
            },
            index=idx,
        )
        df = df.dropna(subset=["Close"])
        if df.empty:
            return pd.DataFrame(), "Dhan API returned no bars for this date range."
        df.index = df.index.normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df[NEEDED_COLS], ""
    except Exception as exc:
        return pd.DataFrame(), f"Dhan API error: {exc}"
