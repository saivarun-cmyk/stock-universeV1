from datetime import date, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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
    return end

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
        })
    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Signal": st.column_config.TextColumn("SIGNAL", width="medium"),
            "Strength": st.column_config.TextColumn("STRENGTH"),
            "Score": st.column_config.TextColumn("SCORE"),
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

def _indexes(rows):
    st.subheader("🇮🇳 INDIA INDEXES")
    st.caption("Daily only. Indexes use the same scanner formulas as stocks.")
    _table(rows, "indexes_table")
    unavailable = [r for r in rows if r.get("Status") == "DATA UNAVAILABLE"]
    if unavailable:
        st.warning("Some configured NSE sector indexes are not available from Yahoo Finance. They are shown as DATA UNAVAILABLE instead of repeatedly generating 404 errors.")
        st.dataframe(pd.DataFrame([{
            "Index": r.get("Symbol",""), "Configured Yahoo Symbol": r.get("Ticker",""),
            "Reason": r.get("Error","")
        } for r in unavailable]), use_container_width=True, hide_index=True)

def _formula_guide():
    from services.market import FORMULAS
    st.subheader("📐 Formula & Strategy Guide")
    for name, rules in FORMULAS.items():
        with st.expander(name):
            for i, rule in enumerate(rules, 1):
                st.markdown(f"**{i}.** `{rule}`")

def main(stocks, indexes, meta):
    st.markdown("# 📈 TRADING SYSTEM UNIVERSE")
    st.caption("Daily • Multi-Screener Trading Scanner")
    st.info(f"📅 **Daily scan:** {meta['end']}  •  Data through selected candle  •  Last run: {meta['scan_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    sector_values = sorted({r.get("Sector","") for r in stocks if r.get("Sector","")})
    sector = st.sidebar.selectbox("Sector", ["All Sectors"] + sector_values)

    tabs = st.tabs([
        "📊 Scanner Overview",
        "🟢 Bullish Universe", "🔴 Bearish Universe",
        "🟢 Bullish Reclaim", "🟢 Bullish Pullback",
        "🔴 Bearish Breakdown", "🔴 Bearish Pullback",
        "🔻 Bearish Continuation", "📦 Darvas",
        "📋 Complete Stocks List", "🇮🇳 INDIA INDEXES", "📐 Formula Guide",
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
        _indexes(indexes)
    with tabs[11]:
        _formula_guide()
