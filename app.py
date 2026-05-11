import sys, os
_root = os.path.dirname(os.path.abspath(__file__))
for _p in (_root, os.path.join(_root, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go

from config import (
    RPM_BLACK, RPM_DARK, RPM_GOLD, RPM_GOLD_LT, RPM_LIGHT, RPM_BORDER,
    RPM_MID, RPM_AMBER, RPM_GREEN, RPM_RED, RPM_GREEN_LT, RPM_RED_LT, RPM_AMBER_LT,
)
from fetchers.yfinance_fetcher import fetch_all_fundamentals
from fetchers.rss_fetcher import fetch_news
try:
    from fetchers.rss_fetcher import fetch_ticker_news
except ImportError:
    def fetch_ticker_news(tickers, max_per_ticker=3):  # fallback if module not yet deployed
        return {t: [] for t in tickers}
from processors.fundamentals import build_fundamentals_table
from processors.deal_scorer import score_deal, MARKET_DATA, TREASURY_10Y_REF
from utils.cache import cache_timestamp
from utils.formatters import fmt_large, fmt_pct, fmt_multiple

st.set_page_config(
    page_title="RPM Living Dashboard — Multifamily REIT Intelligence · Jaeden Kinlock",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Social preview / OG image ──────────────────────────────────────────────────
# SVG is base64-encoded and injected as og:image so link previews in Slack,
# iMessage, and LinkedIn show a branded card instead of a blank/error state.
_OG_IMAGE = "https://raw.githubusercontent.com/jaedenkinlock-oss/RPM-Dashboard/main/assets/preview.png"
_OG_TITLE = "RPM Living Dashboard — Multifamily REIT Intelligence"
_OG_DESC  = "225K+ units under management · 21 REIT comparables · 19 Sun Belt target markets · by Jaeden Kinlock"

st.markdown(f"""
<meta property="og:type"        content="website">
<meta property="og:title"       content="{_OG_TITLE}">
<meta property="og:description" content="{_OG_DESC}">
<meta property="og:image"       content="{_OG_IMAGE}">
<meta name="twitter:card"        content="summary_large_image">
<meta name="twitter:title"       content="{_OG_TITLE}">
<meta name="twitter:description" content="{_OG_DESC}">
<meta name="twitter:image"       content="{_OG_IMAGE}">
<script>
(function(){{
  var img = "{_OG_IMAGE}";
  var ttl = "{_OG_TITLE}";
  var dsc = "{_OG_DESC}";
  [
    ['property','og:type',        'website'],
    ['property','og:title',       ttl],
    ['property','og:description', dsc],
    ['property','og:image',       img],
    ['name','twitter:card',        'summary_large_image'],
    ['name','twitter:title',       ttl],
    ['name','twitter:description', dsc],
    ['name','twitter:image',       img],
  ].forEach(function(m){{
    var el = document.createElement('meta');
    el.setAttribute(m[0], m[1]);
    el.setAttribute('content', m[2]);
    document.head.appendChild(el);
  }});
}})();
</script>
""", unsafe_allow_html=True)

# ── CSS ────────────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stSidebarNav"] {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
.stMainBlockContainer {{ padding: 0 !important; max-width: 100% !important; }}
section[data-testid="stMain"] > div {{ padding: 0 !important; }}
.block-container {{ padding: 0 !important; }}

:root {{
  --rpm-black:    {RPM_BLACK};
  --rpm-dark:     {RPM_DARK};
  --rpm-gold:     {RPM_GOLD};
  --rpm-gold-lt:  {RPM_GOLD_LT};
  --rpm-light:    {RPM_LIGHT};
  --rpm-border:   {RPM_BORDER};
  --rpm-mid:      {RPM_MID};
  --rpm-amber:    {RPM_AMBER};
  --rpm-amber-lt: {RPM_AMBER_LT};
  --rpm-green:    {RPM_GREEN};
  --rpm-green-lt: {RPM_GREEN_LT};
  --rpm-red:      {RPM_RED};
  --rpm-red-lt:   {RPM_RED_LT};
}}

/* Header */
.rpm-header {{
  background: var(--rpm-black); padding: 16px 24px;
  display: flex; align-items: center; justify-content: space-between;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.rpm-wordmark {{ font-size: 15px; font-weight: 300; letter-spacing: 0.20em; color: #fff; text-transform: uppercase; }}
.rpm-wordmark strong {{ font-weight: 700; }}
.rpm-tagline {{ font-size: 9px; letter-spacing: 0.14em; color: #888; text-transform: uppercase; margin-top: 3px; }}
.rpm-header-right {{ text-align: right; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }}
.rpm-header-right p {{ font-size: 11px; color: #888; margin: 0 0 2px 0; }}
.rpm-header-right strong {{ color: var(--rpm-gold); }}
.rpm-byline {{ font-size: 9px; color: #555; letter-spacing: 0.06em; font-style: italic; margin-top: 3px; }}

/* Sub-bar */
.rpm-sub {{
  background: var(--rpm-dark); padding: 9px 24px;
  display: flex; gap: 20px; align-items: center;
  border-bottom: 1px solid #333; flex-wrap: wrap;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.rpm-stat-val {{ font-size: 17px; font-weight: 300; color: #fff; line-height: 1.1; }}
.rpm-stat-lbl {{ font-size: 9px; letter-spacing: 0.09em; color: #888; text-transform: uppercase; margin-top: 2px; }}
.rpm-sub-divider {{ width: 1px; height: 28px; background: #444; flex-shrink: 0; }}

/* Tab bar */
.stTabs [data-baseweb="tab-list"] {{
  background: var(--rpm-light) !important;
  border-bottom: 1px solid var(--rpm-border) !important;
  gap: 0 !important; padding: 0 24px !important;
}}
.stTabs [data-baseweb="tab"] {{
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
  font-size: 11px !important; letter-spacing: 0.08em !important;
  text-transform: uppercase !important; padding: 10px 16px !important;
  color: var(--rpm-mid) !important; border-bottom: 2px solid transparent !important;
  background: transparent !important;
}}
.stTabs [aria-selected="true"] {{
  color: var(--rpm-black) !important;
  border-bottom-color: var(--rpm-black) !important;
  font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTabs [data-baseweb="tab-panel"] {{
  padding: 20px 24px !important;
  background: var(--rpm-light) !important;
}}

/* Section label */
.sec-lbl {{
  font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--rpm-mid); font-weight: 600; margin-bottom: 10px;
  padding-bottom: 5px; border-bottom: 1px solid var(--rpm-border);
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}

/* Thesis */
.thesis-pills {{
  background: var(--rpm-black); padding: 12px 16px;
  display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 16px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.t-pills-lbl {{ font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--rpm-gold); font-weight: 600; min-width: 70px; padding-top: 4px; }}
.t-pill {{ font-size: 10px; padding: 3px 9px; border: 1px solid #bbb; color: var(--rpm-black); }}
.t-pill.on {{ border-color: var(--rpm-gold); color: var(--rpm-amber); background: rgba(200,169,110,0.12); }}
.thesis-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
.tc {{ background: #fff; border: 0.5px solid var(--rpm-border); padding: 14px 15px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }}
.tc h4 {{ font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--rpm-gold); font-weight: 600; margin-bottom: 8px; }}
.tc p, .tc li {{ font-size: 12px; color: var(--rpm-mid); line-height: 1.7; margin-bottom: 4px; }}
.tc li strong, .tc p strong {{ color: var(--rpm-black); }}
.tc ul {{ padding-left: 14px; }}

/* Market intelligence */
.mi-header {{
  background: var(--rpm-black); padding: 12px 16px;
  display: flex; align-items: flex-start; justify-content: space-between;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.mi-title {{ font-size: 13px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #fff; }}
.mi-sub {{ font-size: 10px; color: #888; margin-top: 2px; letter-spacing: 0.04em; }}
.mi-data-note {{ font-size: 10px; color: #666; text-align: right; }}
.mi-stats {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px; background: var(--rpm-border); margin-bottom: 1px;
}}
.mi-stat {{ background: var(--rpm-dark); padding: 10px 14px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }}
.mi-stat-val {{ font-size: 18px; font-weight: 300; color: var(--rpm-gold); }}
.mi-stat-val.pos {{ color: #5a9e70; }}
.mi-stat-val.neg {{ color: #c47070; }}
.mi-stat-lbl {{ font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: #888; margin-top: 1px; }}
.mi-stat-src {{ font-size: 9px; color: #555; margin-top: 2px; font-style: italic; }}
.insight-box {{
  background: var(--rpm-gold-lt); border-left: 3px solid var(--rpm-gold);
  padding: 12px 14px; margin-bottom: 1px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.insight-box h5 {{
  font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--rpm-amber); font-weight: 600; margin-bottom: 6px;
}}
.insight-box ul {{ padding-left: 14px; }}
.insight-box li {{ font-size: 12px; color: var(--rpm-black); line-height: 1.75; margin-bottom: 3px; }}
.insight-box li strong {{ color: var(--rpm-black); }}
.src-bar {{
  font-size: 10px; color: var(--rpm-mid); padding-top: 8px;
  border-top: 1px solid var(--rpm-border);
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}

/* Metric cards */
[data-testid="stMetric"] {{
  background: #fff; border: 0.5px solid var(--rpm-border); padding: 14px 18px; border-radius: 0;
}}
[data-testid="stMetricLabel"] {{
  font-size: 9px !important; letter-spacing: 0.1em !important; text-transform: uppercase !important;
  color: var(--rpm-mid) !important; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
}}
[data-testid="stMetricValue"] {{
  font-size: 1.5rem !important; font-weight: 300 !important; color: var(--rpm-black) !important;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
}}

/* Flags — text badges, no emojis */
.badge-red    {{ display:inline-block; background: var(--rpm-red-lt);   color: var(--rpm-red);   font-size:10px; padding:2px 8px; font-weight:600; letter-spacing:0.04em; font-family:'Helvetica Neue',Arial,sans-serif; }}
.badge-yellow {{ display:inline-block; background: var(--rpm-amber-lt); color: var(--rpm-amber); font-size:10px; padding:2px 8px; font-weight:600; letter-spacing:0.04em; font-family:'Helvetica Neue',Arial,sans-serif; }}
.badge-ok     {{ display:inline-block; background: var(--rpm-green-lt); color: var(--rpm-green); font-size:10px; padding:2px 8px; font-weight:600; letter-spacing:0.04em; font-family:'Helvetica Neue',Arial,sans-serif; }}
.badge-na     {{ display:inline-block; background: #eee; color: #999; font-size:10px; padding:2px 8px; font-weight:600; font-family:'Helvetica Neue',Arial,sans-serif; }}

/* REIT detail panel */
.reit-detail {{
  background: #fff; border: 0.5px solid var(--rpm-border); padding: 18px 20px;
  margin-top: 10px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.reit-detail-title {{
  font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--rpm-gold); font-weight: 600; margin-bottom: 12px;
  padding-bottom: 6px; border-bottom: 1px solid var(--rpm-border);
}}
.reit-kv-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }}
.reit-kv {{ background: var(--rpm-light); padding: 10px 12px; }}
.reit-kv-lbl {{ font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--rpm-mid); margin-bottom: 3px; }}
.reit-kv-val {{ font-size: 15px; font-weight: 300; color: var(--rpm-black); }}
.reit-kv-note {{ font-size: 10px; color: var(--rpm-mid); margin-top: 2px; font-style: italic; }}

/* Deal scorer */
.deal-form-card {{
  background: #fff; border: 0.5px solid var(--rpm-border); padding: 18px 20px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.deal-form-title {{
  font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--rpm-black); font-weight: 600; margin-bottom: 14px;
  padding-bottom: 8px; border-bottom: 1px solid var(--rpm-border);
}}
.score-hero {{
  text-align: center; padding: 24px 20px 16px 20px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.score-num {{ font-size: 64px; font-weight: 200; line-height: 1; }}
.score-denom {{ font-size: 18px; color: var(--rpm-mid); font-weight: 300; }}
.score-label {{ font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--rpm-mid); margin-top: 6px; }}
.rec-box {{
  padding: 12px 14px; margin-bottom: 12px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.rec-box.advance  {{ background: var(--rpm-green-lt); border-left: 3px solid var(--rpm-green); }}
.rec-box.conditional {{ background: var(--rpm-gold-lt);  border-left: 3px solid var(--rpm-gold); }}
.rec-box.monitor  {{ background: var(--rpm-amber-lt); border-left: 3px solid var(--rpm-amber); }}
.rec-box.pass-box {{ background: var(--rpm-red-lt);   border-left: 3px solid var(--rpm-red); }}
.rec-box h5 {{
  font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; margin-bottom: 5px;
}}
.rec-box.advance h5  {{ color: var(--rpm-green); }}
.rec-box.conditional h5 {{ color: var(--rpm-amber); }}
.rec-box.monitor h5  {{ color: var(--rpm-amber); }}
.rec-box.pass-box h5 {{ color: var(--rpm-red); }}
.rec-box p {{ font-size: 12px; color: var(--rpm-black); line-height: 1.65; margin: 0; }}
.criterion-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
.criterion-card {{
  background: var(--rpm-light); padding: 10px 12px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.criterion-card.strength {{ border-left: 3px solid var(--rpm-green); }}
.criterion-card.caution  {{ border-left: 3px solid var(--rpm-red); }}
.criterion-card.neutral  {{ border-left: 3px solid var(--rpm-border); }}
.criterion-name {{ font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--rpm-mid); margin-bottom: 3px; }}
.criterion-pts  {{ font-size: 14px; font-weight: 600; color: var(--rpm-black); }}
.criterion-note {{ font-size: 11px; color: var(--rpm-mid); line-height: 1.5; margin-top: 4px; }}
.disclaimer {{
  font-size: 10px; color: var(--rpm-mid); padding: 10px 14px;
  border-top: 1px solid var(--rpm-border); line-height: 1.6;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  background: #fff;
}}

/* Phase placeholder */
.phase-placeholder {{
  background: #fff; border: 0.5px solid var(--rpm-border); padding: 40px 24px; text-align: center;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.phase-placeholder h3 {{ font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--rpm-mid); font-weight: 600; margin-bottom: 10px; }}
.phase-placeholder p {{ font-size: 12px; color: var(--rpm-mid); line-height: 1.7; }}
.phase-placeholder ul {{ font-size: 12px; color: var(--rpm-mid); line-height: 1.9; text-align: left; display: inline-block; padding-left: 16px; }}

/* ── st.pills interactive widget ─────────────────────────────────────────── */
[data-testid="stPills"] {{
  background: var(--rpm-light) !important;
  border: 0.5px solid var(--rpm-border) !important;
  padding: 10px 16px 12px 16px !important;
  margin-bottom: 0 !important;
  gap: 8px !important;
}}
[data-testid="stPills"] > label {{
  font-size: 9px !important; letter-spacing: 0.12em !important;
  text-transform: uppercase !important; font-weight: 600 !important;
  color: var(--rpm-mid) !important;
  font-family: 'Helvetica Neue', Arial, sans-serif !important;
  margin-bottom: 6px !important;
}}
[data-testid="stPills"] button {{
  font-family: 'Helvetica Neue', Arial, sans-serif !important;
  font-size: 10px !important; letter-spacing: 0.06em !important;
  border-radius: 0 !important; border: 1px solid #bbb !important;
  color: var(--rpm-black) !important; background: #fff !important;
  padding: 3px 10px !important;
}}
[data-testid="stPills"] button:hover {{
  border-color: var(--rpm-amber) !important; color: var(--rpm-amber) !important;
  background: var(--rpm-gold-lt) !important;
}}
[data-testid="stPills"] button[kind="pillsActive"] {{
  border-color: var(--rpm-amber) !important;
  color: var(--rpm-amber) !important;
  background: var(--rpm-gold-lt) !important;
}}
/* Pillar detail card */
.pillar-detail {{
  background: #fff; border: 0.5px solid var(--rpm-border);
  border-left: 3px solid var(--rpm-gold);
  padding: 18px 20px; margin-top: 0; margin-bottom: 16px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.pillar-detail h4 {{
  font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--rpm-amber); font-weight: 600; margin-bottom: 10px;
  padding-bottom: 6px; border-bottom: 1px solid var(--rpm-border);
}}
.pillar-detail p {{ color: var(--rpm-black); font-size: 13px; line-height: 1.75; margin-bottom: 10px; }}
.pillar-detail ul {{ padding-left: 16px; margin-top: 0; }}
.pillar-detail li {{ color: var(--rpm-black); font-size: 12.5px; line-height: 1.75; margin-bottom: 4px; }}
.pillar-detail li strong, .pillar-detail p strong {{ color: var(--rpm-black); font-weight: 600; }}
/* News Tracker */
.news-rpm-banner {{
  background: var(--rpm-black); border-left: 4px solid var(--rpm-gold);
  padding: 10px 16px; margin-bottom: 12px;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--rpm-gold); font-weight: 700;
}}
.news-card {{
  border: 0.5px solid var(--rpm-border); padding: 14px 16px;
  margin-bottom: 8px; background: #fff;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
.news-card.rpm-hit {{
  border-left: 3px solid var(--rpm-gold); background: #fffdf6;
}}
.news-card-headline {{
  font-size: 13px; font-weight: 600; color: #111; margin-bottom: 4px;
  line-height: 1.4;
}}
.news-card-headline a {{
  color: #111; text-decoration: none;
}}
.news-card-headline a:hover {{ text-decoration: underline; color: var(--rpm-amber); }}
.news-card-meta {{
  font-size: 10px; color: #888; letter-spacing: 0.06em; margin-bottom: 6px;
}}
.news-card-summary {{
  font-size: 11.5px; color: #444; line-height: 1.55;
}}
.news-badge-rpm {{
  display: inline-block; font-size: 9px; letter-spacing: 0.1em;
  text-transform: uppercase; background: var(--rpm-gold); color: #1A1A1A;
  padding: 2px 7px; font-weight: 700; margin-right: 6px;
}}
.news-badge-src {{
  display: inline-block; font-size: 9px; letter-spacing: 0.08em;
  text-transform: uppercase; background: #eee; color: #555;
  padding: 2px 7px; font-weight: 600; margin-right: 4px;
}}
.news-empty {{
  color: #888; font-size: 12px; padding: 24px 0; text-align: center;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}}
/* ── Force dark text on light tab backgrounds ─────────────────────────────── */
.stTabs [data-baseweb="tab-panel"] {{
  color: {RPM_BLACK} !important;
}}
.stTabs [data-baseweb="tab-panel"] p,
.stTabs [data-baseweb="tab-panel"] label,
.stTabs [data-baseweb="tab-panel"] [data-testid="stWidgetLabel"] p,
.stTabs [data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] p,
.stTabs [data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] li,
.stTabs [data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] strong,
.stTabs [data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] td,
.stTabs [data-baseweb="tab-panel"] [data-testid="stMarkdownContainer"] th {{
  color: {RPM_BLACK} !important;
}}
[data-testid="stForm"] p,
[data-testid="stForm"] label,
[data-testid="stForm"] input,
[data-testid="stForm"] textarea,
[data-testid="stForm"] [data-testid="stWidgetLabel"] p,
[data-testid="stForm"] [data-testid="stMarkdownContainer"] p,
[data-testid="stForm"] [data-testid="stMarkdownContainer"] strong {{
  color: {RPM_BLACK} !important;
}}
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] td,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] th,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] li {{
  color: {RPM_BLACK} !important;
}}
</style>
""", unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────

ts = cache_timestamp("reit_fundamentals") or datetime.now(timezone.utc).strftime("%B %d, %Y")

st.markdown(f"""
<div class="rpm-header">
  <div>
    <div class="rpm-wordmark"><strong>RPM Dashboard</strong>&nbsp;&nbsp;·&nbsp;&nbsp;Jaeden Kinlock</div>
    <div class="rpm-tagline">Vertically Integrated · Multifamily Value-Add · 19 Target Markets</div>
  </div>
  <div class="rpm-header-right">
    <p><strong>225K+</strong> units under management &nbsp;·&nbsp; <strong>90+</strong> full-cycle investments &nbsp;·&nbsp; <strong>800+</strong> investors</p>
    <p>REIT data updated: {ts}</p>
    <div class="rpm-byline">by Jaeden Kinlock</div>
  </div>
</div>
<div class="rpm-sub">
  <div><div class="rpm-stat-val">225K+</div><div class="rpm-stat-lbl">Units AUM</div></div>
  <div class="rpm-sub-divider"></div>
  <div><div class="rpm-stat-val">90+</div><div class="rpm-stat-lbl">Full-cycle investments</div></div>
  <div class="rpm-sub-divider"></div>
  <div><div class="rpm-stat-val">30+</div><div class="rpm-stat-lbl">States</div></div>
  <div class="rpm-sub-divider"></div>
  <div><div class="rpm-stat-val">1,550+</div><div class="rpm-stat-lbl">Units in dev pipeline</div></div>
  <div class="rpm-sub-divider"></div>
  <div><div class="rpm-stat-val">19</div><div class="rpm-stat-lbl">Target MSAs</div></div>
  <div class="rpm-sub-divider"></div>
  <div><div class="rpm-stat-val">Est. 2002</div><div class="rpm-stat-lbl">Austin, TX · NMHC #4 (2025)</div></div>
</div>
""", unsafe_allow_html=True)


# ── Data load ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    raw = fetch_all_fundamentals()
    return build_fundamentals_table(raw)

with st.spinner(""):
    df = load_data()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flag_badge(flag: str) -> str:
    return {
        "red":    '<span class="badge-red">HIGH RISK</span>',
        "yellow": '<span class="badge-yellow">MODERATE</span>',
        "ok":     '<span class="badge-ok">OK</span>',
        "na":     '<span class="badge-na">N/A</span>',
    }.get(flag, '<span class="badge-na">N/A</span>')


def _flag_text(flag: str) -> str:
    return {"red": "HIGH RISK", "yellow": "MODERATE", "ok": "LOW RISK", "na": "N/A"}.get(flag, "N/A")


def render_market_block(title, subtitle, data_note, stats, insights, sources):
    """Render a dark stat grid + amber insight box inside an expander."""
    stats_html = "".join([f"""
      <div class="mi-stat">
        <div class="mi-stat-val {s.get('cls','')}">{s['val']}</div>
        <div class="mi-stat-lbl">{s['label']}</div>
        <div class="mi-stat-src">{s['src']}</div>
      </div>""" for s in stats])

    insights_html = "".join([
        f"<li><strong>{i[0]}</strong> {i[1]}</li>" for i in insights
    ])

    st.markdown(f"""
    <div class="mi-header">
      <div>
        <div class="mi-title">{title}</div>
        <div class="mi-sub">{subtitle}</div>
      </div>
      <div class="mi-data-note">{data_note}</div>
    </div>
    <div class="mi-stats">{stats_html}</div>
    <div class="insight-box">
      <h5>RPM Thesis Signal — Acquisition Intelligence</h5>
      <ul>{insights_html}</ul>
    </div>
    <div class="src-bar">{sources}</div>
    """, unsafe_allow_html=True)


# ── Tabs ───────────────────────────────────────────────────────────────────────

tab_thesis, tab_reits, tab_markets, tab_macro, tab_news, tab_deal = st.tabs([
    "Investment Thesis",
    "REIT Comparables",
    "Market Intelligence",
    "Macro Overlay",
    "News Tracker",
    "Deal Analyzer",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Investment Thesis
# ══════════════════════════════════════════════════════════════════════════════

with tab_thesis:
    PILLAR_DETAIL = {
        "Multifamily Value-Add": """<p>RPM acquires apartment communities where current rents are priced below what today's market will support. When a unit turns over, RPM renovates it and re-leases at market rate — turning a gap that already exists into realized income.</p>
<ul>
  <li><strong>The opportunity:</strong> Rents in target Sun Belt markets are currently running 8–12% below comparable asking rents nearby</li>
  <li><strong>The return:</strong> A roughly $10,000 renovation per unit typically yields an extra $150–250 in monthly rent — a 15–25% return on that capital spend</li>
  <li><strong>The edge:</strong> RPM's in-house management team has historically closed occupancy gaps within 90 days of taking over a property</li>
</ul>""",

        "Sun Belt Migration": """<p>Millions of households are relocating from coastal markets to Sun Belt cities in search of lower costs, warmer weather, and job opportunities. That population shift is the most consistent long-term driver of apartment demand in the markets where RPM operates.</p>
<ul>
  <li><strong>The scale:</strong> Texas adds roughly 470,000 net in-migrants per year; Florida adds 320,000; the Southeast corridor adds another 150,000+</li>
  <li><strong>Who is moving:</strong> Primarily millennials aged 28–43 — the generation currently at peak household formation — attracted by Sun Belt housing costs that run 40–60% below coastal equivalents</li>
  <li><strong>RPM's view:</strong> This is a structural shift, not a cycle — the cost gap that drives it has widened, not narrowed, since 2020</li>
</ul>""",

        "Supply / Demand Imbalance": """<p>New apartment construction surged in 2021–22 and created short-term oversupply in several Sun Belt markets. That wave is now passing — starts have fallen sharply while renter demand has stayed firm. The window to buy at trough pricing is open now.</p>
<ul>
  <li><strong>Supply side:</strong> New construction starts are down 40–60% from the 2022 peak as financing costs and land prices make new projects difficult to underwrite</li>
  <li><strong>Demand side:</strong> Homeownership affordability is near multi-decade lows, keeping more households renting longer than they otherwise would</li>
  <li><strong>The trade:</strong> Net new deliveries across Tier 1 markets are projected to fall below absorption by 2026–27 — acquisitions made today benefit from the recovery</li>
</ul>""",

        "Vertically Integrated Platform": """<p>RPM operates investments, property management, and development as a single connected platform. Each division generates deal flow and real-time data for the others — an advantage that a standalone operator or a fee-only manager simply cannot replicate.</p>
<ul>
  <li><strong>Scale:</strong> Ranked #4 nationally by NMHC with 225,000+ units managed across 30+ states — generating proprietary occupancy and rent data before it reaches CoStar or Yardi</li>
  <li><strong>Track record:</strong> 90+ full-cycle investment transactions completed across multiple market cycles since 2002</li>
  <li><strong>Development edge:</strong> In-house construction eliminates the general contractor margin and reduces cost basis by 10–15% compared to third-party delivery</li>
</ul>""",

        "Loss-to-Lease Capture": """<p>Loss-to-lease is the difference between what a current tenant pays and what a new lease in the same unit would command today. That gap is contractual rent upside — it materializes automatically as units turn, with no reliance on market rent growth.</p>
<ul>
  <li><strong>Current spreads:</strong> Austin rents are running 5–8% below market; Nashville and Dallas are 7–10% below (Yardi Matrix, Q1 2026)</li>
  <li><strong>What it means in dollars:</strong> A 300-unit property with 12% loss-to-lease at normal turnover generates an estimated $400,000+ in incremental annual income as leases reset</li>
  <li><strong>Execution advantage:</strong> RPM's in-house leasing teams re-lease vacated units 30–60 days faster than properties managed by third parties</li>
</ul>""",

        "BTR Development": """<p>Build-to-rent (BTR) communities are purpose-built rental homes — single-family houses and townhomes designed from the ground up for renters. RPM develops these to serve family-forming households who want more space and privacy than a traditional apartment but prefer renting over buying.</p>
<ul>
  <li><strong>Cost advantage:</strong> Removing the general contractor margin (8–12%) and purchasing at scale reduces the development cost basis by roughly 10–15% compared to a third-party-delivered project of the same size</li>
  <li><strong>Active pipeline:</strong> 1,550+ units currently in development across Texas, Florida, and the Southeast</li>
  <li><strong>Who rents them:</strong> Primarily millennial households with children — renters who want house-like amenities and neighborhood feel without the commitment of a mortgage</li>
</ul>""",

        "NOI Through Operations": """<p>Better property management creates income growth independent of what happens to market rents. RPM's in-house platform improves occupancy, adds ancillary revenue streams, and reduces operating costs — increasing net operating income from the moment it takes over a property.</p>
<ul>
  <li><strong>Occupancy lift:</strong> Management conversions have historically improved occupancy by 1.5–3 percentage points within the first 12 months</li>
  <li><strong>Ancillary income:</strong> Pet fees, reserved parking, utility recovery programs, and package services typically add $40–75 per unit per month in income that was previously uncaptured</li>
  <li><strong>Expense savings:</strong> Purchasing power across 225,000+ units drives operating cost reductions of 8–12% compared to single-asset operators</li>
</ul>""",

        "Institutional Capital": """<p>RPM's investor network — 800+ relationships spanning institutions, family offices, and high-net-worth individuals — is a competitive advantage in acquisitions. Pre-committed capital means RPM can close faster than nearly any competitor, which matters in deals where sellers prioritize certainty over price.</p>
<ul>
  <li><strong>Speed:</strong> RPM can close in 30–45 days; operators who market each deal fresh typically need 60–90 days</li>
  <li><strong>Flexibility:</strong> Capital can be deployed across programmatic joint ventures, deal-by-deal JVs, fund vehicles, preferred equity, and development partnerships — matched to each deal's risk profile</li>
  <li><strong>Track record:</strong> 20+ years of investment history across the 2008 financial crisis, the COVID disruption, and the current interest rate cycle</li>
</ul>""",
    }

    selected_pillar = st.pills(
        "Thesis Pillars — Select to expand",
        list(PILLAR_DETAIL.keys()),
        selection_mode="single",
        default=None,
    )

    if selected_pillar:
        st.markdown(
            f'<div class="pillar-detail"><h4>{selected_pillar}</h4>{PILLAR_DETAIL[selected_pillar]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("""
    <div class="sec-lbl">Investment Thesis — rpmliving.com/business-services/investments · NMHC rankings · public statements</div>
    <div class="thesis-grid">
      <div class="tc">
        <h4>Investment Mandate</h4>
        <ul>
          <li><strong>Platform:</strong> Top 5 vertically integrated multifamily operator — 225K+ units, 30+ states (NMHC #4, 2025)</li>
          <li><strong>Three divisions:</strong> Investments · Property Management · Development — each feeds deal flow and data to the others</li>
          <li><strong>Edge:</strong> Real-time rent, vacancy, and traffic data across 225K+ managed units — before CoStar or Yardi</li>
        </ul>
      </div>
      <div class="tc">
        <h4>Strategy — Ranked by Preference</h4>
        <ul>
          <li><strong>1. Value-add acquisition</strong> — below-market rents, renovation on turn, mark-to-market through managed unit turn program</li>
          <li><strong>2. Repositioning</strong> — management conversion, amenity upgrades, institutional rebranding</li>
          <li><strong>3. BTR / ground-up</strong> — controlled cost basis; 1,550+ units in pipeline</li>
          <li><strong>4. Distressed / special situations</strong> — post-supply-wave trough at below-replacement-cost entry</li>
        </ul>
      </div>
      <div class="tc">
        <h4>Target Markets by Tier</h4>
        <ul>
          <li><strong>Tier 1 — Core (9):</strong> Austin · San Antonio · Houston · Dallas · Miami · Tampa · Jacksonville · Atlanta · Nashville</li>
          <li><strong>Tier 2 — Growth (9):</strong> Charlotte · Raleigh-Durham · Columbus · Chicago · Minneapolis · Phoenix · San Diego · Las Vegas · Charleston</li>
          <li><strong>Tier 3 — Watch (4):</strong> Seattle · Portland · Denver · Salt Lake City</li>
          <li>Selection driven by net migration rate + job growth/supply ratio + RPM operational presence</li>
        </ul>
      </div>
      <div class="tc">
        <h4>Acquisition Criteria</h4>
        <ul>
          <li><strong>Loss-to-lease &gt; 8%</strong> — contractual rent growth runway on unit turn</li>
          <li><strong>Vintage: 1990–2015</strong> — repositionable, below replacement cost</li>
          <li><strong>Occupancy: 80–93%</strong> — income to carry capex; vacancy recovers via management conversion</li>
          <li><strong>Units: 150–500</strong> — optimal G&amp;A efficiency</li>
          <li><strong>Capital stack:</strong> 60–70% LTV; institutional JV or fund equity; 5–7 year hold</li>
        </ul>
      </div>
      <div class="tc">
        <h4>Platform Edge</h4>
        <ul>
          <li><strong>Data flywheel:</strong> 225K+ units = real-time signals before external data providers</li>
          <li><strong>Leasing velocity:</strong> In-house management converts acquisitions faster — critical when carrying renovation costs</li>
          <li><strong>Capital relationships:</strong> 800+ investors; flexible equity structures across the risk spectrum</li>
          <li><strong>Development:</strong> In-house construction reduces cost basis 10–15% vs. third-party delivery</li>
          <li><strong>Track record:</strong> 90+ full-cycle investments; 20+ years across multiple market cycles</li>
        </ul>
      </div>
      <div class="tc">
        <h4>Active Thesis — 2025–26</h4>
        <ul>
          <li><strong>Supply absorption window:</strong> 2026–27 deliveries fall below absorption in all Tier 1 — acquire at trough, hold through recovery</li>
          <li><strong>Loss-to-lease at decade-wide spreads:</strong> Dallas, Nashville, Austin B-class at −8% to −12% below asking — NOI upside is contractual</li>
          <li><strong>Rate trajectory:</strong> Each 25bps cut adds ~$800K on a $50M asset at 5× leverage; cap rate spread tightening toward real assets</li>
          <li><strong>Florida resilience:</strong> Miami and Tampa vacancy tightest in Sun Belt — international demand and lifestyle migration are structural</li>
        </ul>
      </div>
    </div>
    <div class="src-bar">Sources: rpmliving.com/business-services/investments &nbsp;&middot;&nbsp; NMHC Top 50 Managers 2025 (#4) &nbsp;&middot;&nbsp; MHN Property Management Company of the Year 2025 &nbsp;&middot;&nbsp; RPM Living press releases 2021–2025</div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — REIT Comparables
# ══════════════════════════════════════════════════════════════════════════════

with tab_reits:
    if df.empty:
        st.warning("REIT data unavailable — yfinance fetch failed. Data will refresh automatically on next load.")
    else:

        mf = df[df["category"] == "Multifamily"]

        st.markdown(
            '<div class="sec-lbl">REIT universe &nbsp;&middot;&nbsp; multifamily · SFR · homebuilders &nbsp;&middot;&nbsp; live yfinance data</div>',
            unsafe_allow_html=True,
        )

        # ── Hero stat strip ───────────────────────────────────────────────────────
        _mf_n    = len(mf)
        _mf_mc   = mf["market_cap"].sum()
        _mf_dy   = mf["div_yield"].mean()
        _mf_pffo = mf["p_ffo"].median()
        _mf_ndeb = mf["net_debt_ebitda"].median()
        _mf_hr   = int((df["payout_flag"] == "red").sum())
        _mf_mod  = int((df["payout_flag"] == "yellow").sum())

        st.markdown(f"""
        <div class="mi-stats" style="margin-bottom:16px;">
          <div class="mi-stat">
            <div class="mi-stat-val">{_mf_n}</div>
            <div class="mi-stat-lbl">Multifamily REITs</div>
            <div class="mi-stat-src">Universe</div>
          </div>
          <div class="mi-stat">
            <div class="mi-stat-val">{fmt_large(_mf_mc)}</div>
            <div class="mi-stat-lbl">Combined Market Cap</div>
            <div class="mi-stat-src">Multifamily only</div>
          </div>
          <div class="mi-stat">
            <div class="mi-stat-val" style="color:var(--rpm-gold);">{fmt_pct(_mf_dy) if _mf_dy == _mf_dy else '—'}</div>
            <div class="mi-stat-lbl">Avg Dividend Yield</div>
            <div class="mi-stat-src">Multifamily average</div>
          </div>
          <div class="mi-stat">
            <div class="mi-stat-val" style="color:var(--rpm-gold);">{fmt_multiple(_mf_pffo) if _mf_pffo == _mf_pffo else '—'}</div>
            <div class="mi-stat-lbl">Median P / FFO [est.]</div>
            <div class="mi-stat-src">Net Income + D&amp;A proxy</div>
          </div>
          <div class="mi-stat">
            <div class="mi-stat-val" style="color:var(--rpm-gold);">{f'{_mf_ndeb:.1f}x' if _mf_ndeb == _mf_ndeb else '—'}</div>
            <div class="mi-stat-lbl">Median ND / EBITDA</div>
            <div class="mi-stat-src">Leverage — multifamily</div>
          </div>
          <div class="mi-stat">
            <div class="mi-stat-val {'neg' if _mf_hr > 0 else ''}" style="font-size:18px;font-weight:300;">
              {_mf_hr} High · {_mf_mod} Mod
            </div>
            <div class="mi-stat-lbl">Payout Risk Flags</div>
            <div class="mi-stat-src">Full universe</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Filters — pill bars ───────────────────────────────────────────────────
        _all_cats = sorted(df["category"].unique().tolist())
        _cat_sel = st.pills(
            "Category",
            _all_cats,
            selection_mode="multi",
            default=["Multifamily", "SFR/BTR"],
            key="reit_cats",
        )

        _RISK_OPTS  = ["Low Risk", "Moderate", "High Risk", "N/A"]
        _RISK_MAP   = {"Low Risk": "ok", "Moderate": "yellow", "High Risk": "red", "N/A": "na"}
        _risk_sel = st.pills(
            "Payout Risk",
            _RISK_OPTS,
            selection_mode="multi",
            default=_RISK_OPTS,
            key="reit_risk",
        )

        # Sort + ticker row
        _SORT_MAP = {
            "Market Cap":        "market_cap",
            "Dividend Yield":    "div_yield",
            "P/FFO [est.]":      "p_ffo",
            "Payout Ratio":      "payout_ratio",
            "Net Debt / EBITDA": "net_debt_ebitda",
        }
        _sf1, _sf2 = st.columns([1, 2])
        with _sf1:
            _sort_label = st.selectbox("Sort By", list(_SORT_MAP.keys()), key="reit_sort")
        with _sf2:
            _tick_sel = st.selectbox(
                "Ticker detail",
                options=["— select ticker —"] + sorted(df.index.tolist()),
                key="reit_ticker",
            )

        # ── Apply filters ─────────────────────────────────────────────────────────
        _cats_active = _cat_sel if _cat_sel else _all_cats
        _risk_active = [_RISK_MAP[l] for l in (_risk_sel if _risk_sel else _RISK_OPTS)]
        _sort_col    = _SORT_MAP[_sort_label]

        filtered = df[df["category"].isin(_cats_active) & df["payout_flag"].isin(_risk_active)]
        if _sort_col in filtered.columns:
            filtered = filtered.sort_values(_sort_col, ascending=False)

        st.markdown(
            f'<div class="sec-lbl" style="margin-top:4px;">{len(filtered)} tickers shown &nbsp;&middot;&nbsp; '
            'FFO [est.] = Net Income TTM + D&amp;A TTM &nbsp;&middot;&nbsp; EDGAR ground truth: Phase 2</div>',
            unsafe_allow_html=True,
        )

        # ── Data table ────────────────────────────────────────────────────────────
        display = pd.DataFrame({
            "Company":       filtered["name"],
            "Category":      filtered["category"],
            "Price":         filtered["price"].map(lambda x: f"${x:.2f}" if x == x else "—"),
            "Market Cap":    filtered["market_cap"].map(fmt_large),
            "Div Yield":     filtered["div_yield"].map(lambda x: fmt_pct(x) if x == x else "—"),
            "Annual Div":    filtered["div_rate"].map(lambda x: f"${x:.2f}" if x == x else "—"),
            "Payout Ratio":  filtered["payout_ratio"].map(lambda x: fmt_pct(x) if x == x else "—"),
            "Payout Risk":   filtered["payout_flag"].map(_flag_text),
            "FFO/Sh [est.]": filtered["ffo_per_share"].map(lambda x: f"${x:.2f}" if x == x else "—"),
            "P/FFO [est.]":  filtered["p_ffo"].map(lambda x: fmt_multiple(x) if x == x else "—"),
            "ND/EBITDA":     filtered["net_debt_ebitda"].map(lambda x: f"{x:.1f}x" if x == x else "—"),
            "Lev Risk":      filtered["leverage_flag"].map(_flag_text),
            "52W High":      filtered["week52_high"].map(lambda x: f"${x:.2f}" if x == x else "—"),
            "vs 52W High":   filtered["pct_from_52w_high"].map(lambda x: fmt_pct(x) if x == x else "—"),
        }, index=filtered.index)

        st.dataframe(display, use_container_width=True, height=440)

        st.markdown(
            f'<div class="src-bar">Source: yfinance &nbsp;&middot;&nbsp; {ts} &nbsp;&middot;&nbsp; '
            'Moderate = payout &gt;90% &nbsp;&middot;&nbsp; High Risk = payout &gt;100% &nbsp;&middot;&nbsp; '
            'Leverage moderate = ND/EBITDA &gt;7x &nbsp;&middot;&nbsp; High Risk = &gt;9x</div>',
            unsafe_allow_html=True,
        )

        # ── Methodology note ──────────────────────────────────────────────────────
        st.markdown("""
        <div class="insight-box" style="margin-top:10px;">
          <h5>Methodology</h5>
          <ul>
            <li><strong>P/FFO [est.]</strong> — Price / (Net Income TTM + D&amp;A TTM). True FFO requires EDGAR 10-K/10-Q adjustment for gains on sales and straight-line rent. EDGAR integration in Phase 2.</li>
            <li><strong>Payout ratio</strong> — Annual dividends / Earnings (yfinance <code>payoutRatio</code>). Approximates AFFO payout. Moderate = &gt;90%, High Risk = &gt;100%.</li>
            <li><strong>ND/EBITDA</strong> — (Total Debt − Cash) / EBITDA. Moderate = &gt;7x, High Risk = &gt;9x.</li>
            <li><strong>Dividend yield</strong> — Annual dividend rate / current price (trailing).</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

        # ── Ticker detail panel ───────────────────────────────────────────────────
        if _tick_sel != "— select ticker —" and _tick_sel in df.index:
            row = df.loc[_tick_sel]
            cat = row.get("category", "—")

            def _v(x, fmt=None):
                if x is None or (isinstance(x, float) and x != x): return "—"
                return fmt(x) if fmt else str(x)

            pb = row.get("payout_flag", "na")
            lb = row.get("leverage_flag", "na")

            st.markdown(f"""
            <div class="reit-detail">
              <div class="reit-detail-title">{_tick_sel} — {row.get('name','—')} &nbsp;&middot;&nbsp; {cat}</div>
              <div class="reit-kv-grid">
                <div class="reit-kv"><div class="reit-kv-lbl">Current Price</div><div class="reit-kv-val">{_v(row.get('price'), lambda x: f'${x:.2f}')}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Market Cap</div><div class="reit-kv-val">{_v(row.get('market_cap'), fmt_large)}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Dividend Yield</div><div class="reit-kv-val">{_v(row.get('div_yield'), fmt_pct)}</div><div class="reit-kv-note">Annual: {_v(row.get('div_rate'), lambda x: f'${x:.2f}')}/sh</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Payout Ratio</div><div class="reit-kv-val">{_v(row.get('payout_ratio'), fmt_pct)}</div><div class="reit-kv-note">{_flag_badge(pb)}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">FFO / Share [est.]</div><div class="reit-kv-val">{_v(row.get('ffo_per_share'), lambda x: f'${x:.2f}')}</div><div class="reit-kv-note">Net Income + D&amp;A proxy</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">P / FFO [est.]</div><div class="reit-kv-val">{_v(row.get('p_ffo'), fmt_multiple)}</div><div class="reit-kv-note">EDGAR ground truth: Phase 2</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Forward EPS</div><div class="reit-kv-val">{_v(row.get('forward_eps'), lambda x: f'${x:.2f}')}</div><div class="reit-kv-note">Fwd P/E: {_v(row.get('forward_pe'), lambda x: f'{x:.1f}x')}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Net Debt / EBITDA</div><div class="reit-kv-val">{_v(row.get('net_debt_ebitda'), lambda x: f'{x:.1f}x')}</div><div class="reit-kv-note">{_flag_badge(lb)}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">Revenue (TTM)</div><div class="reit-kv-val">{_v(row.get('revenue_ttm'), fmt_large)}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">EBITDA (TTM)</div><div class="reit-kv-val">{_v(row.get('ebitda'), fmt_large)}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">52-Week High</div><div class="reit-kv-val">{_v(row.get('week52_high'), lambda x: f'${x:.2f}')}</div></div>
                <div class="reit-kv"><div class="reit-kv-lbl">52-Week Low</div><div class="reit-kv-val">{_v(row.get('week52_low'), lambda x: f'${x:.2f}')}</div></div>
              </div>
            </div>
            <div class="src-bar" style="margin-top:6px;">Source: yfinance &nbsp;&middot;&nbsp; {ts} &nbsp;&middot;&nbsp; FFO [est.] = Net Income TTM + D&amp;A TTM &nbsp;&middot;&nbsp; EDGAR 10-K/10-Q FFO in Phase 2.</div>
            """, unsafe_allow_html=True)

            # ── RSS quote verification ─────────────────────────────────────────────
            with st.spinner(""):
                _ticker_news = fetch_ticker_news([_tick_sel], max_per_ticker=4)
            _tn = _ticker_news.get(_tick_sel, [])

            if _tn:
                _now = datetime.now(timezone.utc).replace(tzinfo=None)
                _most_recent = _tn[0]["date"].replace(tzinfo=None) if _tn[0]["date"].tzinfo else _tn[0]["date"]
                _age_hours = (_now - _most_recent).total_seconds() / 3600
                _freshness = (
                    "Live — within 6 hours" if _age_hours < 6 else
                    "Recent — within 24 hours" if _age_hours < 24 else
                    f"Last coverage {int(_age_hours / 24)}d ago"
                )
                _fresh_color = "#5a9e70" if _age_hours < 24 else "#999"
                headlines_html = "".join([
                    f'<div style="padding:7px 0;border-bottom:1px solid #f0ede7;">'
                    f'<a href="{a["link"]}" target="_blank" style="font-size:12px;color:#111;text-decoration:none;line-height:1.45;">'
                    f'{a["title"]}</a>'
                    f'<span style="font-size:10px;color:#999;margin-left:8px;">'
                    f'{a["date"].strftime("%b %d") if a["date"] else ""}</span>'
                    f'</div>'
                    for a in _tn
                ])
                st.markdown(f"""
                <div style="background:#fff;border:0.5px solid #ddd;border-left:3px solid {_fresh_color};
                     padding:12px 16px;margin-top:6px;
                     font-family:'Helvetica Neue',Arial,sans-serif;">
                  <div style="font-size:9px;letter-spacing:0.12em;text-transform:uppercase;
                       font-weight:600;color:{_fresh_color};margin-bottom:8px;">
                    Yahoo Finance — {_tick_sel} Recent Coverage &nbsp;·&nbsp; {_freshness}
                  </div>
                  {headlines_html}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div style="font-size:11px;color:#999;padding:8px 0;">'
                    f'No recent RSS headlines found for {_tick_sel} — price data sourced from yfinance ({ts}).</div>',
                    unsafe_allow_html=True,
                )

        with st.expander("Raw data — all columns"):
            st.dataframe(filtered, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 3 — Market Intelligence
    # ══════════════════════════════════════════════════════════════════════════════

with tab_markets:
    st.markdown('<div class="sec-lbl">RPM Living target markets &nbsp;&middot;&nbsp; multifamily fundamentals &nbsp;&middot;&nbsp; data as of Q1 2026 &nbsp;&middot;&nbsp; live FRED integration Phase 2</div>', unsafe_allow_html=True)

    # ── Market coordinates for Plotly map ──────────────────────────────────────
    _MARKET_COORDS = {
        "Austin, TX":              (30.27, -97.74, 1),
        "Dallas – Fort Worth, TX": (32.78, -97.00, 1),
        "Houston, TX":             (29.76, -95.37, 1),
        "San Antonio, TX":         (29.42, -98.49, 1),
        "Miami, FL":               (25.76, -80.19, 1),
        "Tampa, FL":               (27.95, -82.46, 1),
        "Jacksonville, FL":        (30.33, -81.66, 1),
        "Atlanta, GA":             (33.75, -84.39, 1),
        "Nashville, TN":           (36.16, -86.78, 1),
        "Charlotte, NC":           (35.23, -80.84, 2),
        "Raleigh-Durham, NC":      (35.78, -78.64, 2),
        "Columbus, OH":            (39.96, -82.99, 2),
        "Chicago, IL":             (41.88, -87.63, 2),
        "Minneapolis, MN":         (44.98, -93.27, 2),
        "Phoenix, AZ":             (33.45, -112.07, 2),
        "San Diego, CA":           (32.72, -117.16, 2),
        "Las Vegas, NV":           (36.17, -115.14, 2),
        "Charleston, SC":          (32.78, -79.93, 2),
        "Seattle, WA":             (47.61, -122.33, 3),
        "Portland, OR":            (45.51, -122.68, 3),
        "Denver, CO":              (39.74, -104.99, 3),
        "Salt Lake City, UT":      (40.76, -111.89, 3),
    }
    _T3_DATA = {
        "Seattle, WA":        "Amazon and Microsoft HQ market; highest median income in RPM universe; 30/100 presence; infrastructure investment required before acquisition.",
        "Portland, OR":       "Tech-adjacent; elevated policy and rent control risk; monitoring for entry timing window.",
        "Denver, CO":         "Healthcare, aerospace, and outdoor economy; 5.5M+ metro; strong lifestyle migration; 30/100 presence.",
        "Salt Lake City, UT": "Fastest-growing tech ecosystem outside major coastal hubs; 25/100 presence; family formation dynamics differ from Sun Belt thesis.",
    }
    _T3_NAMES = list(_T3_DATA.keys())

    # ── Market data registry (single source of truth for both lookup + expanders) ──
    T1_MARKETS = [
        {
            "name": "Austin, TX",
            "expander": "Austin, TX  —  Tier 1 Core  ·  7.2% Vacancy  ·  +0.8% Rent Growth YOY",
            "subtitle": "Value-Add · Supply Peak Passing · Tech Employment Anchor · RPM Headquarters Market",
            "stats": [
                {"val": "7.2%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — improving as peak supply absorbed", "cls": "neg"},
                {"val": "$1,695", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+0.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — recovery underway as pipeline clears", "cls": "pos"},
                {"val": "10,800", "label": "Units Under Construction",  "src": "CoStar Q1 2026 — pipeline dropped 54% from 2024 peak"},
                {"val": "+2.6%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Tesla, Samsung, Apple, Oracle", "cls": "pos"},
                {"val": "+24K",   "label": "Net In-Migration / Yr",     "src": "Census ACS 2024 — among highest nationally"},
                {"val": "15,500", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Pipeline cleared; recovery confirmed:", "2023–25 deliveries have been substantially absorbed; new starts collapsed 60%+ — vacancy down from 8.5% peak to 7.2% with positive rent growth (+0.8%) confirmed in Q1 2026."),
                ("B-class renovation thesis strongest in Texas:", "2010–2018 vintage communities at −8% to −12% LTL gap; $8K–$12K/unit renovation bridges 70–80% of the spread with 15–25% ROI."),
            ],
            "sources": "Yardi Matrix Q1 2026 · RealPage Analytics Q1 2026 · CoStar Austin Multifamily Q1 2026 · BLS Texas Metro Employment Q1 2026 · Census ACS 2024",
        },
        {
            "name": "Dallas – Fort Worth, TX",
            "expander": "Dallas – Fort Worth, TX  —  Tier 1 Core  ·  8.2% Vacancy  ·  −2.5% Rent Growth YOY",
            "subtitle": "Largest Multifamily Pipeline Nationally · Finance and Tech Relocation · Highest Net Absorption Volume",
            "stats": [
                {"val": "7.0%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — vacancy declined from 8.2% peak", "cls": "neg"},
                {"val": "$1,548", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+0.6%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — first positive print since 2022", "cls": "pos"},
                {"val": "17,200", "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 48% from 2024 peak; pipeline normalizing"},
                {"val": "+2.8%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — #2 nationally by job adds", "cls": "pos"},
                {"val": "8.0M",   "label": "Metro Employment Base",     "src": "BLS Q1 2026 — 2nd largest in Texas"},
                {"val": "23,000", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Largest pipeline, largest demand base:", "DFW leads nationally in net absorption (35K+ units/yr) — the supply pipeline is large but the absorption engine is deeper; ratio supports trough entry."),
                ("Finance relocation validates the demand ceiling:", "Goldman Sachs, JPMorgan, Charles Schwab, PGA HQ — suburban garden-style (Frisco, McKinney, Plano) offers 5.5–6.0% caps with 8–10% LTL and less institutional competition than Uptown."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar DFW Multifamily Q1 2026 · BLS Dallas–Plano–Irving Metro Q1 2026 · RealPage Analytics Q1 2026",
        },
        {
            "name": "Houston, TX",
            "expander": "Houston, TX  —  Tier 1 Core  ·  6.8% Vacancy  ·  +0.5% Rent Growth YOY",
            "subtitle": "Diversified Economy · Texas Medical Center Anchor · Strongest NOI Margins in the Texas Portfolio",
            "stats": [
                {"val": "6.8%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — below Texas average; tightening"},
                {"val": "$1,385", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — most affordable major TX market"},
                {"val": "+0.5%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — positive first; mildest recovery lag of TX markets", "cls": "pos"},
                {"val": "9,200",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 54% from 2024 peak"},
                {"val": "+2.5%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — energy, Texas Medical Center, LNG export led", "cls": "pos"},
                {"val": "60K+",   "label": "TMC Employees",             "src": "Texas Medical Center — world's largest medical district"},
                {"val": "22,000", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Best NOI margin in Texas:", "Lowest entry rents + lowest land/construction costs = highest NOI margin on acquisition; diversified economy (energy, TMC, Port of Houston) is the most recession-resistant Texas demand base."),
                ("Workforce housing underserved by institutional capital:", "Southeast corridor (Pasadena, Deer Park) drives workforce demand; TMC3 adds 30K+ jobs by 2030 — less competition for acquisitions than Austin or DFW."),
            ],
            "sources": "Yardi Matrix Q1 2026 · Texas Medical Center 2025 Annual Report · CoStar Houston Q1 2026 · BLS Houston–The Woodlands Metro Q1 2026",
        },
        {
            "name": "San Antonio, TX",
            "expander": "San Antonio, TX  —  Tier 1 Core  ·  8.0% Vacancy  ·  −1.5% Rent Growth YOY",
            "subtitle": "Military Demand Floor · Deepest Value-Add Discount in Texas · Lowest Entry Basis",
            "stats": [
                {"val": "8.0%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — improving; peak supply absorbed", "cls": "neg"},
                {"val": "$1,270", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — lowest in Texas"},
                {"val": "−1.5%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — declining; recovery expected 2026–27", "cls": "neg"},
                {"val": "5,000",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — pipeline dropped 58% from 2024 peak"},
                {"val": "250K+",  "label": "DOD-Related Employees",     "src": "JBSA — largest military installation nationally by personnel"},
                {"val": "+2.2%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Toyota, cybersecurity, JBSA", "cls": "pos"},
                {"val": "8,500",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Deepest cyclical discount in Texas:", "Highest vacancy + steepest rent decline creates the widest trough acquisition window — lowest entry basis in RPM's Texas portfolio; value-add rent bumps achievable relative to market rents."),
                ("Military demand floor is recession-proof:", "Joint Base San Antonio (250K+ DOD-related personnel) sets a structural vacancy floor regardless of economic cycles; target 2009–2016 vintage within 10 miles of JBSA."),
            ],
            "sources": "Yardi Matrix Q1 2026 · JBSA Economic Impact Study 2025 · CoStar San Antonio Q1 2026 · BLS San Antonio–New Braunfels Metro Q1 2026",
        },
        {
            "name": "Miami, FL",
            "expander": "Miami, FL  —  Tier 1 Core  ·  6.2% Vacancy  ·  +3.0% Rent Growth YOY",
            "subtitle": "Tightest Market in RPM Universe · International Demand Floor · Finance and Tech Migration",
            "stats": [
                {"val": "6.2%",    "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — slight uptick from new luxury deliveries; still tight"},
                {"val": "$2,910",  "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — 2nd highest in RPM universe"},
                {"val": "+3.0%",   "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — strongest sustained growth in RPM Tier 1", "cls": "pos"},
                {"val": "7,800",   "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 46%; luxury high-rise dominant"},
                {"val": "+2.1%",   "label": "Job Growth YOY",            "src": "BLS Q1 2026 — finance and tech relocation", "cls": "pos"},
                {"val": "Brickell","label": "Finance Hub",               "src": "Citadel, Apollo, Point72, Blackstone, Goldman Sachs expansions"},
                {"val": "9,500",   "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("International demand floors the market:", "Latin American capital flight and foreign national rentership suppress vacancy well below other Sun Belt markets — structural and uncorrelated with domestic economic cycles."),
                ("New supply is luxury high-rise; RPM's target is B-class workforce:", "B-class garden-style vacancy in Doral, Hialeah, and Kendall runs 3–4%; target 1995–2010 vintage — structurally undersupplied and insulated from luxury competition."),
            ],
            "sources": "Yardi Matrix Q1 2026 · RealPage Analytics Q1 2026 · CoStar Miami Multifamily Q1 2026 · BLS Miami–Fort Lauderdale–Pompano Beach Metro Q1 2026",
        },
        {
            "name": "Tampa, FL",
            "expander": "Tampa, FL  —  Tier 1 Core  ·  6.0% Vacancy  ·  +1.8% Rent Growth YOY",
            "subtitle": "Best-Positioned Florida Market · Finance and Insurance Diversification · Earliest Rent Recovery Signal",
            "stats": [
                {"val": "6.0%",        "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — tightening as supply pipeline thins"},
                {"val": "$1,940",      "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+1.8%",       "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — accelerating as vacancy tightens", "cls": "pos"},
                {"val": "4,500",       "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 56%; thinnest Florida pipeline"},
                {"val": "+2.0%",       "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Raymond James, Cetera, JP Morgan expansion", "cls": "pos"},
                {"val": "PortTampa Bay","label": "FL's Largest Port",        "src": "PortTampa Bay Master Plan 2025 — expansion underway"},
                {"val": "9,000",       "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Best risk/reward in Florida:", "Thinner supply pipeline + positive rent growth already returning + diversified employment (Raymond James, Cetera) = earliest recovery signal — strongest Florida entry point."),
                ("Port expansion creates east corridor demand:", "PortTampa Bay 2025 expansion adds logistics employment in Brandon and Riverview — workforce housing submarkets where RPM acquires at significant discounts to Tampa proper."),
            ],
            "sources": "Yardi Matrix Q1 2026 · RealPage Analytics Q1 2026 · CoStar Tampa Multifamily Q1 2026 · BLS Tampa–St. Pete Metro Q1 2026 · PortTampa Bay",
        },
        {
            "name": "Jacksonville, FL",
            "expander": "Jacksonville, FL  —  Tier 1 Core  ·  7.0% Vacancy  ·  +0.2% Rent Growth YOY",
            "subtitle": "Florida's Most Affordable Market · Financial Services Hub · Navy Demand Floor · Thinnest FL Supply Pipeline",
            "stats": [
                {"val": "7.0%",          "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — improving from 8.5% peak"},
                {"val": "$1,528",        "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — most affordable FL core market"},
                {"val": "+0.2%",         "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — returned to positive territory", "cls": "pos"},
                {"val": "3,000",         "label": "Units Under Construction",  "src": "CoStar Q1 2026 — pipeline down 56%; thinnest FL core market"},
                {"val": "NAS Jax",       "label": "Naval Air Station",         "src": "US Navy 2024 — 28K+ personnel, largest Jacksonville employer"},
                {"val": "TIAA · Fidelity","label": "Financial Sector Anchors", "src": "TIAA HQ, Fidelity SE operations, Deutsche Bank campus"},
                {"val": "5,500",         "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Thinnest FL pipeline — earliest absorption:", "6,800 units UC is the lowest in Florida; vacancy recovery arrives 12–18 months earlier than Miami or Orlando — underwrite into a recovering market with less institutional competition."),
                ("Military demand floor + financial cluster building:", "NAS Jacksonville (28K+ personnel) sets a structural vacancy floor 200bps below city average; TIAA, Fidelity, and Deutsche Bank are assembling a stable high-income renter cohort."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Jacksonville Multifamily Q1 2026 · BLS Jacksonville Metro Q1 2026 · US Navy Jacksonville 2025",
        },
        {
            "name": "Atlanta, GA",
            "expander": "Atlanta, GA  —  Tier 1 Core  ·  7.5% Vacancy  ·  −0.2% Rent Growth YOY",
            "subtitle": "Southeast's Largest Economy · Tech and Film Hub · Institutional Capital Validating the Thesis",
            "stats": [
                {"val": "7.5%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — down from 8.8% peak; recovering"},
                {"val": "$1,695", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "−2.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026", "cls": "neg"},
                {"val": "10,200", "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 54%; concentrated in Midtown and Buckhead"},
                {"val": "+2.4%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Delta, Cox, NCR, Google, Microsoft", "cls": "pos"},
                {"val": "$4B+",   "label": "Georgia Film Economy",      "src": "Georgia Dept. of Economic Development 2024"},
                {"val": "20,000", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Institutional capital is validating the thesis:", "Blackstone, Equity Residential, and Cousins Properties all expanded Atlanta exposure in 2024–25 — RPM needs to be ahead of this repricing wave, not following it."),
                ("Suburbs are tighter than the city average:", "New luxury supply concentrated in Midtown and Buckhead; Cobb, Gwinnett, and Clayton counties show 5.5–6.5% vacancy — the value-add acquisition target."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Atlanta Multifamily Q1 2026 · BLS Atlanta–Sandy Springs Metro Q1 2026 · Georgia Dept. of Economic Development 2025",
        },
        {
            "name": "Nashville, TN",
            "expander": "Nashville, TN  —  Tier 1 Core  ·  7.5% Vacancy  ·  −0.5% Rent Growth YOY",
            "subtitle": "Highest Vacancy in Tier 1 = Deepest Discount · Healthcare and Tech Anchor · Supply Wave Ending 2026",
            "stats": [
                {"val": "7.5%",         "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — down from 9.2% peak; recovering"},
                {"val": "$1,910",       "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "−0.5%",        "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — approaching breakeven from -3.5% trough", "cls": "neg"},
                {"val": "6,200",        "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 61% from 2024 peak"},
                {"val": "+2.2%",        "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Oracle HQ, Amazon, HCA, Vanderbilt", "cls": "pos"},
                {"val": "HCA Healthcare","label": "World's Largest For-Profit Hospital HQ", "src": "HCA — 29K Nashville-area employees"},
                {"val": "10,000",       "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Highest vacancy = deepest discount = maximum upside:", "9.2% vacancy is the highest in Tier 1 — sellers conceding; supply pipeline drains by Q3 2026 and rent recovery follows within 2–3 quarters."),
                ("Healthcare anchor is recession-proof:", "HCA Healthcare (29K employees), Vanderbilt Medical Center (25K+), Oracle HQ (8,500 jobs) — US's largest for-profit hospital cluster plus $150K+ tech renters make this the most stable demand stack in Tier 1."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Nashville Multifamily Q1 2026 · BLS Nashville–Davidson Metro Q1 2026 · HCA Healthcare 2025 Annual Report",
        },
    ]

    T2_MARKETS = [
        {
            "name": "Charlotte, NC",
            "expander": "Charlotte, NC  —  Tier 2 Growth  ·  6.8% Vacancy  ·  +0.8% Rent Growth YOY",
            "subtitle": "Banking Capital of the Southeast · University Anchor · Carolinas Growth Corridor",
            "stats": [
                {"val": "6.8%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — improved from 8.0% peak"},
                {"val": "$1,658", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+0.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — turned positive as supply clears", "cls": "pos"},
                {"val": "6,800",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 52% from 2024 peak"},
                {"val": "+2.5%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Bank of America, Wells Fargo, Truist", "cls": "pos"},
                {"val": "Bank HQ","label": "Major Banking Center",      "src": "BofA HQ, Wells Fargo SE ops, Truist HQ — largest banking cluster outside NYC"},
                {"val": "11,000", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Banking sector provides premium renter cohort:", "BofA HQ (16K+ employees), Wells Fargo SE, Truist HQ — Charlotte finance creates structurally high-income renters; outer suburbs (Ballantyne, Steele Creek) offer better basis and tighter vacancy."),
                ("Pipeline moderating; recovery 12–18 months out:", "Underwrite flat rents near-term; RPM's 65/100 presence provides leasing comps and subcontractor network for efficient acquisition execution."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Charlotte Multifamily Q1 2026 · BLS Charlotte Metro Q1 2026",
        },
        {
            "name": "Raleigh-Durham, NC",
            "expander": "Raleigh-Durham, NC  —  Tier 2 Growth  ·  6.5% Vacancy  ·  +0.8% Rent Growth YOY",
            "subtitle": "Research Triangle Park · Life Sciences and Tech Demand · Triangle University Ecosystem",
            "stats": [
                {"val": "6.5%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — one of fastest-improving markets in Tier 2"},
                {"val": "$1,618", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+0.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — mildest recovery lag in Tier 2 NC", "cls": "pos"},
                {"val": "6,000",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 53% from 2024 peak"},
                {"val": "+3.0%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — RTP pharma, Apple, Google expansions", "cls": "pos"},
                {"val": "RTP",    "label": "Research Triangle Park",    "src": "World's largest research park — 300+ companies, 65K+ employees"},
                {"val": "8,200",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("RTP anchors high-income, structural demand:", "300+ companies, 65K+ employees; Duke, UNC, NC State drive continuous knowledge-worker inflows — mildest rent decline (−1.0% YOY) in the Tier 2 universe."),
                ("Apple and Google expand the demand runway:", "Apple's $1B campus and Google's data center expansion add $150K+ income renters through 2026–28."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Raleigh-Durham Q1 2026 · BLS Raleigh Metro Q1 2026 · Research Triangle Park 2025 Economic Impact",
        },
        {
            "name": "Columbus, OH",
            "expander": "Columbus, OH  —  Tier 2 Growth  ·  6.0% Vacancy  ·  +1.5% Rent Growth YOY",
            "subtitle": "Intel Semiconductor Megacampus · Midwest Affordability Leader · Ohio State University Anchor",
            "stats": [
                {"val": "6.0%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — tightening as Intel fab demand materializes"},
                {"val": "$1,352", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — most affordable in Tier 2"},
                {"val": "+1.5%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — accelerating as Intel supply chain hiring ramps", "cls": "pos"},
                {"val": "6,500",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — manageable; calibrated to Intel demand"},
                {"val": "+2.5%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Intel fab supply chain, logistics, healthcare", "cls": "pos"},
                {"val": "55/100", "label": "RPM Presence Score",        "src": "RPM Living internal operational footprint assessment"},
                {"val": "7,500",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Intel fab is the inflection point:", "Intel's $20B+ semiconductor campus commits 7,000 direct + 10,000+ indirect jobs by 2030 — will reshape multifamily demand fundamentals; Ohio State (65K+) anchors the north Columbus submarket."),
                ("Most affordable Midwest market with positive rent growth:", "Lowest rents in Tier 2 + thin supply pipeline = best risk-adjusted entry in the Midwest."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Columbus Multifamily Q1 2026 · BLS Metro Employment Q1 2026",
        },
        {
            "name": "Chicago, IL",
            "expander": "Chicago, IL  —  Tier 2 Growth  ·  5.8% Vacancy  ·  +1.8% Rent Growth YOY",
            "subtitle": "Largest Midwest Employment Base · Finance, Healthcare, and Professional Services · Positive Rent Growth",
            "stats": [
                {"val": "5.8%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — steady; thin supply protects fundamentals"},
                {"val": "$1,832", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+1.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — sustained; outperforming Sun Belt recoveries", "cls": "pos"},
                {"val": "14,500", "label": "Units Under Construction",  "src": "CoStar Q1 2026 — elevated but absorption pace steady"},
                {"val": "+1.0%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — finance, healthcare, professional services", "cls": "pos"},
                {"val": "50/100", "label": "RPM Presence Score",        "src": "RPM Living internal operational footprint assessment"},
                {"val": "12,000", "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Largest Midwest demand base — stable absorption:", "4.9M metro employment absorbs supply more effectively than smaller Midwest markets; finance, healthcare, and professional services anchor demand."),
                ("+1.0% rent growth; fundamentals stronger than perception:", "Thin supply pipeline and positive rent growth — institutional underexposure may create acquisition pricing ahead of broader recognition."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Chicago Multifamily Q1 2026 · BLS Metro Employment Q1 2026",
        },
        {
            "name": "Minneapolis, MN",
            "expander": "Minneapolis, MN  —  Tier 2 Growth  ·  5.2% Vacancy  ·  +1.5% Rent Growth YOY",
            "subtitle": "Tightest Midwest Vacancy · Mayo Clinic Healthcare Ecosystem · Stable Positive Rent Growth",
            "stats": [
                {"val": "5.2%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — tightest in RPM Midwest; continues to tighten"},
                {"val": "$1,598", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+1.5%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — sustained; benefits from thin pipeline", "cls": "pos"},
                {"val": "5,200",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — thinnest Midwest pipeline; constrained geography"},
                {"val": "+1.2%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Mayo Clinic, Allina Health, financial services", "cls": "pos"},
                {"val": "50/100", "label": "RPM Presence Score",        "src": "RPM Living internal operational footprint assessment"},
                {"val": "5,000",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Tightest Midwest vacancy with positive rent growth:", "5.5% vacancy + thinnest supply pipeline in the group — strongest fundamentals in the RPM Tier 2 Midwest universe."),
                ("Healthcare anchor drives stable demand:", "Mayo Clinic (44K employees), Allina Health, M Health Fairview — medical workers are the most predictable renter cohort; underwrite Minnesota seasonality into unit turn and utility costs."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Minneapolis Multifamily Q1 2026 · BLS Metro Employment Q1 2026",
        },
        {
            "name": "Phoenix, AZ",
            "expander": "Phoenix, AZ  —  Tier 2 Growth  ·  7.5% Vacancy  ·  +1.2% Rent Growth YOY",
            "subtitle": "Highest US Population Growth · Deep Supply Wave · Highest Net Absorption Nationally · Trough Acquisition Window",
            "stats": [
                {"val": "7.5%",    "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — down from 9.0% peak; fastest recovery in US"},
                {"val": "$1,582",  "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+1.2%",   "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — sharpest recovery in RPM Tier 2", "cls": "pos"},
                {"val": "12,000",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 52% from 2024 peak; pipeline cleared"},
                {"val": "#1",      "label": "US Population Growth Rate", "src": "Census 2024 — fastest-growing large metro nationally", "cls": "pos"},
                {"val": "+3.2%",   "label": "Job Growth YOY",            "src": "BLS Q1 2026 — TSMC, Intel, semiconductor corridor", "cls": "pos"},
                {"val": "22,000",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026 — among highest nationally", "cls": "pos"},
            ],
            "insights": [
                ("Fastest recovery in Tier 2:", "Vacancy down from 9.0% to 7.5% in 12 months with rent growth flipping to +1.2% — #1 US population growth metro with TSMC and Intel fab supply chain hiring driving demand."),
                ("Semiconductor corridor is a 15-year demand driver:", "TSMC (40K jobs by 2030), Intel Ocotillo — target 2005–2015 vintage in Chandler, Gilbert, Tempe; recovery is underway now; model 3–5% continued growth through 2027."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Phoenix Multifamily Q1 2026 · BLS Phoenix Metro Q1 2026 · Census ACS 2024",
        },
        {
            "name": "San Diego, CA",
            "expander": "San Diego, CA  —  Tier 2 Growth  ·  4.8% Vacancy  ·  +2.8% Rent Growth YOY",
            "subtitle": "Tightest Tier 2 Market · Military and Biotech Demand · West Coast Entry Point for RPM",
            "stats": [
                {"val": "4.8%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — tightest in Tier 2; slight uptick from new supply"},
                {"val": "$2,538", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026 — highest in Tier 2"},
                {"val": "+2.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — accelerating; structural demand outpacing supply", "cls": "pos"},
                {"val": "5,200",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — lowest in Tier 2; geography-constrained"},
                {"val": "100K+",  "label": "Military Personnel",        "src": "Camp Pendleton, NAS Miramar, NAS North Island combined"},
                {"val": "Biotech", "label": "Life Sciences Cluster",    "src": "Torrey Pines / Sorrento Valley — 600+ biotech companies"},
                {"val": "4,800",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Tightest vacancy in Tier 2 — structural demand:", "4.5% vacancy; 100K+ military personnel (Camp Pendleton, NAS Miramar, NAS North Island) plus 600+ biotech companies drive permanent, high-income renter demand."),
                ("West Coast entry opportunity:", "55/100 presence score; lowest supply risk in Tier 2 means operational ramp-up time is less critical — right entry point for West Coast expansion."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar San Diego Multifamily Q1 2026 · BLS San Diego Metro Q1 2026 · San Diego Regional EDC 2025",
        },
        {
            "name": "Las Vegas, NV",
            "expander": "Las Vegas, NV  —  Tier 2 Growth  ·  6.2% Vacancy  ·  +1.5% Rent Growth YOY",
            "subtitle": "Gaming to Logistics Diversification · Workforce Housing Undersupply · Entertainment Economy Expanding",
            "stats": [
                {"val": "6.2%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — tightening from 7.0%; logistics jobs absorbing supply"},
                {"val": "$1,462", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+1.5%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — turned positive on pipeline reduction", "cls": "pos"},
                {"val": "5,800",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — down 39%; pipeline recalibrated to demand"},
                {"val": "+2.5%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — gaming, logistics, distribution, A's stadium", "cls": "pos"},
                {"val": "55/100", "label": "RPM Presence Score",        "src": "RPM Living internal operational footprint assessment"},
                {"val": "7,500",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Gaming-to-logistics diversification is the story:", "Amazon, USPS, FedEx distribution centers + F1 Grand Prix infrastructure + Raiders/A's stadium = permanent employment diversification beyond hospitality."),
                ("Workforce housing thesis fits the demographic:", "Gaming and hospitality creates $35K–$65K household income demand for B-class product — underserved by institutional capital focused on class-A."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Las Vegas Multifamily Q1 2026 · BLS Metro Employment Q1 2026",
        },
        {
            "name": "Charleston, SC",
            "expander": "Charleston, SC  —  Tier 2 Growth  ·  6.5% Vacancy  ·  +0.8% Rent Growth YOY",
            "subtitle": "Manufacturing Demand Anchor · Port of Charleston Expansion · Fastest-Growing Small Metro in the US",
            "stats": [
                {"val": "6.5%",   "label": "Multifamily Vacancy",     "src": "Yardi Matrix Q1 2026 — one of fastest-improving markets in Tier 2"},
                {"val": "$1,518", "label": "Avg Effective Rent / Mo",  "src": "RealPage Analytics Q1 2026"},
                {"val": "+0.8%",  "label": "Rent Growth YOY",          "src": "Yardi Matrix Q1 2026 — turned positive as manufacturing hiring sustains demand", "cls": "pos"},
                {"val": "2,800",  "label": "Units Under Construction",  "src": "CoStar Q1 2026 — thinnest in Tier 2; lowest supply risk"},
                {"val": "+3.0%",  "label": "Job Growth YOY",            "src": "BLS Q1 2026 — Boeing, Volvo, Mercedes-Benz, Port Leatherman expansion", "cls": "pos"},
                {"val": "50/100", "label": "RPM Presence Score",        "src": "RPM Living internal operational footprint assessment"},
                {"val": "3,000",  "label": "Net Absorption (Units/Yr)", "src": "CoStar Q1 2026", "cls": "pos"},
            ],
            "insights": [
                ("Manufacturing anchors structural workforce housing demand:", "Boeing (6K+), Volvo Cars (4K+), Mercedes-Benz Vans — high-wage workforce renters underserved by institutional capital; Port Leatherman expansion adds 1,500+ logistics jobs in North Charleston."),
                ("Thinnest Tier 2 pipeline + fastest-growing small metro:", "4,200 units UC (lowest in group) + 25%+ metro population growth last decade = lowest supply-adjusted risk in the Tier 2 universe."),
            ],
            "sources": "Yardi Matrix Q1 2026 · CoStar Charleston Multifamily Q1 2026 · BLS Metro Employment Q1 2026",
        },
    ]

    ALL_MARKETS_DICT = {m["name"]: m for m in T1_MARKETS + T2_MARKETS}

    # ── Session state for exclusive tier selection ────────────────────────────
    for _k in ("mkt_t1", "mkt_t2", "mkt_t3"):
        if _k not in st.session_state:
            st.session_state[_k] = None

    def _clr_t2_t3():
        st.session_state.mkt_t2 = None
        st.session_state.mkt_t3 = None

    def _clr_t1_t3():
        st.session_state.mkt_t1 = None
        st.session_state.mkt_t3 = None

    def _clr_t1_t2():
        st.session_state.mkt_t1 = None
        st.session_state.mkt_t2 = None

    # ── Tier pill bars ────────────────────────────────────────────────────────
    sel_t1 = st.pills(
        "Tier 1 — Core Markets",
        [m["name"] for m in T1_MARKETS],
        selection_mode="single",
        default=None,
        key="mkt_t1",
        on_change=_clr_t2_t3,
    )
    sel_t2 = st.pills(
        "Tier 2 — Growth Markets",
        [m["name"] for m in T2_MARKETS],
        selection_mode="single",
        default=None,
        key="mkt_t2",
        on_change=_clr_t1_t3,
    )
    sel_t3 = st.pills(
        "Tier 3 — Expansion Watch",
        _T3_NAMES,
        selection_mode="single",
        default=None,
        key="mkt_t3",
        on_change=_clr_t1_t2,
    )
    _sel = sel_t1 or sel_t2 or sel_t3

    # ── Plotly US market map ──────────────────────────────────────────────────
    _mlats, _mlons, _mtexts, _mcolors, _msizes, _mborders = [], [], [], [], [], []

    for _mname, (_mlat, _mlon, _mtier) in _MARKET_COORDS.items():
        _mlats.append(_mlat)
        _mlons.append(_mlon)
        if _mname in ALL_MARKETS_DICT:
            _md = ALL_MARKETS_DICT[_mname]
            _ms = _md["stats"]
            _vac = next((x["val"] for x in _ms if "Vacancy" in x["label"]), "—")
            _rg  = next((x["val"] for x in _ms if "Rent Growth" in x["label"]), "—")
            _rnt = next((x["val"] for x in _ms if "Rent / Mo" in x["label"]), "—")
            _tlbl = "Tier 1 — Core" if _mtier == 1 else "Tier 2 — Growth"
            _mtexts.append(
                f"<b>{_mname}</b><br>{_tlbl}<br>"
                f"Vacancy: {_vac}<br>Rent Growth: {_rg}<br>Avg Rent/Mo: {_rnt}"
            )
        else:
            _mtexts.append(
                f"<b>{_mname}</b><br>Tier 3 — Expansion Watch<br>{_T3_DATA.get(_mname, '')}"
            )

        if _mname == _sel:
            _mcolors.append("#C8A96E"); _msizes.append(20); _mborders.append("#ffffff")
        elif _mtier == 1:
            _mcolors.append("#C8A96E"); _msizes.append(12); _mborders.append("#1A1A1A")
        elif _mtier == 2:
            _mcolors.append("#A07840"); _msizes.append(10); _mborders.append("#1A1A1A")
        else:
            _mcolors.append("#555555"); _msizes.append(8);  _mborders.append("#1A1A1A")

    _mfig = go.Figure(go.Scattergeo(
        lat=_mlats, lon=_mlons,
        text=_mtexts,
        hovertemplate="%{text}<extra></extra>",
        mode="markers",
        marker=dict(
            size=_msizes,
            color=_mcolors,
            line=dict(width=1.5, color=_mborders),
        ),
    ))
    _mfig.update_layout(
        geo=dict(
            scope="usa",
            projection_type="albers usa",
            showland=True,    landcolor="#2C2C2C",
            showcoastlines=True, coastlinecolor="#444",
            showlakes=True,   lakecolor="#1A1A1A",
            showframe=False,
            bgcolor="#1A1A1A",
            showsubunits=True, subunitcolor="#3A3A3A",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#1A1A1A",
        height=340,
        hoverlabel=dict(
            bgcolor="#1A1A1A",
            bordercolor="#C8A96E",
            font=dict(color="#fff", size=11, family="Helvetica Neue, Arial"),
        ),
    )
    st.plotly_chart(_mfig, use_container_width=True, config={"displayModeBar": False})

    # ── Market detail block ───────────────────────────────────────────────────
    if _sel and _sel in ALL_MARKETS_DICT:
        _lm = ALL_MARKETS_DICT[_sel]
        render_market_block(
            _lm["name"], _lm["subtitle"], "Data as of Q1 2026",
            _lm["stats"], _lm["insights"], _lm["sources"],
        )
    elif _sel and _sel in _T3_DATA:
        st.markdown(f"""
        <div class="mi-header">
          <div>
            <div class="mi-title">{_sel}</div>
            <div class="mi-sub">Tier 3 — Expansion Watch &nbsp;·&nbsp; Full intelligence module in Phase 3</div>
          </div>
          <div class="mi-data-note">Phase 3</div>
        </div>
        <div class="insight-box" style="margin-top:1px;">
          <h5>Market Brief</h5>
          <ul><li>{_T3_DATA[_sel]}</li>
          <li>Full CoStar and Yardi Matrix data integration in Phase 3.</li></ul>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Deal Analyzer
# ══════════════════════════════════════════════════════════════════════════════

with tab_deal:
    st.markdown('<div class="sec-lbl">Multifamily deal analyzer &nbsp;&middot;&nbsp; score any property against RPM Living acquisition criteria &nbsp;&middot;&nbsp; 8 weighted criteria &nbsp;&middot;&nbsp; 0&ndash;100 scale</div>', unsafe_allow_html=True)

    with st.expander("Scoring methodology — how this analyzer works"):
        st.markdown(f"""
| Criterion | Weight | Key Driver |
|---|---|---|
| Market Fit (Tier) | 20 pts | Tier 1 Core = 20, Tier 2 Growth = 14, Tier 3 Expansion = 7, Outside RPM = 0 |
| RPM Market Presence | 15 pts | Operational footprint score (0–100) × 15. Higher presence = lower execution risk and shorter lease-up timeline. |
| Cap Rate vs. 10Y Treasury | 15 pts | Spread in bps over {TREASURY_10Y_REF}% 10Y proxy. >175bps = 15 pts; negative spread = 0 pts. |
| Loss-to-Lease Opportunity | 15 pts | (Market rent − In-place rent) / In-place rent. >10% gap = 15 pts; negative = 0 pts. |
| Vacancy vs. Market Average | 10 pts | Property vacancy vs. market benchmark. Underperforming asset = higher score (more operational upside). |
| Asset Vintage / Capex Profile | 10 pts | 1990–2010 = 10 pts (ideal value-add window). Pre-1980 or post-2022 = lower. |
| Supply Pipeline Risk | 10 pts | Market-level supply risk: Low = 10, Moderate = 6, High = 2. Based on Q1 2026 market data. |
| Asset Scale / G&A Efficiency | 5 pts | 200–400 units = 5 pts (optimal). Below 100 or above 600 = reduced. |

**Thresholds:** 75–100 = Advance to Due Diligence · 55–74 = Conditional Review · 35–54 = Monitor / Pass · 0–34 = Pass

*Market data as of Q1 2026 (Yardi Matrix, RealPage, CoStar). 10Y Treasury reference: {TREASURY_10Y_REF}% (Phase 2 will pull live from FRED GS10). RPM presence scores reflect internal operational footprint assessment.*
        """)

    col_form, col_result = st.columns([1, 1], gap="large")

    with col_form:
        st.markdown('<div class="deal-form-card"><div class="deal-form-title">Property Details</div>', unsafe_allow_html=True)

        with st.form("deal_form"):
            property_name = st.text_input("Property Name / Address", placeholder="e.g. The Meridian at Riverside, 1200 Main St Austin TX")
            market = st.selectbox("Market", options=list(MARKET_DATA.keys()))
            asset_class = st.selectbox("Asset Class",
                ["Garden-Style", "Mid-Rise (4–7 stories)", "High-Rise (8+ stories)", "BTR / Horizontal", "Mixed-Use"])

            st.markdown("**Location & Size**")
            col_a, col_b = st.columns(2)
            with col_a:
                units = st.number_input("Total Units", min_value=1, max_value=2000, value=250, step=10)
                year_built = st.number_input("Year Built", min_value=1960, max_value=2025, value=2005)
            with col_b:
                asking_price_m = st.number_input("Asking Price ($M)", min_value=0.1, max_value=500.0, value=35.0, step=0.5)
                noi_k = st.number_input("Annual NOI ($K)", min_value=0.0, value=1750.0, step=50.0,
                                        help="Net Operating Income before debt service")

            st.markdown("**Financial Metrics**")
            col_c, col_d = st.columns(2)
            with col_c:
                cap_rate = st.number_input("Going-in Cap Rate (%)", min_value=0.5, max_value=12.0, value=5.0, step=0.05,
                                           format="%.2f")
                inplace_rent = st.number_input("In-Place Avg Rent ($/mo)", min_value=500.0, max_value=8000.0,
                                               value=1450.0, step=25.0)
            with col_d:
                vacancy = st.number_input("Current Vacancy (%)", min_value=0.0, max_value=50.0, value=9.0, step=0.5)
                market_rent = st.number_input("Market Avg Rent ($/mo)", min_value=500.0, max_value=8000.0,
                                              value=1620.0, step=25.0,
                                              help="Current market asking rent for comparable units in this submarket")

            treasury_rate = st.number_input("10Y Treasury Rate (%)", min_value=1.0, max_value=10.0,
                                            value=TREASURY_10Y_REF, step=0.05, format="%.2f",
                                            help=f"Default: {TREASURY_10Y_REF}% (Q1 2026 proxy). Update to current rate for live analysis.")

            submitted = st.form_submit_button("Analyze Deal", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_result:
        if submitted:
            total, criteria, rec, rec_detail = score_deal(
                market=market,
                asset_class=asset_class,
                units=int(units),
                asking_price_m=float(asking_price_m),
                year_built=int(year_built),
                cap_rate_pct=float(cap_rate),
                inplace_rent=float(inplace_rent),
                market_rent=float(market_rent),
                vacancy_pct=float(vacancy),
                noi_annual_k=float(noi_k) if noi_k else None,
                treasury_rate=float(treasury_rate),
            )

            if total >= 75:   score_color, rec_cls = RPM_GREEN, "advance"
            elif total >= 55: score_color, rec_cls = RPM_AMBER, "conditional"
            elif total >= 35: score_color, rec_cls = RPM_AMBER, "monitor"
            else:             score_color, rec_cls = RPM_RED,   "pass-box"

            prop_label = property_name if property_name.strip() else "Unnamed Property"

            st.markdown(f"""
            <div class="score-hero">
              <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:var(--rpm-mid);margin-bottom:8px;font-family:'Helvetica Neue',Arial,sans-serif;">{prop_label} &nbsp;&middot;&nbsp; {market}</div>
              <div class="score-num" style="color:{score_color};">{total}<span class="score-denom"> / 100</span></div>
              <div class="score-label">RPM Living Investment Score</div>
            </div>

            <div class="rec-box {rec_cls}">
              <h5>Recommendation</h5>
              <p><strong>{rec}</strong> &mdash; {rec_detail}</p>
            </div>

            <div style="font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--rpm-mid);font-weight:600;margin-bottom:8px;font-family:'Helvetica Neue',Arial,sans-serif;">Score Breakdown</div>
            <div class="criterion-grid">
            """, unsafe_allow_html=True)

            for c in criteria:
                pct = c.points_earned / c.points_max * 100 if c.points_max else 0
                st.markdown(f"""
                <div class="criterion-card {c.status}">
                  <div class="criterion-name">{c.name}</div>
                  <div class="criterion-pts">{c.points_earned:.1f} <span style="font-size:11px;color:var(--rpm-mid);font-weight:400;">/ {c.points_max}</span></div>
                  <div class="criterion-note">{c.note}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

            # Quick metrics strip
            price_per_unit = asking_price_m * 1_000_000 / units if units > 0 else 0
            ltl = (market_rent - inplace_rent) / inplace_rent * 100 if inplace_rent > 0 else 0
            spread_bps = (cap_rate - treasury_rate) * 100

            st.markdown(f"""
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--rpm-border);margin-top:12px;margin-bottom:12px;">
              <div class="mi-stat" style="background:var(--rpm-dark);">
                <div class="mi-stat-val" style="font-size:15px;">${price_per_unit:,.0f}</div>
                <div class="mi-stat-lbl">Price / Unit</div>
              </div>
              <div class="mi-stat" style="background:var(--rpm-dark);">
                <div class="mi-stat-val {'pos' if ltl > 0 else 'neg'}" style="font-size:15px;">{ltl:+.1f}%</div>
                <div class="mi-stat-lbl">Loss-to-Lease</div>
              </div>
              <div class="mi-stat" style="background:var(--rpm-dark);">
                <div class="mi-stat-val {'pos' if spread_bps > 100 else 'neg'}" style="font-size:15px;">{spread_bps:.0f}bps</div>
                <div class="mi-stat-lbl">Cap Rate Spread</div>
              </div>
              <div class="mi-stat" style="background:var(--rpm-dark);">
                <div class="mi-stat-val" style="font-size:15px;">{MARKET_DATA.get(market,{}).get('rpm_presence','—')}/100</div>
                <div class="mi-stat-lbl">RPM Presence Score</div>
              </div>
            </div>
            <div class="disclaimer">
              Analysis generated by RPM Living Investment Intelligence v1.0 &nbsp;&middot;&nbsp; Market data as of Q1 2026 (Yardi Matrix, RealPage, CoStar) &nbsp;&middot;&nbsp;
              10Y Treasury reference rate: {treasury_rate:.2f}% &nbsp;&middot;&nbsp; This tool is for preliminary screening only and does not constitute investment advice.
              All acquisitions subject to RPM Living's full underwriting, due diligence, and Investment Committee approval process.
            </div>
            """, unsafe_allow_html=True)

        else:
            st.markdown("""
            <div class="phase-placeholder" style="margin-top:40px;">
              <h3>Enter property details to generate score</h3>
              <p>Complete the form to receive a scored analysis across 8 RPM Living acquisition criteria,<br>
              including RPM's operational presence in the target market as a first-class risk input.</p>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Macro Overlay
# ══════════════════════════════════════════════════════════════════════════════

with tab_macro:
    from fetchers.fred_fetcher import fetch_all_macro

    _m_lbl, _m_btn = st.columns([5, 1])
    with _m_lbl:
        st.markdown(
            '<div class="sec-lbl">FRED macro overlay &nbsp;&middot;&nbsp; live St. Louis Fed data &nbsp;&middot;&nbsp; '
            '4-hour cache &nbsp;&middot;&nbsp; capital markets → multifamily fundamentals</div>',
            unsafe_allow_html=True,
        )
    with _m_btn:
        _macro_refresh = st.button("Refresh Data", key="macro_refresh")

    @st.cache_data(ttl=14400, show_spinner=False)
    def _load_macro():
        return fetch_all_macro()

    if _macro_refresh:
        st.cache_data.clear()
    with st.spinner("Fetching FRED data..."):
        _macro = _load_macro()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _latest(s):
        if s is None or len(s) == 0: return None
        return float(s.dropna().iloc[-1])

    def _yoy(s):
        if s is None or len(s) < 13: return None
        v = s.dropna()
        return (float(v.iloc[-1]) / float(v.iloc[-13]) - 1.0) * 100.0

    def _chg(s):
        if s is None or len(s) < 2: return None
        v = s.dropna()
        return float(v.iloc[-1]) - float(v.iloc[-2])

    def _fmt(val, suffix="", dec=2, sign=False):
        if val is None: return "—"
        prefix = "+" if sign and val > 0 else ""
        return f"{prefix}{val:.{dec}f}{suffix}"

    def _fmt_dollar(val):
        if val is None: return "—"
        if val >= 1_000_000: return f"${val/1_000_000:.2f}M"
        if val >= 1_000:     return f"${val/1_000:.1f}K"
        return f"${val:,.0f}"

    gs10  = _macro.get("gs10")
    gs2   = _macro.get("gs2")
    cpi   = _macro.get("cpi")
    rcpi  = _macro.get("rent_cpi")
    rpri  = _macro.get("rent_primary")
    vac   = _macro.get("vacancy")
    hvac  = _macro.get("homeowner_vacancy")
    prm   = _macro.get("permits")
    unem  = _macro.get("unemployment")
    mtg   = _macro.get("mortgage30")
    cs    = _macro.get("case_shiller")
    mhp   = _macro.get("median_home_price")

    gs10_val  = _latest(gs10)
    gs2_val   = _latest(gs2)
    spread    = (gs10_val - gs2_val) if gs10_val and gs2_val else None
    cpi_yoy   = _yoy(cpi)
    rcpi_yoy  = _yoy(rcpi)
    rpri_yoy  = _yoy(rpri)
    vac_val   = _latest(vac)
    hvac_val  = _latest(hvac)
    prm_val   = _latest(prm)
    unem_val  = _latest(unem)
    mtg_val   = _latest(mtg)
    mtg_chg   = _chg(mtg)
    cs_val    = _latest(cs)
    cs_yoy    = _yoy(cs)
    mhp_val   = _latest(mhp)

    # ── Cap rate spread signal ─────────────────────────────────────────────────
    _BENCH_CAP = 5.0
    cap_spread_bps = int((_BENCH_CAP - gs10_val) * 100) if gs10_val else None
    if cap_spread_bps is not None:
        if cap_spread_bps < 0:
            _spread_cls, _spread_icon, _spread_msg = "high-risk", "NEGATIVE SPREAD", \
                f"Multifamily cap rates ({_BENCH_CAP:.1f}%) are BELOW the 10Y Treasury ({gs10_val:.2f}%). Capital reallocation is the rational move."
        elif cap_spread_bps < 150:
            _spread_cls, _spread_icon, _spread_msg = "moderate", "COMPRESSED — WATCH", \
                f"Cap rate spread at {cap_spread_bps}bps — below the 150bps Moghadam threshold. Underwriting discipline required; value-add yield premium is the buffer."
        else:
            _spread_cls, _spread_icon, _spread_msg = "ok", f"{cap_spread_bps}bps SPREAD", \
                f"Cap rate spread at {cap_spread_bps}bps above 10Y Treasury. Adequate premium for multifamily risk; acquisition window remains open."
    else:
        _spread_cls, _spread_icon, _spread_msg = "na", "—", "FRED data unavailable."

    _spread_color = {"ok": RPM_GREEN, "moderate": RPM_AMBER, "high-risk": RPM_RED, "na": RPM_MID}[_spread_cls]
    _spread_bg    = {"ok": RPM_GREEN_LT, "moderate": RPM_AMBER_LT, "high-risk": RPM_RED_LT, "na": "#eee"}[_spread_cls]

    st.markdown(f"""
    <div style="background:{_spread_bg};border-left:4px solid {_spread_color};
         padding:12px 16px;margin-bottom:14px;
         font-family:'Helvetica Neue',Arial,sans-serif;">
      <div style="font-size:9px;letter-spacing:0.14em;text-transform:uppercase;
           font-weight:600;color:{_spread_color};margin-bottom:4px;">
        Cap Rate Spread Signal &nbsp;·&nbsp; {_spread_icon}
      </div>
      <div style="font-size:12px;color:{RPM_BLACK};line-height:1.6;">{_spread_msg}</div>
      <div style="font-size:10px;color:{RPM_MID};margin-top:4px;">
        Benchmark cap rate: {_BENCH_CAP:.1f}% (multifamily proxy) &nbsp;·&nbsp;
        Live 10Y: {_fmt(gs10_val,'%')} &nbsp;·&nbsp;
        30Y Mortgage: {_fmt(mtg_val,'%')} &nbsp;·&nbsp;
        Source: FRED GS10, MORTGAGE30US
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Hero metric strip — Row 1: Rates & Inflation ──────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-bottom:4px;">Rates &amp; Inflation</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="mi-stats" style="margin-bottom:12px;">
      <div class="mi-stat">
        <div class="mi-stat-val">{_fmt(gs10_val,'%')}</div>
        <div class="mi-stat-lbl">10Y Treasury (GS10)</div>
        <div class="mi-stat-src">FRED — live</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val">{_fmt(gs2_val,'%')}</div>
        <div class="mi-stat-lbl">2Y Treasury (GS2)</div>
        <div class="mi-stat-src">FRED — live</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val {'pos' if spread and spread >= 0 else 'neg'}"
             style="font-size:18px;font-weight:300;color:{'#5a9e70' if spread and spread>=0 else '#c47070'}">
          {_fmt(spread,'%',sign=True)}
        </div>
        <div class="mi-stat-lbl">Yield Curve (10Y−2Y)</div>
        <div class="mi-stat-src">FRED GS10 − GS2</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(mtg_val,'%')}
        </div>
        <div class="mi-stat-lbl">30Y Fixed Mortgage</div>
        <div class="mi-stat-src">FRED MORTGAGE30US — weekly</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val {'neg' if cpi_yoy and cpi_yoy>3 else 'pos'}"
             style="font-size:18px;font-weight:300;color:{'#c47070' if cpi_yoy and cpi_yoy>3 else '#5a9e70'}">
          {_fmt(cpi_yoy,'%',sign=True)}
        </div>
        <div class="mi-stat-lbl">CPI Inflation YOY</div>
        <div class="mi-stat-src">FRED CPIAUCSL</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(rcpi_yoy,'%',sign=True)}
        </div>
        <div class="mi-stat-lbl">Shelter CPI YOY</div>
        <div class="mi-stat-src">FRED CUSR0000SEHA</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(rpri_yoy,'%',sign=True)}
        </div>
        <div class="mi-stat-lbl">Rent of Primary Res. YOY</div>
        <div class="mi-stat-src">FRED CUSR0000SEHC</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Hero metric strip — Row 2: Housing Fundamentals ───────────────────────
    st.markdown('<div class="sec-lbl" style="margin-bottom:4px;">Housing Fundamentals</div>', unsafe_allow_html=True)
    _mtg_chg_str = f" ({_fmt(mtg_chg, 'pp', sign=True)})" if mtg_chg is not None else ""
    st.markdown(f"""
    <div class="mi-stats" style="margin-bottom:16px;">
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(vac_val,'%')}
        </div>
        <div class="mi-stat-lbl">US Rental Vacancy</div>
        <div class="mi-stat-src">FRED RRVRUSQ156N — quarterly</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(hvac_val,'%')}
        </div>
        <div class="mi-stat-lbl">Homeowner Vacancy</div>
        <div class="mi-stat-src">FRED RHVRUSQ156N — quarterly</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val {'neg' if unem_val and unem_val>5 else 'pos'}"
             style="font-size:18px;font-weight:300;">
          {_fmt(unem_val,'%')}
        </div>
        <div class="mi-stat-lbl">Unemployment Rate</div>
        <div class="mi-stat-src">FRED UNRATE</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(prm_val,'',dec=0)}K
        </div>
        <div class="mi-stat-lbl">Building Permits (SAAR)</div>
        <div class="mi-stat-src">FRED PERMIT — thousands</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt_dollar(mhp_val)}
        </div>
        <div class="mi-stat-lbl">Median Home Sale Price</div>
        <div class="mi-stat-src">FRED MSPUS — quarterly</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val {'neg' if cs_yoy and cs_yoy>5 else 'pos'}"
             style="font-size:18px;font-weight:300;">
          {_fmt(cs_yoy,'%',sign=True)}
        </div>
        <div class="mi-stat-lbl">Case-Shiller HPI YOY</div>
        <div class="mi-stat-src">FRED CSUSHPISA — national</div>
      </div>
      <div class="mi-stat">
        <div class="mi-stat-val" style="font-size:18px;font-weight:300;color:var(--rpm-gold);">
          {_fmt(cs_val,'',dec=1)}
        </div>
        <div class="mi-stat-lbl">Case-Shiller Index Level</div>
        <div class="mi-stat-src">Jan 2000 = 100</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Plotly chart helpers ───────────────────────────────────────────────────
    def _dark_layout(title, yformat=".2f", height=260):
        return dict(
            paper_bgcolor="#1A1A1A", plot_bgcolor="#1A1A1A",
            font=dict(color="#888", family="Helvetica Neue, Arial", size=10),
            title=dict(text=title, font=dict(color="#888", size=9), x=0,
                       xanchor="left", pad=dict(l=0, t=4)),
            xaxis=dict(gridcolor="#2A2A2A", linecolor="#333", tickfont=dict(size=9)),
            yaxis=dict(gridcolor="#2A2A2A", linecolor="#333", tickfont=dict(size=9),
                       tickformat=yformat),
            margin=dict(l=50, r=16, t=36, b=36),
            height=height,
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9), x=0.01, y=0.99),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#1A1A1A", bordercolor="#C8A96E",
                            font=dict(color="#fff", size=10)),
        )

    def _line(s, name, color="#C8A96E", dash="solid", width=1.5):
        if s is None or len(s) == 0:
            return go.Scatter(x=[], y=[], name=name)
        v = s.dropna()
        return go.Scatter(
            x=v.index, y=v.values, name=name, mode="lines",
            line=dict(color=color, width=width, dash=dash),
            hovertemplate=f"%{{y:.2f}} ({name})<extra></extra>",
        )

    def _yoy_series(s):
        if s is None or len(s) < 13: return None
        v = s.dropna()
        return (v / v.shift(12) - 1) * 100

    _cfg = {"displayModeBar": False}

    # ── Row 1: Rates ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin:8px 0 4px;">Rate Environment</div>', unsafe_allow_html=True)
    _r1c1, _r1c2 = st.columns(2)

    with _r1c1:
        _f1 = go.Figure()
        if gs10 is not None:
            _f1.add_trace(_line(gs10, "10Y Treasury (GS10)", "#C8A96E"))
        if gs2 is not None:
            _f1.add_trace(_line(gs2, "2Y Treasury (GS2)", "#7A5A1A", dash="dot"))
        _f1.add_hline(y=_BENCH_CAP, line=dict(color="#2D5A3D", width=1, dash="dash"),
                      annotation_text=f"Cap Rate Proxy {_BENCH_CAP}%",
                      annotation_font=dict(color="#2D5A3D", size=9))
        if gs10_val:
            _f1.add_hline(y=1.5 + gs10_val, line=dict(color="#555", width=0.5, dash="dot"),
                          annotation_text="150bps threshold",
                          annotation_font=dict(color="#666", size=8))
        _f1.update_layout(**_dark_layout("TREASURY RATES VS. CAP RATE PROXY  (%)", yformat=".2f"))
        st.plotly_chart(_f1, use_container_width=True, config=_cfg)

    with _r1c2:
        _f_mtg = go.Figure()
        if mtg is not None:
            _f_mtg.add_trace(_line(mtg, "30Y Fixed Mortgage Rate", "#C8A96E"))
        if gs10 is not None:
            _f_mtg.add_trace(_line(gs10, "10Y Treasury", "#7A5A1A", dash="dot", width=1))
        _f_mtg.update_layout(**_dark_layout("30Y FIXED MORTGAGE RATE VS. 10Y TREASURY  (%)", yformat=".2f"))
        st.plotly_chart(_f_mtg, use_container_width=True, config=_cfg)

    # ── Row 2: Inflation & Rents ──────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin:8px 0 4px;">Inflation &amp; Rent Prices</div>', unsafe_allow_html=True)
    _r2c1, _r2c2 = st.columns(2)

    with _r2c1:
        _f2 = go.Figure()
        _cpi_yoy_s  = _yoy_series(cpi)
        _rcpi_yoy_s = _yoy_series(rcpi)
        _rpri_yoy_s = _yoy_series(rpri)
        if _cpi_yoy_s is not None:
            _f2.add_trace(_line(_cpi_yoy_s, "CPI All Items YOY", "#C8A96E"))
        if _rcpi_yoy_s is not None:
            _f2.add_trace(_line(_rcpi_yoy_s, "Shelter CPI YOY", "#7A5A1A", dash="dot"))
        if _rpri_yoy_s is not None:
            _f2.add_trace(_line(_rpri_yoy_s, "Rent of Primary Res. YOY", "#A07840", dash="dash"))
        _f2.add_hline(y=2.0, line=dict(color="#2D5A3D", width=1, dash="dash"),
                      annotation_text="Fed Target 2%",
                      annotation_font=dict(color="#2D5A3D", size=9))
        _f2.update_layout(**_dark_layout("INFLATION: CPI vs. SHELTER vs. PRIMARY RENT  (YOY %)", yformat=".1f"))
        st.plotly_chart(_f2, use_container_width=True, config=_cfg)

    with _r2c2:
        # Rent of Primary Residence — index level (rebased to 100 at start)
        _f_rent = go.Figure()
        if rpri is not None:
            _rv = rpri.dropna()
            _rv_rb = (_rv / _rv.iloc[0]) * 100  # rebase to 100
            _f_rent.add_trace(go.Scatter(
                x=_rv_rb.index, y=_rv_rb.values,
                name="Rent CPI Index (rebased 100)", mode="lines",
                line=dict(color="#C8A96E", width=1.5),
                hovertemplate="%{y:.1f} index<extra></extra>",
                fill="tozeroy", fillcolor="rgba(200,169,110,0.08)",
            ))
        if rcpi is not None:
            _sv = rcpi.dropna()
            _sv_rb = (_sv / _sv.iloc[0]) * 100
            _f_rent.add_trace(_line(_sv_rb, "Shelter CPI Index (rebased 100)", "#7A5A1A", dash="dot", width=1))
        _f_rent.update_layout(**_dark_layout("RENT PRICE INDEX — Rent of Primary Residence vs. Shelter  (rebased=100)", yformat=".1f"))
        st.plotly_chart(_f_rent, use_container_width=True, config=_cfg)

    # ── Row 3: Vacancy & Supply ───────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin:8px 0 4px;">Vacancy &amp; Supply Pipeline</div>', unsafe_allow_html=True)
    _r3c1, _r3c2 = st.columns(2)

    with _r3c1:
        _f3 = go.Figure()
        if vac is not None:
            _vv = vac.dropna()
            _f3.add_trace(_line(_vv, "Rental Vacancy", "#C8A96E"))
        if hvac is not None:
            _hv = hvac.dropna()
            _f3.add_trace(_line(_hv, "Homeowner Vacancy", "#7A5A1A", dash="dot"))
        _f3.add_hrect(y0=5.0, y1=8.0, fillcolor="rgba(200,169,110,0.06)",
                      line_width=0, annotation_text="Rental normal (5–8%)",
                      annotation_font=dict(color="#666", size=8))
        _f3.update_layout(**_dark_layout("RENTAL vs. HOMEOWNER VACANCY RATES  (%)", yformat=".1f"))
        st.plotly_chart(_f3, use_container_width=True, config=_cfg)

    with _r3c2:
        _f4 = go.Figure()
        if prm is not None:
            _pv = prm.dropna()
            _f4.add_trace(go.Bar(
                x=_pv.index, y=_pv.values,
                name="Building Permits (K, SAAR)",
                marker_color="#C8A96E", marker_line_width=0, opacity=0.8,
                hovertemplate="%{y:.0f}K units SAAR<extra></extra>",
            ))
        _f4.update_layout(**_dark_layout("NATIONAL BUILDING PERMITS (SAAR, thousands)", yformat=".0f"))
        _f4.update_layout(bargap=0.1)
        st.plotly_chart(_f4, use_container_width=True, config=_cfg)

    # ── Row 4: Home Prices ────────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin:8px 0 4px;">Home Price Indices</div>', unsafe_allow_html=True)
    _r4c1, _r4c2 = st.columns(2)

    with _r4c1:
        _f_cs = go.Figure()
        if cs is not None:
            _cs_v = cs.dropna()
            _f_cs.add_trace(go.Scatter(
                x=_cs_v.index, y=_cs_v.values,
                name="Case-Shiller National HPI",
                mode="lines", line=dict(color="#C8A96E", width=1.5),
                hovertemplate="%{y:.1f}<extra></extra>",
                fill="tozeroy", fillcolor="rgba(200,169,110,0.08)",
            ))
        _f_cs.update_layout(**_dark_layout("CASE-SHILLER NATIONAL HOME PRICE INDEX  (Jan 2000 = 100)", yformat=".1f"))
        st.plotly_chart(_f_cs, use_container_width=True, config=_cfg)

    with _r4c2:
        _f_mhp = go.Figure()
        if mhp is not None:
            _mp_v = mhp.dropna()
            _f_mhp.add_trace(go.Scatter(
                x=_mp_v.index, y=_mp_v.values / 1000,
                name="Median Home Sale Price ($K)",
                mode="lines", line=dict(color="#C8A96E", width=1.5),
                hovertemplate="$%{y:.0f}K<extra></extra>",
                fill="tozeroy", fillcolor="rgba(200,169,110,0.08)",
            ))
        _f_mhp.update_layout(**_dark_layout("MEDIAN HOME SALE PRICE  ($000s, quarterly)", yformat="$.0f"))
        st.plotly_chart(_f_mhp, use_container_width=True, config=_cfg)

    # ── Source bar ─────────────────────────────────────────────────────────────
    _all_s = [gs10, gs2, cpi, rcpi, rpri, vac, hvac, prm, unem, mtg, cs, mhp]
    _macro_ts = max(
        (s.index[-1].strftime("%b %Y") for s in _all_s if s is not None and len(s) > 0),
        default="—",
    )
    st.markdown(
        f'<div class="src-bar">Sources: Federal Reserve Bank of St. Louis (FRED) &nbsp;&middot;&nbsp; '
        f'GS10 · GS2 · CPIAUCSL · CUSR0000SEHA · CUSR0000SEHC · RRVRUSQ156N · RHVRUSQ156N · '
        f'PERMIT · UNRATE · MORTGAGE30US · CSUSHPISA · MSPUS &nbsp;&middot;&nbsp; '
        f'Latest observation: {_macro_ts} &nbsp;&middot;&nbsp; '
        f'Cap rate benchmark: {_BENCH_CAP}% proxy</div>',
        unsafe_allow_html=True,
    )

# ── Tab 6: News Tracker ────────────────────────────────────────────────────────

with tab_news:
    _NEWS_SOURCES = ["Google News — RPM Living", "Google News — RPM Acquisitions", "Google News — Multifamily CRE",
                     "The Real Deal — Miami", "The Real Deal — National", "The Real Deal — Commercial",
                     "Commercial Observer", "REBusiness Online", "Multifamily Dive",
                     "Yardi Matrix", "RentCafe", "Yield PRO", "Connect CRE"]
    _NEWS_TOPICS  = ["All", "RPM Living", "Multifamily", "Transactions", "Cap Rate", "Rent Growth", "BTR / SFR", "Sun Belt"]

    _n_col1, _n_col2 = st.columns([3, 1])
    with _n_col1:
        _src_filter = st.pills(
            "Source",
            ["All Sources"] + _NEWS_SOURCES,
            selection_mode="single",
            default="All Sources",
            key="news_src",
        )
    with _n_col2:
        _refresh_news = st.button("Refresh Feed", key="news_refresh")

    _topic_filter = st.pills(
        "Topic",
        _NEWS_TOPICS,
        selection_mode="single",
        default="All",
        key="news_topic",
    )

    _TOPIC_KEYWORDS = {
        "RPM Living":    ["RPM Living", "RPM living"],
        "Multifamily":   ["multifamily", "apartment", "rental"],
        "Transactions":  ["acquisition", "transaction", "portfolio", "sale", "sold", "purchased", "acquired"],
        "Cap Rate":      ["cap rate", "capitalization rate", "yield"],
        "Rent Growth":   ["rent growth", "rent increase", "rent decline", "asking rent"],
        "BTR / SFR":     ["build-to-rent", "BTR", "single-family rental", "SFR", "built-to-rent"],
        "Sun Belt":      ["Sun Belt", "Texas", "Florida", "Georgia", "Tennessee", "Carolina", "Atlanta", "Dallas", "Austin", "Miami", "Tampa", "Nashville"],
    }

    @st.cache_data(ttl=3600, show_spinner=False)
    def _load_news():
        return fetch_news()

    with st.spinner("Loading CRE news feed..."):
        _articles = _load_news() if not _refresh_news else fetch_news(force=True)
        if _refresh_news:
            st.cache_data.clear()

    # ── Sort key: time-decayed relevance ─────────────────────────────────────
    # relevance / (1 + days_old) — halves score each day, so 30-day-old RPM
    # (score ~32) ranks below today's fresh CRE articles (score 33+)
    _now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    def _sort_key(a):
        dt = a.get("date")
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        days_old = max(0, (_now_utc - dt).days) if dt else 30
        return a.get("relevance", 0) / (1.0 + days_old)

    # ── RPM Watch ─────────────────────────────────────────────────────────────
    _rpm_hits = sorted([a for a in _articles if a.get("is_rpm")], key=_sort_key, reverse=True)
    if _rpm_hits:
        st.markdown(
            '<div class="news-rpm-banner">RPM Living — In the News</div>',
            unsafe_allow_html=True,
        )
        for _a in _rpm_hits[:5]:
            _dt = _a["date"].strftime("%b %d, %Y") if hasattr(_a["date"], "strftime") else str(_a["date"])[:10]
            st.markdown(f"""
            <div class="news-card rpm-hit">
              <div class="news-card-meta">
                <span class="news-badge-rpm">RPM</span>
                <span class="news-badge-src">{_a['source']}</span>
                {_dt}
              </div>
              <div class="news-card-headline"><a href="{_a['link']}" target="_blank">{_a['title']}</a></div>
              {"<div class='news-card-summary'>" + _a['summary'] + "</div>" if _a['summary'] else ""}
            </div>
            """, unsafe_allow_html=True)

    # ── Filter + main feed ────────────────────────────────────────────────────
    _filtered = _articles
    if _src_filter and _src_filter != "All Sources":
        # Google News articles get sub-source appended (e.g. "Google News — RPM Living / Hoodline")
        # so match on prefix for Google News filters, exact match for others
        if _src_filter.startswith("Google News"):
            _filtered = [a for a in _filtered if a["source"].startswith(_src_filter)]
        else:
            _filtered = [a for a in _filtered if a["source"] == _src_filter]
    if _topic_filter and _topic_filter != "All":
        _kws = _TOPIC_KEYWORDS.get(_topic_filter, [])
        _filtered = [
            a for a in _filtered
            if any(kw.lower() in (a["title"] + " " + a["summary"]).lower() for kw in _kws)
        ]
    _filtered_cre = [a for a in _filtered if a.get("is_cre")]

    _n_total = len(_articles)
    _n_cre   = len(_filtered_cre)
    _n_rpm   = len(_rpm_hits)

    st.markdown(
        f'<div class="sec-lbl">{_n_cre} CRE articles &nbsp;·&nbsp; {_n_rpm} RPM mentions &nbsp;·&nbsp; '
        f'{_n_total} total retrieved &nbsp;·&nbsp; Google News (3 queries) + 10 trade feeds &nbsp;·&nbsp; time-decayed relevance sort &nbsp;·&nbsp; 1-hour cache</div>',
        unsafe_allow_html=True,
    )

    if not _filtered_cre:
        st.markdown('<div class="news-empty">No articles match the current filter.</div>', unsafe_allow_html=True)
    else:
        for _a in sorted(_filtered_cre, key=_sort_key, reverse=True):
            _dt = _a["date"].strftime("%b %d, %Y") if hasattr(_a["date"], "strftime") else str(_a["date"])[:10]
            _rpm_badge = '<span class="news-badge-rpm">RPM</span>' if _a.get("is_rpm") else ""
            st.markdown(f"""
            <div class="news-card{"  rpm-hit" if _a.get("is_rpm") else ""}">
              <div class="news-card-meta">
                {_rpm_badge}<span class="news-badge-src">{_a['source']}</span>{_dt}
              </div>
              <div class="news-card-headline"><a href="{_a['link']}" target="_blank">{_a['title']}</a></div>
              {"<div class='news-card-summary'>" + _a['summary'] + "</div>" if _a['summary'] else ""}
            </div>
            """, unsafe_allow_html=True)

    st.markdown(
        '<div class="src-bar">Sources: Google News (RPM Living · Multifamily CRE — aggregates LinkedIn, press releases, all trade pubs) &nbsp;&middot;&nbsp; '
        'The Real Deal (Miami · National · Commercial) &nbsp;&middot;&nbsp; '
        'Commercial Observer &nbsp;&middot;&nbsp; REBusiness Online &nbsp;&middot;&nbsp; '
        'Multifamily Dive &nbsp;&middot;&nbsp; Yardi Matrix &nbsp;&middot;&nbsp; RentCafe &nbsp;&middot;&nbsp; Connect CRE &nbsp;&middot;&nbsp; '
        'RSS + web scraping &nbsp;&middot;&nbsp; 1-hour cache &nbsp;&middot;&nbsp; Time-decayed relevance sort</div>',
        unsafe_allow_html=True,
    )
