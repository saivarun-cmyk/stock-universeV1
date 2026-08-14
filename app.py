from datetime import date, datetime
from zoneinfo import ZoneInfo
import time
import streamlit as st

from services.universe import stocks, indexes
from services.market import scan, clear_scan_cache
from ui.app import main, date_controls, market_controls, data_source_controls

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Trading System Universe", page_icon="📈", layout="wide")

st.sidebar.markdown("## ⚙️ Scanner")
st.sidebar.caption("Stocks/indexes are loaded from config/universe_india.yaml or config/universe_usa.yaml, based on the Market selected below.")
st.sidebar.caption("Daily timeframe only • No price filter")

market = market_controls()
use_dhan = data_source_controls(market)
end, auto_run, run_time = date_controls()
run_now = st.sidebar.button("▶️ RUN SCANNER NOW", use_container_width=True, type="primary")

# --- Auto-run once/day at the configured IST time -------------------------
# Streamlit apps only execute while a session is open (there's no built-in
# background scheduler), so this triggers the scan automatically the next
# time the app is open/refreshed at or after the chosen IST time — it does
# NOT wake the app up on its own if nobody has it open. For a true
# unattended 3 PM run, schedule a request to this app's URL (e.g. via cron
# or your hosting platform's job scheduler) so a session exists at 3 PM.
now_ist = datetime.now(IST)
today_ist = now_ist.date()
already_ran_today = st.session_state.get("auto_run_last_date") == today_ist
if auto_run and now_ist.time() >= run_time and not already_ran_today:
    st.session_state["auto_run_last_date"] = today_ist
    st.sidebar.success(f"Auto-run triggered at {now_ist.strftime('%H:%M:%S')} IST")
    run_now = True

if run_now:
    clear_scan_cache()
    st.session_state.pop("scan_signature", None)
    st.rerun()

# Market + data-source flag are part of the cache signature so switching
# either one always forces a fresh scan instead of showing stale/mixed data.
sig = ("Daily", market, use_dhan, end)
if st.session_state.get("scan_signature") != sig:
    with st.spinner(f"Loading {market} daily market data and calculating indicators..."):
        started = time.time()
        rows = scan(stocks(market), end, use_dhan)
        idx = scan(indexes(market), end, use_dhan)
        st.session_state.update(
            scan_rows=rows, scan_indexes=idx, scan_signature=sig,
            scan_duration=time.time() - started, last_scan_at=datetime.now()
        )

meta = {
    "end": end,
    "market": market,
    "use_dhan": use_dhan,
    "scan_at": st.session_state.get("last_scan_at", datetime.now()),
    "duration": st.session_state.get("scan_duration", 0),
}
main(st.session_state.get("scan_rows", []), st.session_state.get("scan_indexes", []), meta)
