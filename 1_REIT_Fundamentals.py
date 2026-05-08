import streamlit as st
import pandas as pd

from src.fetchers.yfinance_fetcher import fetch_all_fundamentals
from src.processors.fundamentals import build_fundamentals_table
from src.utils.cache import cache_timestamp
from src.utils.formatters import fmt_large, fmt_pct, fmt_multiple
from config import SIGNAL_GREEN, SIGNAL_RED, TEXT_MUTED, CARD_BG

st.set_page_config(page_title="REIT Fundamentals", layout="wide")

st.markdown(f"""
<style>
  .ts {{ color: {TEXT_MUTED}; font-size: 0.72rem; }}
</style>
""", unsafe_allow_html=True)

st.markdown("# REIT Fundamentals")
st.caption("FFO [est.] = Net Income (TTM) + D&A (TTM) via yfinance. Ground truth from SEC EDGAR in Phase 2.")


@st.cache_data(ttl=3600, show_spinner="Loading fundamentals…")
def load():
    raw = fetch_all_fundamentals()
    return build_fundamentals_table(raw)


df = load()
ts = cache_timestamp("reit_fundamentals") or "—"

# ── Filters ────────────────────────────────────────────────────────────────────

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    cats = st.multiselect("Category", df["category"].unique().tolist(), default=df["category"].unique().tolist())
with col_f2:
    min_yield, max_yield = 0.0, 0.15
    yield_range = st.slider("Div Yield range", min_yield, max_yield, (min_yield, max_yield), step=0.005, format="%.1%%")
with col_f3:
    flag_filter = st.multiselect("Payout Flag", ["ok", "yellow", "red", "na"], default=["ok", "yellow", "red", "na"])

mask = (
    df["category"].isin(cats) &
    df["payout_flag"].isin(flag_filter)
)
if "div_yield" in df.columns:
    mask &= df["div_yield"].between(yield_range[0], yield_range[1], inclusive="both").fillna(True)

filtered = df[mask]
st.markdown(f"**{len(filtered)}** tickers shown")


# ── Table ──────────────────────────────────────────────────────────────────────

def _flag_icon(flag: str) -> str:
    return {"red": "🔴", "yellow": "🟡", "ok": "🟢", "na": "—"}.get(flag, "—")


def _lev_icon(flag: str) -> str:
    return {"red": "🔴", "yellow": "🟡", "ok": "🟢", "na": "—"}.get(flag, "—")


display = pd.DataFrame({
    "Company":         filtered["name"],
    "Cat":             filtered["category"],
    "Price":           filtered["price"].map(lambda x: f"${x:.2f}" if x == x else "—"),
    "Mkt Cap":         filtered["market_cap"].map(fmt_large),
    "Div Yield":       filtered["div_yield"].map(lambda x: fmt_pct(x) if x == x else "—"),
    "Div Rate":        filtered["div_rate"].map(lambda x: f"${x:.2f}" if x == x else "—"),
    "Payout":          filtered["payout_ratio"].map(lambda x: fmt_pct(x) if x == x else "—"),
    "Payout ⚑":       filtered["payout_flag"].map(_flag_icon),
    "FFO/Sh [est.]":   filtered["ffo_per_share"].map(lambda x: f"${x:.2f}" if x == x else "—"),
    "P/FFO [est.]":    filtered["p_ffo"].map(lambda x: fmt_multiple(x) if x == x else "—"),
    "Fwd EPS":         filtered["forward_eps"].map(lambda x: f"${x:.2f}" if x == x else "—"),
    "ND/EBITDA":       filtered["net_debt_ebitda"].map(lambda x: f"{x:.1f}x" if x == x else "—"),
    "Lev ⚑":          filtered["leverage_flag"].map(_lev_icon),
    "52W High":        filtered["week52_high"].map(lambda x: f"${x:.2f}" if x == x else "—"),
    "vs 52W High":     filtered["pct_from_52w_high"].map(lambda x: fmt_pct(x) if x == x else "—"),
}, index=filtered.index)

st.dataframe(display, use_container_width=True, height=600)

st.markdown(f'<p class="ts">Source: yfinance · Last updated: {ts} · FFO [est.] = Net Income TTM + D&A TTM</p>', unsafe_allow_html=True)

# ── Raw data expander ──────────────────────────────────────────────────────────

with st.expander("Raw data (all columns)"):
    st.dataframe(filtered, use_container_width=True)
