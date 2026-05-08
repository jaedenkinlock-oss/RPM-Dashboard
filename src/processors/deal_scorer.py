"""
Multifamily deal scoring engine — RPM Living Investment Intelligence.

Scores any property 0–100 against RPM Living acquisition criteria.
Eight weighted criteria; market presence is a first-class input.

Reference rate: 10Y Treasury ~4.30% (Q1 2026 proxy — Phase 2 will pull live from FRED GS10).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

TREASURY_10Y_REF = 4.30  # update when FRED wired in Phase 2

# ── Market intelligence table ──────────────────────────────────────────────────
# rpm_presence: 0–100 (higher = more established operational footprint)
# supply_risk:  "Low" | "Moderate" | "High"
# market_vacancy, rent_growth: Q4 2024 figures (Yardi Matrix / RealPage)

MARKET_DATA: dict[str, dict] = {
    "Austin, TX":         {"tier": 1, "rpm_presence": 95, "supply_risk": "High",     "market_vacancy": 8.5,  "rent_growth": -3.2, "rpm_note": "Headquarters market — largest Texas presence; deep subcontractor network and leasing staff pipeline"},
    "Dallas, TX":         {"tier": 1, "rpm_presence": 90, "supply_risk": "High",     "market_vacancy": 8.2,  "rent_growth": -2.5, "rpm_note": "Major Texas market — deep operational footprint; finance and tech relocation driving high-income renter base"},
    "Houston, TX":        {"tier": 1, "rpm_presence": 85, "supply_risk": "Moderate", "market_vacancy": 7.5,  "rent_growth": -1.5, "rpm_note": "Strong Texas presence — medical center and energy sector provide recession-resistant demand base"},
    "San Antonio, TX":    {"tier": 1, "rpm_presence": 85, "supply_risk": "High",     "market_vacancy": 9.5,  "rent_growth": -4.0, "rpm_note": "Core Texas market — JBSA military demand floor; deepest value-add discount in the Texas portfolio"},
    "Atlanta, GA":        {"tier": 1, "rpm_presence": 80, "supply_risk": "High",     "market_vacancy": 8.8,  "rent_growth": -2.8, "rpm_note": "Key Southeast hub — institutional-grade operations in place; film/tech/HBCU demand diversification"},
    "Nashville, TN":      {"tier": 1, "rpm_presence": 80, "supply_risk": "High",     "market_vacancy": 9.2,  "rent_growth": -3.5, "rpm_note": "Strong presence — Oracle HQ relocation and HCA Healthcare provide structural high-income demand"},
    "Miami, FL":          {"tier": 1, "rpm_presence": 75, "supply_risk": "Moderate", "market_vacancy": 5.8,  "rent_growth":  2.5, "rpm_note": "Florida coastal — tightest market in RPM universe; international demand floor buffers cyclical risk"},
    "Tampa, FL":          {"tier": 1, "rpm_presence": 75, "supply_risk": "Moderate", "market_vacancy": 7.0,  "rent_growth":  0.5, "rpm_note": "Core Florida market — finance and insurance sector providing premium renter cohort"},
    "Jacksonville, FL":   {"tier": 1, "rpm_presence": 70, "supply_risk": "Low",      "market_vacancy": 8.5,  "rent_growth": -2.0, "rpm_note": "Florida market — navy and financial services anchor; thinnest supply pipeline in the Florida portfolio"},
    "Charlotte, NC":      {"tier": 2, "rpm_presence": 65, "supply_risk": "Moderate", "market_vacancy": 8.0,  "rent_growth": -1.5, "rpm_note": "Growth market — developing presence; banking and university sector drive stable demand"},
    "Raleigh-Durham, NC": {"tier": 2, "rpm_presence": 65, "supply_risk": "Moderate", "market_vacancy": 7.5,  "rent_growth": -1.0, "rpm_note": "Triangle market — Research Triangle Park pharma and life sciences anchor; expanding RPM presence"},
    "Columbus, OH":       {"tier": 2, "rpm_presence": 55, "supply_risk": "Low",      "market_vacancy": 6.5,  "rent_growth":  0.5, "rpm_note": "Midwest growth market — Intel fab investment driving future tech employment; limited presence today"},
    "Chicago, IL":        {"tier": 2, "rpm_presence": 50, "supply_risk": "Low",      "market_vacancy": 6.0,  "rent_growth":  1.0, "rpm_note": "Large metro — establishing institutional presence; positive rent growth in tight core market"},
    "Minneapolis, MN":    {"tier": 2, "rpm_presence": 50, "supply_risk": "Low",      "market_vacancy": 5.5,  "rent_growth":  0.8, "rpm_note": "Midwest stable market — developing presence; medical and financial services anchor"},
    "Phoenix, AZ":        {"tier": 2, "rpm_presence": 60, "supply_risk": "High",     "market_vacancy": 9.0,  "rent_growth": -3.0, "rpm_note": "Growth market — highest US population growth; deep supply wave creating trough acquisition window"},
    "San Diego, CA":      {"tier": 2, "rpm_presence": 55, "supply_risk": "Low",      "market_vacancy": 4.5,  "rent_growth":  2.0, "rpm_note": "West Coast entry — military and biotech demand; tightest vacancy in the RPM Tier 2 universe"},
    "Las Vegas, NV":      {"tier": 2, "rpm_presence": 55, "supply_risk": "Moderate", "market_vacancy": 7.0,  "rent_growth":  0.0, "rpm_note": "Growth market — gaming and logistics diversification adding workforce housing demand"},
    "Charleston, SC":     {"tier": 2, "rpm_presence": 50, "supply_risk": "Low",      "market_vacancy": 7.5,  "rent_growth": -0.5, "rpm_note": "Carolinas growth market — Boeing, Volvo, Mercedes-Benz manufacturing driving blue-collar demand"},
    "Seattle, WA":        {"tier": 3, "rpm_presence": 30, "supply_risk": "Low",      "market_vacancy": 5.5,  "rent_growth":  1.5, "rpm_note": "Expansion watch — evaluating entry strategy; Amazon and Microsoft HQ market with highest median income in RPM universe"},
    "Denver, CO":         {"tier": 3, "rpm_presence": 30, "supply_risk": "Moderate", "market_vacancy": 7.5,  "rent_growth": -1.0, "rpm_note": "Mountain West — monitoring for entry timing; aerospace and healthcare employment diversification"},
    "Portland, OR":       {"tier": 3, "rpm_presence": 25, "supply_risk": "Low",      "market_vacancy": 6.0,  "rent_growth":  0.0, "rpm_note": "Evaluating entry — regulatory and rent control risk elevated; market fundamentals secondary to policy risk"},
    "Salt Lake City, UT": {"tier": 3, "rpm_presence": 25, "supply_risk": "Moderate", "market_vacancy": 6.5,  "rent_growth": -0.5, "rpm_note": "Mountain West growth market — limited presence; tech sector and family formation dynamics differ from Sun Belt"},
    "Other Market":       {"tier": 0, "rpm_presence": 10, "supply_risk": "Unknown",  "market_vacancy": 7.0,  "rent_growth":  0.0, "rpm_note": "Outside RPM target geography — no established operational infrastructure; execution and leasing risk significantly elevated"},
}


@dataclass
class ScoreCriterion:
    name: str
    points_earned: float
    points_max: float
    note: str
    status: str  # "strength" | "caution" | "neutral"


def score_deal(
    market: str,
    asset_class: str,
    units: int,
    asking_price_m: float,
    year_built: int,
    cap_rate_pct: float,
    inplace_rent: float,
    market_rent: float,
    vacancy_pct: float,
    noi_annual_k: Optional[float] = None,
    treasury_rate: float = TREASURY_10Y_REF,
) -> tuple[float, list[ScoreCriterion], str, str]:
    """
    Score a multifamily deal against RPM Living acquisition criteria.

    Returns:
        (total_score 0–100, criteria list, recommendation label, recommendation detail)
    """
    mkt = MARKET_DATA.get(market, MARKET_DATA["Other Market"])
    criteria: list[ScoreCriterion] = []

    # ── 1. Market Fit (20 pts) ─────────────────────────────────────────────────
    tier = mkt["tier"]
    if tier == 1:
        pts, note, st_ = 20, "Tier 1 Core market — within RPM's primary investment geography and operational infrastructure", "strength"
    elif tier == 2:
        pts, note, st_ = 14, "Tier 2 Growth market — within RPM's active expansion footprint; moderate execution risk", "neutral"
    elif tier == 3:
        pts, note, st_ = 7,  "Tier 3 Expansion Watch — RPM evaluating entry; staffing and subcontractor networks not yet established", "caution"
    else:
        pts, note, st_ = 0,  "Outside RPM target geography — no operational infrastructure; acquisition would require full market entry investment", "caution"
    criteria.append(ScoreCriterion("Market Fit", pts, 20, note, st_))

    # ── 2. RPM Operational Presence (15 pts) ──────────────────────────────────
    presence = mkt["rpm_presence"]
    rpm_pts = round(presence / 100 * 15, 1)
    base_note = mkt["rpm_note"]
    if presence >= 80:
        st_ = "strength"
        full_note = f"{base_note}. Presence score {presence}/100: RPM can leverage local leasing velocity, maintenance staff, and vendor relationships to compress value-add timeline."
    elif presence >= 55:
        st_ = "neutral"
        full_note = f"{base_note}. Presence score {presence}/100: operational infrastructure present; some market-specific ramp-up required for optimal execution speed."
    else:
        st_ = "caution"
        full_note = f"{base_note}. Presence score {presence}/100: limited local infrastructure elevates execution risk and extends projected lease-up timeline by 3–6 months."
    criteria.append(ScoreCriterion("RPM Market Presence", rpm_pts, 15, full_note, st_))

    # ── 3. Cap Rate vs. 10Y Treasury Spread (15 pts) ──────────────────────────
    spread_bps = (cap_rate_pct - treasury_rate) * 100
    if spread_bps > 175:
        pts, st_ = 15, "strength"
        note = f"{spread_bps:.0f}bps spread over 10Y Treasury ({treasury_rate:.2f}%) — attractive risk-adjusted entry; meaningful cushion against rate volatility"
    elif spread_bps > 125:
        pts, st_ = 11, "strength"
        note = f"{spread_bps:.0f}bps spread over 10Y — acceptable; spread tightens further on each 25bps rate cut, improving hold-period returns"
    elif spread_bps > 75:
        pts, st_ = 7,  "neutral"
        note = f"{spread_bps:.0f}bps spread over 10Y — compressed; NOI growth must drive returns; limited margin for underwriting error"
    elif spread_bps > 0:
        pts, st_ = 3,  "caution"
        note = f"{spread_bps:.0f}bps spread over 10Y — thin; leverage amplifies downside risk; model stress scenario at +50bps rate move"
    else:
        pts, st_ = 0,  "caution"
        note = f"{spread_bps:.0f}bps — negative spread; cap rate below 10Y Treasury; very difficult to underwrite positive unlevered returns at current pricing"
    criteria.append(ScoreCriterion("Cap Rate vs. Treasury Spread", pts, 15, note, st_))

    # ── 4. Loss-to-Lease / Rent Upside (15 pts) ───────────────────────────────
    if market_rent > 0 and inplace_rent > 0:
        ltl_pct = (market_rent - inplace_rent) / inplace_rent * 100
        annual_upside_per_unit = (market_rent - inplace_rent) * 12
        if ltl_pct > 10:
            pts, st_ = 15, "strength"
            note = f"{ltl_pct:.1f}% loss-to-lease (${inplace_rent:.0f}/mo in-place vs. ${market_rent:.0f}/mo market, +${annual_upside_per_unit:.0f}/unit/yr) — significant mark-to-market rent upside through interior renovation; renovation ROI highly achievable"
        elif ltl_pct > 5:
            pts, st_ = 11, "strength"
            note = f"{ltl_pct:.1f}% loss-to-lease (${inplace_rent:.0f}/mo vs. ${market_rent:.0f}/mo market, +${annual_upside_per_unit:.0f}/unit/yr) — material rent growth achievable through systematic interior renovation program"
        elif ltl_pct > 2:
            pts, st_ = 7,  "neutral"
            note = f"{ltl_pct:.1f}% loss-to-lease (${inplace_rent:.0f}/mo vs. ${market_rent:.0f}/mo market) — moderate upside; renovation capex underwriting should be conservative given compressed spread"
        elif ltl_pct >= 0:
            pts, st_ = 3,  "caution"
            note = f"{ltl_pct:.1f}% loss-to-lease — minimal rent upside; returns are predominantly appreciation- and NOI-margin-dependent"
        else:
            pts, st_ = 0,  "caution"
            note = f"In-place rents {abs(ltl_pct):.1f}% above market — rent premium is inverted; investigate lease structure for concessions or short-term agreements masking effective rent"
    else:
        pts, st_ = 5, "neutral"
        note = "Rent inputs not provided — scored as neutral; enter in-place and market rents for full loss-to-lease analysis"
    criteria.append(ScoreCriterion("Loss-to-Lease Opportunity", pts, 15, note, st_))

    # ── 5. Vacancy vs. Market Average (10 pts) ────────────────────────────────
    mkt_vac = mkt["market_vacancy"]
    delta = vacancy_pct - mkt_vac
    if vacancy_pct > 15:
        pts, st_ = 10, "strength"
        note = f"{vacancy_pct:.1f}% current vacancy — deep value-add; management conversion to RPM platform alone can drive meaningful occupancy improvement without additional capex"
    elif delta > 2:
        pts, st_ = 8, "strength"
        note = f"{vacancy_pct:.1f}% vs. {mkt_vac:.1f}% market average ({delta:+.1f}ppts above market) — underperforming property; operational improvement through RPM's leasing platform represents clear, low-risk NOI recovery path"
    elif abs(delta) <= 2:
        pts, st_ = 5, "neutral"
        note = f"{vacancy_pct:.1f}% vacancy in line with {mkt_vac:.1f}% market average — occupancy improvement requires renovation program or amenity upgrade rather than leasing execution alone"
    else:
        pts, st_ = 3, "neutral"
        note = f"{vacancy_pct:.1f}% below {mkt_vac:.1f}% market average ({delta:.1f}ppts) — well-occupied asset; value-add returns must come from rent growth rather than occupancy improvement"
    criteria.append(ScoreCriterion("Vacancy vs. Market Average", pts, 10, note, st_))

    # ── 6. Asset Vintage / Capex Profile (10 pts) ─────────────────────────────
    age = 2026 - year_built
    if 1990 <= year_built <= 2010:
        pts, st_ = 10, "strength"
        note = f"{year_built} vintage ({age} yrs) — RPM's ideal value-add window; interior renovation at $8K–$15K/unit typical; 8–12% renovation ROI achievable with proper unit turn sequencing"
    elif 2010 < year_built <= 2018:
        pts, st_ = 8, "strength"
        note = f"{year_built} vintage ({age} yrs) — newer product; value creation through amenity refresh ($2K–$6K/unit) and management optimization vs. full interior program"
    elif 1980 <= year_built < 1990:
        pts, st_ = 6, "neutral"
        note = f"{year_built} vintage ({age} yrs) — significant capex required; underwrite $15K–$25K/unit renovation; verify plumbing, electrical, and HVAC system condition in due diligence"
    elif year_built > 2018:
        pts, st_ = 4, "neutral"
        note = f"{year_built} vintage ({age} yrs) — recent construction; core/core-plus underwriting; limited value-add capex opportunity; returns driven by market rent growth and NOI margin"
    else:
        pts, st_ = 3, "caution"
        note = f"{year_built} vintage ({age} yrs) — pre-1980 product; potential deferred maintenance on structural systems; budget for partial or full systems replacement in renovation underwriting"
    criteria.append(ScoreCriterion("Asset Vintage / Capex Profile", pts, 10, note, st_))

    # ── 7. Supply Pipeline Risk (10 pts) ──────────────────────────────────────
    supply_risk = mkt["supply_risk"]
    rent_growth = mkt["rent_growth"]
    rg_str = f"{rent_growth:+.1f}% YOY rent growth (Q4 2024)"
    if supply_risk == "Low":
        pts, st_ = 10, "strength"
        note = f"Low supply pipeline in {market} — limited new deliveries protect in-place rents; {rg_str}; underwrite for stable to positive rent performance"
    elif supply_risk == "Moderate":
        pts, st_ = 6, "neutral"
        note = f"Moderate supply pipeline in {market} — {rg_str}; underwrite conservatively for 2025–26 lease-up; model 12–18 months of flat-to-negative rent before recovery"
    elif supply_risk == "High":
        pts, st_ = 2, "caution"
        note = f"High supply pipeline in {market} — {rg_str}; underwrite flat rents for 18–24 months; model careful lease-up sequencing with renovation; supply absorption critical path"
    else:
        pts, st_ = 4, "neutral"
        note = f"Supply pipeline data not available for {market} — conduct independent CoStar/Yardi analysis before finalizing underwriting assumptions"
    criteria.append(ScoreCriterion("Supply Pipeline Risk", pts, 10, note, st_))

    # ── 8. Asset Scale / G&A Efficiency (5 pts) ───────────────────────────────
    if 200 <= units <= 400:
        pts, st_ = 5, "strength"
        note = f"{units} units — RPM's optimal G&A efficiency range (200–400); on-site staffing model is fully leveraged; property management fee as % of revenue is most favorable"
    elif 100 <= units < 200 or 400 < units <= 600:
        pts, st_ = 4, "neutral"
        note = f"{units} units — workable; slightly outside optimal efficiency range; staffing model will work but per-unit G&A allocation is marginally higher"
    elif units > 600:
        pts, st_ = 3, "neutral"
        note = f"{units} units — large asset; verify on-site maintenance team requirement; may justify dedicated assistant manager; evaluate in context of RPM's regional portfolio"
    else:
        pts, st_ = 1, "caution"
        note = f"{units} units — small asset; fixed G&A costs compress NOI margin; evaluate only in portfolio context or if acquisition basis is deeply discounted"
    criteria.append(ScoreCriterion("Asset Scale / G&A Efficiency", pts, 5, note, st_))

    # ── Totals and recommendation ──────────────────────────────────────────────
    total = round(min(100.0, sum(c.points_earned for c in criteria)), 1)

    if total >= 75:
        rec = "Advance to Due Diligence"
        rec_detail = (
            "Strong thesis alignment across market, operations, and financial structure. "
            "Recommend proceeding to full underwriting package and site visit. "
            "Priority items for due diligence: physical inspection of unit conditions, "
            "submarket rent comp validation, and review of in-place lease expirations."
        )
    elif total >= 55:
        rec = "Conditional — Deeper Review Required"
        rec_detail = (
            "Moderate thesis fit with identifiable risk factors (flagged above). "
            "Recommend targeted diligence on the lowest-scoring criteria before submitting LOI. "
            "Re-score after addressing flagged items; this deal may improve materially with additional information."
        )
    elif total >= 35:
        rec = "Monitor — Below Threshold in Current Form"
        rec_detail = (
            "Below RPM's acquisition threshold at current pricing or market conditions. "
            "Document property for off-market follow-up. Revisit if: (a) pricing improves by 10%+, "
            "(b) supply pipeline data improves, or (c) market conditions stabilize."
        )
    else:
        rec = "Pass"
        rec_detail = (
            "Significant misalignment with RPM investment criteria across multiple dimensions. "
            "Not recommended for pursuit without material re-pricing, market change, or "
            "identification of a value driver not captured in this analysis."
        )

    return total, criteria, rec, rec_detail
