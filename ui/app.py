from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

IST = ZoneInfo("Asia/Kolkata")

SCREENER_NAMES = [
    "Bullish Universe", "Bearish Universe", "Bullish Reclaim",
    "Bullish Pullback", "Bearish Breakdown", "Bearish Pullback",
    "Bearish Continuation", "Darvas",
]
REGIME_ORDER = {
    "STRONG BULLISH": 0, "BULLISH": 1, "NEUTRAL": 2,
    "BEARISH": 3, "STRONG BEARISH": 4, "DATA UNAVAILABLE": 5,
}
REGIME_STYLE = {
    "STRONG BULLISH": ("🔥", "STRONG BULLISH", "Very Strong"),
    "BULLISH": ("🟢", "BULLISH", "Bullish"),
    "NEUTRAL": ("⚪", "NEUTRAL", "Neutral"),
    "BEARISH": ("🔴", "BEARISH", "Bearish"),
    "STRONG BEARISH": ("🛑", "STRONG BEARISH", "Very Weak"),
    "DATA UNAVAILABLE": ("⚠️", "DATA UNAVAILABLE", "Unavailable"),
}

def market_controls():
    st.sidebar.markdown("### 🌍 Market")
    market = st.sidebar.selectbox(
        "Select market", ["🇮🇳 India", "🇺🇸 USA"], key="market_select",
    )
    market = "India" if "India" in market else "USA"
    st.sidebar.caption(
        "India and USA symbols are scanned and shown completely separately — "
        "switching this reloads a different universe file, never a mixed list."
    )
    return market

def data_source_controls(market):
    """DHAN broker API toggle — India only (Dhan does not cover US markets)."""
    if market != "India":
        return False
    st.sidebar.markdown("### 🔌 India Data Source")
    use_dhan = st.sidebar.toggle(
        "Use DHAN broker API as primary source",
        value=st.session_state.get("use_dhan", False),
        key="use_dhan",
        help=(
            "ON: try DHAN's official Data API first for every Indian symbol, "
            "then fall back to Yahoo → NSE India if DHAN has no data.\n"
            "OFF (default): Yahoo Finance → Yahoo (direct) → NSE India, as before.\n\n"
            "Note: this uses DhanHQ's own historical-data API, not TradingView — "
            "Dhan's TradingView charts are a visual widget only, there's no public "
            "TradingView data-pull endpoint exposed through Dhan."
        ),
    )
    if use_dhan:
        from services.dhan_provider import get_credentials
        client_id, token = get_credentials()
        if not client_id or not token:
            with st.sidebar.expander("🔑 Enter DHAN credentials", expanded=True):
                st.caption("Session-only — not saved to disk. For a persistent setup, add these to `.streamlit/secrets.toml` instead.")
                st.text_input("DHAN Client ID", key="dhan_client_id")
                st.text_input("DHAN Access Token", key="dhan_access_token", type="password")
        else:
            st.sidebar.success("DHAN credentials detected ✓")
    return use_dhan

def date_controls():
    st.sidebar.markdown("### 📅 Daily Scan")
    choice = st.sidebar.selectbox(
        "Candle to scan",
        ["Latest / Today", "Yesterday", "2 Days Ago", "3 Days Ago", "Custom Date"],
        key="daily_candle",
    )
    today = date.today()
    if choice == "Latest / Today":
        end = today
    elif choice == "Yesterday":
        end = today - timedelta(days=1)
    elif choice == "2 Days Ago":
        end = today - timedelta(days=2)
    elif choice == "3 Days Ago":
        end = today - timedelta(days=3)
    else:
        end = st.sidebar.date_input("Custom Date", today, key="custom_daily_date")
    st.sidebar.caption(f"Scan through: **{end}**")

    now_ist = datetime.now(IST)
    st.sidebar.markdown("### ⏱️ Auto-Run (IST)")
    auto_run = st.sidebar.toggle(
        "Auto-run once per day at set time",
        value=st.session_state.get("auto_run_enabled", False),
        key="auto_run_enabled",
        help=(
            "When the app is open (or reloaded) at/after this IST time, it "
            "triggers RUN SCANNER NOW automatically, once per calendar day. "
            "Streamlit has no background scheduler of its own, so this only "
            "fires while someone/something has the app open — for a true "
            "unattended 3 PM run, schedule `streamlit run app.py` (or hit "
            "this URL) via cron / a hosting platform's scheduler."
        ),
    )
    run_time = st.sidebar.time_input(
        "Daily run time (IST)", value=st.session_state.get("auto_run_time", dtime(15, 0)),
        key="auto_run_time",
    )
    if now_ist.time() < dtime(15, 30):
        st.sidebar.caption(
            f"🕒 IST now: {now_ist.strftime('%H:%M:%S')} — NSE closes 3:30 PM IST, "
            "so today's daily candle may still be forming if you scan before then."
        )
    else:
        st.sidebar.caption(f"🕒 IST now: {now_ist.strftime('%H:%M:%S')} — today's daily candle should be final.")
    return end, auto_run, run_time

def chart(df, key, title):
    if df is None or df.empty:
        st.info("Chart unavailable for this symbol.")
        return
    fig = go.Figure(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price"
    ))
    for c in ["SMA10", "EMA20", "SMA50"]:
        if c in df:
            fig.add_trace(go.Scatter(x=df.index, y=df[c], mode="lines", name=c))
    fig.update_layout(
        template="plotly_dark", height=420,
        xaxis_rangeslider_visible=False, title=title,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)

def _filtered(rows, sector):
    return [r for r in rows if sector == "All Sectors" or r.get("Sector") == sector]

def _rank(rows):
    return sorted(
        rows,
        key=lambda r: (
            REGIME_ORDER.get(r.get("Status", "DATA UNAVAILABLE"), 5),
            -float(r.get("Score", 0)),
            str(r.get("Stock", "")),
        ),
    )

def _summary(rows):
    counts = {k: 0 for k in REGIME_ORDER}
    for r in rows:
        counts[r.get("Status", "DATA UNAVAILABLE")] = counts.get(r.get("Status", "DATA UNAVAILABLE"), 0) + 1
    cols = st.columns(5)
    for col, label in zip(cols, ["STRONG BULLISH","BULLISH","NEUTRAL","BEARISH","STRONG BEARISH"]):
        icon, text, _ = REGIME_STYLE[label]
        with col:
            st.metric(f"{icon} {text}", counts.get(label, 0))

def _table(rows, key):
    rows = _rank(rows)
    if not rows:
        st.info("No stocks matched this screener.")
        return
    data = []
    for r in rows:
        icon, label, strength = REGIME_STYLE.get(r.get("Status"), ("⚠️", "DATA UNAVAILABLE", "Unavailable"))
        data.append({
            "Signal": f"{icon} {label}",
            "Strength": strength,
            "Score": f'{r.get("Score", 0)}/100',
            "Sector": r.get("Sector", ""),
            "Stock": r.get("Stock", ""),
            "Ticker": r.get("Ticker", ""),
            "Scan End": r.get("Scan End", ""),
            "Source": r.get("Data Source", "") or ("—" if r.get("Status") != "DATA UNAVAILABLE" else "None"),
        })
    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Signal": st.column_config.TextColumn("SIGNAL", width="medium"),
            "Strength": st.column_config.TextColumn("STRENGTH"),
            "Score": st.column_config.TextColumn("SCORE"),
            "Source": st.column_config.TextColumn("DATA SOURCE"),
        },
        key=key,
    )

def _condition_detail(row, screen):
    result = row.get("Screens", {}).get(screen, {})
    if not result:
        st.info("No calculation data available.")
        return
    st.markdown(f"### {row.get('Stock')} — {screen}")
    st.caption(f"Daily candle used: {row.get('Scan End')}")
    detail = pd.DataFrame([
        {"Condition": k, "Result": "✅ PASS" if v else "❌ FAIL"}
        for k, v in result.get("conditions", {}).items()
    ])
    st.dataframe(detail, use_container_width=True, hide_index=True)

def _screener_tab(rows, name):
    matched = [r for r in rows if r.get("Screens", {}).get(name, {}).get("signal")]
    st.subheader(name)
    st.caption(f"{len(matched)} stocks matched • Results ordered Strong Bullish → Bullish → Neutral → Bearish → Strong Bearish")
    _summary(matched)
    _table(matched, f"table_{name.replace(' ','_')}")
    if matched:
        options = [f"{r['Stock']} · {r['Ticker']}" for r in matched]
        selected = st.selectbox("Inspect conditions", options, key=f"inspect_{name}")
        row = next(r for r in matched if f"{r['Stock']} · {r['Ticker']}" == selected)
        _condition_detail(row, name)

def _complete(rows):
    st.subheader("📋 Complete Stocks List")
    ranked = _rank(rows)
    data = [{
        "Signal": f"{REGIME_STYLE.get(r['Status'], ('⚠️',r['Status'],'Unavailable'))[0]} {r['Status']}",
        "Score": f"{r.get('Score',0)}/100",
        "Sector": r.get("Sector",""),
        "Stock": r.get("Stock",""),
        "Ticker": r.get("Ticker",""),
        "Scan Start": r.get("Scan Start",""),
        "Scan End": r.get("Scan End",""),
    } for r in ranked]
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    usable = [r for r in ranked if not r.get("Frame", pd.DataFrame()).empty]
    if usable:
        choice = st.selectbox("Inspect stock", [f"{r['Stock']} · {r['Ticker']}" for r in usable], key="complete_inspect")
        row = next(r for r in usable if f"{r['Stock']} · {r['Ticker']}" == choice)
        chart(row["Frame"], f"complete_chart_{row['Ticker']}", f"Daily — {row['Stock']}")
        st.caption(f"Data used: {row['Scan Start']} → {row['Scan End']}")

def _indexes(rows, market):
    label = "🇮🇳 INDIA INDEXES" if market == "India" else "🇺🇸 USA INDEXES / ETFs"
    st.subheader(label)
    st.caption("Daily only. Indexes use the same scanner formulas as stocks.")
    _table(rows, "indexes_table")
    unavailable = [r for r in rows if r.get("Status") == "DATA UNAVAILABLE"]
    if unavailable:
        source_note = (
            "Yahoo Finance, the direct Yahoo API, the DHAN broker API, or the NSE India fallback"
            if market == "India" else "Yahoo Finance or the direct Yahoo API"
        )
        st.warning(f"These symbols returned no data from {source_note}.")
        st.dataframe(pd.DataFrame([{
            "Index": r.get("Symbol",""), "Configured Yahoo Symbol": r.get("Ticker","") or "(none)",
            "Reason": r.get("Error","")
        } for r in unavailable]), use_container_width=True, hide_index=True)

def _ema13_tab(stocks, indexes):
    st.subheader("📏 EMA13 Distance Scanner")
    st.caption(
        "EMA13 = (Close × 0.142857) + (Yesterday EMA13 × 0.857143)  •  "
        "Distance % = ((Close − EMA13) / EMA13) × 100  •  "
        "Ranked by absolute distance, closest to EMA13 first."
    )

    scope = st.radio(
        "Show", ["Stocks + Indexes", "Stocks Only", "Indexes Only"],
        horizontal=True, key="ema13_scope",
    )
    if scope == "Stocks Only":
        pool = [dict(r, Type="Stock") for r in stocks]
    elif scope == "Indexes Only":
        pool = [dict(r, Type="Index") for r in indexes]
    else:
        pool = [dict(r, Type="Stock") for r in stocks] + [dict(r, Type="Index") for r in indexes]

    usable = [r for r in pool if r.get("EMA13 Abs Distance %") is not None]
    unavailable = [r for r in pool if r.get("EMA13 Abs Distance %") is None]

    if not usable:
        st.info("No EMA13 values available yet — data may still be loading or unavailable for this selection.")
        return

    ranked = sorted(usable, key=lambda r: r["EMA13 Abs Distance %"])

    c1, c2, c3 = st.columns(3)
    above = sum(1 for r in ranked if r["EMA13 Distance %"] > 0)
    below = sum(1 for r in ranked if r["EMA13 Distance %"] < 0)
    c1.metric("Total Ranked", len(ranked))
    c2.metric("🟢 Above EMA13", above)
    c3.metric("🔴 Below EMA13", below)

    data = []
    for i, r in enumerate(ranked, 1):
        dist = r["EMA13 Distance %"]
        data.append({
            "Rank": i,
            "Side": "🟢 Above" if dist > 0 else ("🔴 Below" if dist < 0 else "⚪ At"),
            "Type": r.get("Type", ""),
            "Sector": r.get("Sector", ""),
            "Name": r.get("Stock", ""),
            "Ticker": r.get("Ticker", ""),
            "Close": round(r.get("Close", 0) or 0, 2),
            "EMA13": round(r.get("EMA13", 0) or 0, 2),
            "Distance %": round(dist, 2),
            "Abs Distance %": round(r["EMA13 Abs Distance %"], 2),
            "Candle Used": r.get("Scan End", ""),
            "Source": r.get("Data Source", ""),
        })
    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True, hide_index=True,
        column_config={
            "Distance %": st.column_config.NumberColumn(format="%.2f%%"),
            "Abs Distance %": st.column_config.NumberColumn(format="%.2f%%"),
        },
        key="ema13_table",
    )

    if unavailable:
        with st.expander(f"⚠️ {len(unavailable)} symbol(s) without enough data for EMA13"):
            st.dataframe(pd.DataFrame([{
                "Type": r.get("Type", ""), "Name": r.get("Stock", ""),
                "Ticker": r.get("Ticker", ""), "Reason": r.get("Error", "Not enough daily bars yet"),
            } for r in unavailable]), use_container_width=True, hide_index=True)

def _formula_guide():
    from services.market import FORMULAS
    st.subheader("📐 Formula & Strategy Guide")
    with st.expander("EMA13 Distance", expanded=True):
        for i, rule in enumerate(FORMULAS["EMA13 Distance"], 1):
            st.markdown(f"**{i}.** `{rule}`")
        st.markdown("---")
        st.markdown("**Worked example**")
        st.markdown(
            "- Current Price = 1020, Yesterday EMA13 = 1000\n"
            "- EMA13 today = (1020 × 0.142857) + (1000 × 0.857143) = **1002.86**\n"
            "- Distance % = ((1020 − 1002.86) / 1002.86) × 100 = **1.71%**\n"
            "- Stock is **1.71% above EMA13** → shows up near the top of the "
            "EMA13 Distance tab once ranked by Abs Distance %."
        )
    for name, rules in FORMULAS.items():
        if name == "EMA13 Distance":
            continue
        with st.expander(name):
            for i, rule in enumerate(rules, 1):
                st.markdown(f"**{i}.** `{rule}`")

def main(stocks, indexes, meta):
    market = meta.get("market", "India")
    flag = "🇮🇳" if market == "India" else "🇺🇸"
    st.markdown(f"# 📈 TRADING SYSTEM UNIVERSE — {flag} {market}")
    st.caption("Daily • Multi-Screener Trading Scanner")
    src_note = " • Source: DHAN (primary)" if meta.get("use_dhan") else ""
    st.info(f"📅 **Daily scan:** {meta['end']}  •  Data through selected candle  •  Last run: {meta['scan_at'].strftime('%Y-%m-%d %H:%M:%S')}{src_note}")

    sector_values = sorted({r.get("Sector","") for r in stocks if r.get("Sector","")})
    sector = st.sidebar.selectbox("Sector", ["All Sectors"] + sector_values)

    tabs = st.tabs([
        "📊 Scanner Overview",
        "🟢 Bullish Universe", "🔴 Bearish Universe",
        "🟢 Bullish Reclaim", "🟢 Bullish Pullback",
        "🔴 Bearish Breakdown", "🔴 Bearish Pullback",
        "🔻 Bearish Continuation", "📦 Darvas",
        "📋 Complete Stocks List", f"{flag} {market.upper()} INDEXES",
        "📏 EMA13 Distance", "📐 Formula Guide",
    ])

    selected = _filtered(stocks, sector)
    with tabs[0]:
        st.subheader("📊 Daily Market Regime")
        _summary(selected)
        _table(selected, "overview_table")

    for tab, name in zip(tabs[1:9], SCREENER_NAMES):
        with tab:
            _screener_tab(selected, name)

    with tabs[9]:
        _complete(selected)
    with tabs[10]:
        _indexes(indexes, market)
    with tabs[11]:
        _ema13_tab(stocks, indexes)
    with tabs[12]:
        _formula_guide()
