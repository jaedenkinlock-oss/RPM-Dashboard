import os
from dotenv import load_dotenv

load_dotenv()

# On Streamlit Community Cloud, secrets are injected via st.secrets rather than .env.
# Try to pull the key from there if the env var isn't already set.
try:
    import streamlit as st
    if not os.getenv("FRED_API_KEY") and "FRED_API_KEY" in st.secrets:
        os.environ["FRED_API_KEY"] = st.secrets["FRED_API_KEY"]
except Exception:
    pass

# ── REIT Universe ──────────────────────────────────────────────────────────────

MULTIFAMILY_REITS: dict[str, str] = {
    "EQR":  "Equity Residential",
    "AVB":  "AvalonBay Communities",
    "MAA":  "Mid-America Apartment",
    "CPT":  "Camden Property Trust",
    "UDR":  "UDR Inc",
    "NXRT": "NexPoint Residential Trust",
    "IRT":  "Independence Realty Trust",
    "CSR":  "Centerspace",
    "BRT":  "BRT Realty Trust",
    "ESS":  "Essex Property Trust",
    "VRE":  "Veris Residential",
}

HOMEBUILDER_ADJACENT: dict[str, str] = {
    "DHI":  "D.R. Horton",
    "LEN":  "Lennar Corporation",
    "PHM":  "PulteGroup",
    "TOL":  "Toll Brothers",
    "NVR":  "NVR Inc",
    "MTH":  "Meritage Homes",
    "MHO":  "M/I Homes",
    "TMHC": "Taylor Morrison Home",
}

SFR_BTR: dict[str, str] = {
    "INVH": "Invitation Homes",
    "AMH":  "American Homes 4 Rent",
}

ALL_REITS: dict[str, str] = {**MULTIFAMILY_REITS, **HOMEBUILDER_ADJACENT, **SFR_BTR}

REIT_CATEGORIES: dict[str, str] = {
    **{t: "Multifamily" for t in MULTIFAMILY_REITS},
    **{t: "Homebuilder" for t in HOMEBUILDER_ADJACENT},
    **{t: "SFR/BTR" for t in SFR_BTR},
}

# ── RPM Living Target Markets ──────────────────────────────────────────────────

RPM_MARKETS: dict[str, list[str]] = {
    "tier_1": [
        "Austin, TX", "San Antonio, TX", "Houston, TX", "Dallas, TX",
        "Miami, FL", "Tampa, FL", "Jacksonville, FL",
        "Atlanta, GA", "Nashville, TN",
    ],
    "tier_2": [
        "Charlotte, NC", "Raleigh-Durham, NC", "Columbus, OH",
        "Chicago, IL", "Minneapolis, MN", "Phoenix, AZ",
        "San Diego, CA", "Las Vegas, NV", "Charleston, SC",
    ],
    "tier_3": [
        "Seattle, WA", "Portland, OR", "Denver, CO", "Salt Lake City, UT",
    ],
}

# ── FRED Series ────────────────────────────────────────────────────────────────

FRED_SERIES: dict[str, str] = {
    "treasury_10y":   "GS10",
    "treasury_2y":    "GS2",
    "cpi_all":        "CPIAUCSL",
    "cpi_rent":       "CUSR0000SEHA",
    "vacancy_rental": "RRVRUSQ156N",
    "permits_nat":    "PERMIT",
    "unemployment":   "UNRATE",
}

# ── API Keys ───────────────────────────────────────────────────────────────────

FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# ── Cache / Paths ──────────────────────────────────────────────────────────────

CACHE_DIR: str = "data/cache"
PROCESSED_DIR: str = "data/processed"
LOG_DIR: str = "logs"
CACHE_TTL_HOURS: int = 24

# ── Thresholds (Moghadam layer) ────────────────────────────────────────────────

AFFO_PAYOUT_YELLOW: float = 0.90   # flag: payout ratio > 90%
AFFO_PAYOUT_RED: float = 1.00      # flag: payout ratio > 100%
CAP_SPREAD_WARN_BPS: int = 150     # flag: cap rate spread < 150bps

# ── UI Colors (RPM Living / institutional palette) ─────────────────────────────

RPM_BLACK   = "#1A1A1A"
RPM_DARK    = "#222222"
RPM_GRAY    = "#3D3D3D"
RPM_MID     = "#6B6B6B"
RPM_LIGHT   = "#F5F4F0"
RPM_BORDER  = "#E2E0D8"
RPM_GOLD    = "#C8A96E"
RPM_GOLD_LT = "#F5EAD8"
RPM_GREEN   = "#2D5A3D"
RPM_GREEN_LT= "#E8F2EC"
RPM_RED     = "#8B2A2A"
RPM_RED_LT  = "#F5E8E8"
RPM_AMBER   = "#7A5A1A"
RPM_AMBER_LT= "#F5F0E0"

# Legacy aliases kept for backwards compatibility
DARK_BG     = RPM_BLACK
CARD_BG     = RPM_DARK
ACCENT_BLUE = RPM_GOLD
SIGNAL_GREEN= RPM_GREEN
SIGNAL_RED  = RPM_RED
TEXT_MUTED  = RPM_MID
