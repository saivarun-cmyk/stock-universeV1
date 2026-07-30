from datetime import datetime
import time
import streamlit as st

from services.universe import stocks, indexes
from services.market import scan, clear_scan_cache
from ui.app import main, date_controls

st.set_page_config(page_title="Trading System Universe", page_icon="📈", layout="wide")

st.sidebar.markdown("## ⚙️ Scanner")
st.sidebar.caption("All stocks and indexes are loaded from config/universe.yaml.")
st.sidebar.caption("Daily timeframe only • No price filter")

end = date_controls()
run_now = st.sidebar.button("▶️ RUN SCANNER NOW", use_container_width=True, type="primary")

if run_now:
    clear_scan_cache()
    st.session_state.pop("scan_signature", None)
    st.rerun()

sig = ("Daily", end)
if st.session_state.get("scan_signature") != sig:
    with st.spinner("Loading daily market data and calculating indicators..."):
        started = time.time()
        rows = scan(stocks(), end)
        idx = scan(indexes(), end)
        st.session_state.update(
            scan_rows=rows, scan_indexes=idx, scan_signature=sig,
            scan_duration=time.time() - started, last_scan_at=datetime.now()
        )

meta = {
    "end": end,
    "scan_at": st.session_state.get("last_scan_at", datetime.now()),
    "duration": st.session_state.get("scan_duration", 0),
}
main(st.session_state.get("scan_rows", []), st.session_state.get("scan_indexes", []), meta)
