# RPM Living — Investment Intelligence Dashboard
## Claude Code Project Context

---

### What This Is

An institutional-grade REIT analytics and market intelligence dashboard built in Python/Streamlit. It is designed to demonstrate analytical capability to senior contacts at multifamily REPE and real estate syndication firms — specifically RPM Living. The audience is Bloomberg-literate GPs and LPs with a high bar for data quality and signal clarity.

**Design philosophy:** Signal over decoration. Every element earns its place. Institutional look modeled on the DivcoWest fund report aesthetic — black header, gold accent (#C8A96E), light body (#F5F4F0), dark stat grids.

---

### Running the App

```bash
cd /Users/jaedenkinlock/reit_dashboard
python3 -m streamlit run app.py
```

Fetch / refresh REIT data:
```bash
python3 -m src.fetchers.yfinance_fetcher
```

---

### Stack

| Layer | Tool |
|---|---|
| UI | Streamlit (light theme base + heavy CSS injection) |
| Data | yfinance (fundamentals), FRED API stub (Phase 2), CoStar/Yardi/RealPage hardcoded (Q4 2024) |
| Cache | Parquet files in `data/cache/` — date-stamped, daily TTL |
| Logging | Structured JSON to `logs/fetch_errors.log`, human-readable to console |
| Config | `config.py` — tickers, markets, FRED series, UI color palette |

---

### File Map

```
app.py                          — Main Streamlit app (5 tabs)
config.py                       — REIT universe, market tiers, color palette, thresholds
src/
  fetchers/
    yfinance_fetcher.py         — Primary data fetcher (21 REIT tickers, retry logic, cache)
    fred_fetcher.py             — Stub (Phase 2)
    edgar_fetcher.py            — Stub (Phase 2 — ground-truth FFO)
  processors/
    fundamentals.py             — Payout + leverage flag logic
    deal_scorer.py              — 8-criterion deal scoring engine (0–100 scale)
  utils/
    cache.py                    — Parquet read/write with TTL
    logger.py                   — get_logger() factory
    formatters.py               — fmt_currency, fmt_pct, fmt_large, fmt_multiple, fmt_bps
pages/
  1_REIT_Fundamentals.py        — Sortable full fundamentals table (secondary page)
data/cache/                     — Parquet cache (auto-managed, gitignored)
logs/                           — Fetch error logs
```

---

### REIT Universe (21 Tickers)

| Sector | Tickers |
|---|---|
| Multifamily | EQR, AVB, MAA, CPT, UDR, NXRT, IRT, CSR, BRT, ESS, VRE |
| Homebuilder | DHI, LEN, PHM, TOL, NVR, MTH, MHO, TMHC |
| SFR/BTR | INVH, AMH |

**Delisted/excluded:** AIRC (taken private by Blackstone 2023 → replaced with CSR), MDC (acquired by Sekisui House 2024 → replaced with MTH), ELME (taken private 2023 → excluded).

---

### App Tabs

1. **Investment Thesis** — 6-card overview grid + 8 clickable pillar expanders (Multifamily Value-Add, Sun Belt Migration, Supply/Demand Imbalance, Vertically Integrated Platform, Loss-to-Lease, BTR Development, NOI Through Operations, Institutional Capital)

2. **REIT Comparables** — Hero metrics + filter/sort controls (no underscores in labels; payout risk shown as LOW RISK / MODERATE / HIGH RISK) + sortable data table + ticker detail panel (selectbox → 12-field KV card)

3. **Market Intelligence** — Market lookup selectbox (any of 18 RPM target markets → instant render) + Tier 1 / Tier 2 / Tier 3 sub-tabs with `st.expander()` per market. Each market block: dark stat grid (7 stats including Net Absorption) + amber insight box + source bar.

4. **Deal Analyzer** — 8-criterion 0–100 scoring engine. Inputs: market, asset class, units, year built, price, NOI, cap rate, rents, vacancy, 10Y treasury. Outputs: score hero + recommendation box + criterion breakdown grid + metrics strip. RPM market presence (0–100) is a first-class scoring input.

5. **Macro Overlay** — Phase 2 placeholder (FRED GS10, CPI, vacancy, permits, unemployment)

---

### Key Design Rules (Do Not Break)

- **No emojis anywhere.** Flags are HTML badges: `<span class="badge-red">HIGH RISK</span>`, `<span class="badge-yellow">MODERATE</span>`, `<span class="badge-ok">LOW RISK</span>`, `<span class="badge-na">N/A</span>`.
- **FFO is a proxy in Phase 1.** Label all FFO/P-FFO values as `[est.]`. FFO = Net Income TTM + D&A TTM from yfinance quarterly cashflow. Ground-truth FFO from EDGAR is Phase 2.
- **AFFO not shown in Phase 1.** Show as "Phase 2 — EDGAR integration required" if referenced.
- **Color palette** — only use RPM_* variables from config.py. Never introduce new hex codes.
- **Light theme.** `.streamlit/config.toml` sets `base="light"`. The dark elements (header, sub-bar, stat grids) are CSS injected.
- **No sidebar.** `initial_sidebar_state="collapsed"`. All navigation is in-tab.
- **Data provenance.** Every stat has a `src` note (Yardi Matrix Q4 2024, RealPage Q4 2024, CoStar Q4 2024, BLS 2024, Census ACS 2023). Never add data without a source citation.
- **Professional capitalizations.** Expander labels, section labels, stat labels use Title Case. No ALL CAPS in headers. No lowercase headers.
- **Payout flag thresholds:** >90% payout ratio = MODERATE, >100% = HIGH RISK (config.py: AFFO_PAYOUT_YELLOW=0.90, AFFO_PAYOUT_RED=1.00).
- **Leverage flag thresholds:** ND/EBITDA >7x = MODERATE, >9x = HIGH RISK.

---

### Market Data Architecture

Market data in the Market Intelligence tab is defined as `T1_MARKETS` and `T2_MARKETS` lists of dicts (inside `with tab_markets:`). Each dict has: `name`, `expander`, `subtitle`, `stats` (list of dicts with val/label/src/cls), `insights` (list of 2-tuples), `sources`.

`ALL_MARKETS_DICT = {m["name"]: m for m in T1_MARKETS + T2_MARKETS}` powers the market lookup selectbox. To add or edit a market, edit the dict in `T1_MARKETS` or `T2_MARKETS` — the expanders and lookup both update automatically.

---

### Deal Scorer (`src/processors/deal_scorer.py`)

8 criteria, 100 total points:

| Criterion | Weight |
|---|---|
| Market Fit (Tier) | 20 pts |
| RPM Market Presence | 15 pts |
| Cap Rate vs. 10Y Treasury | 15 pts |
| Loss-to-Lease Opportunity | 15 pts |
| Vacancy vs. Market Average | 10 pts |
| Asset Vintage | 10 pts |
| Supply Pipeline Risk | 10 pts |
| Asset Scale / G&A Efficiency | 5 pts |

`TREASURY_10Y_REF = 4.30` — proxy rate (Phase 2 will pull live from FRED GS10).
`MARKET_DATA` dict contains 23 markets with tier, rpm_presence (0–100), supply_risk, market_vacancy, rent_growth, rpm_note.

---

### RPM Target Markets

**Tier 1 Core (9):** Austin TX · Dallas-Fort Worth TX · Houston TX · San Antonio TX · Miami FL · Tampa FL · Jacksonville FL · Atlanta GA · Nashville TN

**Tier 2 Growth (9):** Charlotte NC · Raleigh-Durham NC · Columbus OH · Chicago IL · Minneapolis MN · Phoenix AZ · San Diego CA · Las Vegas NV · Charleston SC

**Tier 3 Expansion Watch (4):** Seattle WA · Portland OR · Denver CO · Salt Lake City UT

---

### Phase Roadmap

| Phase | Status | Scope |
|---|---|---|
| Phase 1 | Complete | Scaffold, yfinance fetcher, parquet cache, fundamentals table, market intelligence, deal analyzer, thesis tab |
| Phase 2 | Planned | FRED API integration (GS10, CPI, vacancy, permits), EDGAR ground-truth FFO, σ-based anomaly detection, Plotly chart factory |
| Phase 3 | Planned | MSA heatmap, Census ACS migration fetcher, Nareit/CBRE RSS feed, Tier 3 market modules |
| Phase 4 | Planned | Portfolio screener, PDF export, auth layer |

---

### Known Data Notes

- **NXRT payout_ratio anomaly:** yfinance reports an implausibly high payout ratio (~47x) for NXRT, likely due to near-zero EPS denominator. Phase 2 anomaly detector will flag and suppress.
- **FFO proxy limitation:** yfinance does not provide true FFO (which requires adjusting for gains on sales, straight-line rent, and maintenance capex). The proxy (Net Income + D&A) systematically understates FFO for REITs. All proxy values are labeled `[est.]`.
- **Market data vintage:** All hardcoded market stats (vacancy, rent growth, absorption, pipeline) are as of Q4 2024. Live FRED integration in Phase 2 will update macro series; MSA-level data will remain Q4 2024 until a CoStar/Yardi API is integrated.

---

### Python Environment

- Python 3.9 (macOS system)
- Packages installed to `~/Library/Python/3.9/`
- Run with `python3 -m streamlit run app.py` (not `streamlit run app.py`)
- `pip3 install -r requirements.txt` to add new packages
