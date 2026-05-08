"""
CRE news RSS aggregator + TRD full-text scraper + Google News.
Standard RSS feeds, Google News RPM/CRE queries, TRD full-text for deeper RPM detection.
1-hour parquet cache.
"""
from datetime import datetime, timezone
import re
import feedparser
import requests
from bs4 import BeautifulSoup

from src.utils.cache import read_cache, write_cache
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TTL = 1  # hours

_RPM_KEYWORDS = ["RPM Living", "RPM living", "rpm living"]

# ── Relevance keyword table ────────────────────────────────────────────────────
# Organised in tiers; title hits count double.
_KEYWORD_WEIGHTS: dict[str, int] = {
    # Tier 1 — RPM identity (non-"Living" shorthand caught here too)
    "RPM Living":        100,
    "Jason Berkowitz":    80,   # RPM founder/CEO

    # Tier 2 — deal signals (most actionable content)
    "value-add":          18,
    "loss-to-lease":      16,
    "build-to-rent":      15,
    "BTR":                12,
    "acquired":           12,
    "acquisition":        12,
    "joint venture":      10,
    "ground-up":          10,
    "lease-up":           10,
    "development":         8,
    "disposition":         8,
    "refinancing":         7,
    "recapitalization":    7,
    "transaction":         6,
    "closed":              5,
    "portfolio":           5,
    "per unit":            8,   # deal pricing signal

    # Tier 3 — asset type
    "multifamily":        12,
    "apartment":           8,
    "workforce housing":   9,
    "affordable housing":  7,
    "garden-style":        6,
    "mid-rise":            5,
    "high-rise":           4,
    "mixed-use":           4,
    "townhome":            5,
    "SFR":                 7,
    "single-family rental": 7,

    # Tier 4 — RPM target markets (each adds signal)
    "Sun Belt":           10,
    "Austin":              7,
    "Dallas":              7,
    "Houston":             7,
    "San Antonio":         7,
    "Miami":               7,
    "Tampa":               7,
    "Jacksonville":        6,
    "Atlanta":             7,
    "Nashville":           7,
    "Charlotte":           6,
    "Raleigh":             6,
    "Kansas City":         6,
    "Columbus":            5,
    "Chicago":             5,
    "Minneapolis":         5,
    "Phoenix":             6,
    "Denver":              5,
    "Seattle":             5,
    "Las Vegas":           5,
    "Charleston":          5,
    "Texas":               5,
    "Florida":             5,
    "Georgia":             4,
    "Tennessee":           4,

    # Tier 5 — financial / performance signals
    "cap rate":           10,
    "NOI":                 8,
    "rent growth":        10,
    "vacancy":             7,
    "occupancy":           6,
    "absorption":          8,
    "net absorption":      9,
    "supply":              5,
    "pipeline":            6,
    "deliveries":          6,
    "affordability":       6,
    "interest rate":       5,
    "SOFR":                5,
    "mortgage":            4,
    "cost basis":          7,

    # Tier 6 — industry ecosystem
    "REIT":                7,
    "NMHC":                8,
    "CoStar":              5,
    "Yardi":               5,
    "RealPage":            5,
    "Berkadia":            5,
    "CBRE":                4,
    "JLL":                 4,
    "Walker & Dunlop":     4,
    "Newmark":             4,
    "Greystar":            5,
    "Sentinel":            6,   # seller in KC deal; flag future Sentinel transactions
    "Integra":             6,   # seller in Miami deal

    # Tier 7 — general CRE (lowest relevance; keeps things from being buried)
    "residential":         3,
    "commercial real estate": 4,
    "rental":              3,
    "REIT":                7,
}

# Minimum score for an article to be considered CRE-relevant
_CRE_THRESHOLD = 6

# Keywords whose presence in a title/summary actively reduces score
# (penalise off-topic content that slips through)
_NEGATIVE_WEIGHTS: dict[str, int] = {
    "office space":       -6,
    "retail":             -4,
    "industrial":         -4,
    "hotel":              -4,
    "data center":        -6,
    "self-storage":       -3,
    "condo":              -3,   # mild; condos share some keywords with MF
}

# Standard RSS feeds
_FEEDS = [
    ("The Real Deal — Miami",       "https://therealdeal.com/miami/feed/"),
    ("The Real Deal — National",    "https://therealdeal.com/national/feed/"),
    ("The Real Deal — Commercial",  "https://therealdeal.com/category/commercial/feed/"),
    ("Commercial Observer",         "https://commercialobserver.com/feed/"),
    ("REBusiness Online",           "https://rebusinessonline.com/feed/"),
    ("Multifamily Dive",            "https://www.multifamilydive.com/feeds/news/"),
    ("Connect CRE",                 "https://www.connectcre.com/feed/"),
    ("Yardi Matrix",                "https://www.yardimatrix.com/blog/feed/"),
    ("RentCafe",                    "https://rentcafe.com/blog/feed/"),
    ("Yield PRO",                   "https://yieldpro.com/feed/"),
]

# Google News RSS — four queries for broad RPM + CRE coverage.
# Tuple: (label, url, force_rpm)
# force_rpm=True: all articles from that query are presumed to be about RPM Living
# (used for targeted searches where any result is RPM-relevant).
# Google's index is inconsistent across variants, so overlapping queries are needed.
_GOOGLE_NEWS_FEEDS = [
    ("Google News — RPM Living",
     'https://news.google.com/rss/search?q=%22RPM+Living%22&hl=en-US&gl=US&ceid=US:en',
     True),
    ("Google News — RPM Acquisitions",
     'https://news.google.com/rss/search?q=%22RPM%22+multifamily+acquired+OR+purchased+OR+acquires+OR+sells&hl=en-US&gl=US&ceid=US:en',
     True),
    ("Google News — Multifamily CRE",
     'https://news.google.com/rss/search?q=multifamily+%22Sun+Belt%22+apartment&hl=en-US&gl=US&ceid=US:en',
     False),
]

# TRD search URLs to scrape for RPM Living mentions beyond the RSS window
_TRD_RPM_SEARCH_URLS = [
    "https://therealdeal.com/miami/?s=RPM+Living",
]
_TRD_BASE = "https://therealdeal.com"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _relevance_score(title: str, summary: str) -> int:
    t_lo = title.lower()
    s_lo = summary.lower()
    both = t_lo + " " + s_lo
    score = 0

    # Keyword weights — title hits count 3×, summary hits count 1×
    for kw, weight in _KEYWORD_WEIGHTS.items():
        kw_l = kw.lower()
        if kw_l in t_lo:
            score += weight * 3
        elif kw_l in s_lo:
            score += weight

    # Negative signals (check combined text, subtract once)
    for kw, penalty in _NEGATIVE_WEIGHTS.items():
        if kw.lower() in both:
            score += penalty  # penalty is already negative

    # Co-occurrence bonus: deal verb + asset type in same article = more actionable
    _deal_verbs = {"acquired", "purchased", "acquires", "buys", "sells", "closed", "traded"}
    _asset_types = {"multifamily", "apartment", "build-to-rent", "btr", "workforce housing"}
    has_deal_verb  = any(v in both for v in _deal_verbs)
    has_asset_type = any(a in both for a in _asset_types)
    if has_deal_verb and has_asset_type:
        score += 15

    # Dollar-amount bonus: article mentions a deal price ($XM or $XB)
    if re.search(r"\$\s*\d+\.?\d*\s*[mb]illion|\$\s*\d+[mb]", both, re.IGNORECASE):
        score += 10

    # Unit-count bonus: article mentions unit/apartment count (e.g. "350-unit", "350 units")
    if re.search(r"\b\d{2,4}[\s-]units?\b|\b\d{2,4}[\s-]unit\b", both, re.IGNORECASE):
        score += 8

    # RPM market + deal = highly targeted signal
    _rpm_markets = {"austin", "dallas", "houston", "san antonio", "miami", "tampa",
                    "jacksonville", "atlanta", "nashville", "charlotte", "raleigh",
                    "kansas city", "phoenix", "las vegas", "denver", "seattle"}
    if has_deal_verb and any(m in both for m in _rpm_markets):
        score += 10

    return max(score, 0)


def _fetch_article_text(url: str) -> str:
    """Fetch and extract article body text. Returns empty string on failure."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for sel in ["article", ".article-body", ".post-content", ".entry-content", "main"]:
            body = soup.select_one(sel)
            if body:
                text = body.get_text(separator=" ", strip=True)
                if len(text) > 150:
                    return text[:2000]
    except Exception:
        pass
    return ""


def _make_article(source: str, title: str, summary: str, link: str,
                  date: datetime, full_text: str = "") -> dict:
    combined = title + " " + summary + " " + full_text
    is_rpm   = any(kw.lower() in combined.lower() for kw in _RPM_KEYWORDS)
    score    = _relevance_score(title, summary + " " + full_text[:600])
    is_cre   = is_rpm or score >= _CRE_THRESHOLD
    return {
        "source":    source,
        "title":     title,
        "summary":   summary[:400] if summary else full_text[:400],
        "link":      link,
        "date":      date,
        "is_rpm":    is_rpm,
        "is_cre":    is_cre,
        "relevance": score + (1000 if is_rpm else 0),
    }


# ── Fetchers ──────────────────────────────────────────────────────────────────

def _fetch_feed(source_name: str, url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as exc:
        logger.error("RSS fetch failed — %s: %s", source_name, exc)
        return []

    is_trd = "Real Deal" in source_name
    articles = []
    for entry in feed.entries:
        title   = getattr(entry, "title",   "").strip()
        summary = getattr(entry, "summary", "").strip()
        link    = getattr(entry, "link",    "").strip()
        if not title or not link:
            continue

        # For TRD, fetch full article text to catch RPM mentions below the fold
        full_text = ""
        if is_trd:
            full_text = _fetch_article_text(link)

        articles.append(_make_article(source_name, title, summary, link, _parse_date(entry), full_text))
    return articles


def _fetch_google_news(label: str, url: str, force_rpm: bool = False) -> list[dict]:
    """
    Fetch a Google News RSS feed.
    Google News titles are formatted as "Article Title - Publication Name".
    We strip the publication suffix and use it as a sub-source label.
    force_rpm=True: all articles are tagged is_rpm (used for targeted RPM queries
    where any result is presumed to be about RPM Living — catches articles that
    say 'RPM' without 'Living', e.g. press release shorthand).
    """
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as exc:
        logger.error("Google News fetch failed — %s: %s", label, exc)
        return []

    articles = []
    for entry in feed.entries:
        raw_title = getattr(entry, "title", "").strip()
        link      = getattr(entry, "link",  "").strip()
        summary   = getattr(entry, "summary", "").strip()
        if not raw_title or not link:
            continue

        # Split "Article Title - Publication Name" → extract pub as sub-source
        parts = re.split(r"\s+[-–]\s+", raw_title)
        if len(parts) >= 2:
            title  = " - ".join(parts[:-1]).strip()
            pub    = parts[-1].strip()
            source = f"{label} / {pub}"
        else:
            title  = raw_title
            source = label

        if "<" in summary:
            summary = BeautifulSoup(summary, "html.parser").get_text(strip=True)

        art = _make_article(source, title, summary[:400], link, _parse_date(entry))
        if force_rpm:
            art["is_rpm"]    = True
            art["is_cre"]    = True
            art["relevance"] = max(art["relevance"], 1000)
        articles.append(art)

    logger.info("Google News fetched — %s: %d articles", label, len(articles))
    return articles


def _scrape_trd_rpm_search() -> list[dict]:
    """
    Scrapes TRD Miami search results for 'RPM Living'.
    TRD wraps each <article> in a parent <a href>, so we select those anchor tags.
    Fetches full article text for each result to get deal details.
    """
    seen:     set[str]   = set()
    articles: list[dict] = []

    for search_url in _TRD_RPM_SEARCH_URLS:
        try:
            r = requests.get(search_url, headers=_HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")
        except Exception as exc:
            logger.error("TRD search scrape failed — %s: %s", search_url, exc)
            continue

        # TRD structure: <a href="/miami/..."><article>...</article></a>
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            # Only take paths that look like article URLs (year in path)
            if not any(f"/{y}/" in href for y in ["2024", "2025", "2026", "2023"]):
                continue
            if not anchor.find("article"):
                continue

            link = (_TRD_BASE + href) if href.startswith("/") else href
            if link in seen:
                continue

            article_el = anchor.find("article")
            title_el   = article_el.select_one("h2, h3, [class*='title']") if article_el else None
            date_el    = article_el.select_one("[class*='date'] span, time") if article_el else None

            title = title_el.get_text(strip=True) if title_el else anchor.get_text(strip=True)[:120]
            if not title:
                continue

            date_str = date_el.get_text(strip=True) if date_el else ""
            try:
                date = datetime.strptime(date_str, "%B %d, %Y").replace(tzinfo=timezone.utc) if date_str else datetime.now(timezone.utc)
            except Exception:
                date = datetime.now(timezone.utc)

            seen.add(link)
            full_text = _fetch_article_text(link)
            summary   = full_text[:400] if full_text else ""

            art = _make_article("The Real Deal — Miami", title, summary, link, date, full_text)
            # Only hard-flag as RPM if the URL slug or full text actually confirms it
            if "rpm" in link.lower():
                art["is_rpm"]    = True
                art["relevance"] = max(art["relevance"], 1000)
            art["is_cre"] = True
            articles.append(art)

    logger.info("TRD RPM search: %d articles found", len(articles))
    return articles


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_news(force: bool = False) -> list[dict]:
    """Return combined, deduplicated article list; 1-hour parquet cache."""
    import pandas as pd

    key = "news_feed"
    if not force:
        cached = read_cache(key, ttl_hours=_TTL)
        if cached is not None and not cached.empty:
            records = cached.to_dict("records")
            for rec in records:
                if isinstance(rec.get("date"), str):
                    try:
                        rec["date"] = datetime.fromisoformat(rec["date"])
                    except Exception:
                        rec["date"] = datetime.now(timezone.utc)
                rec["is_rpm"]    = bool(rec.get("is_rpm"))
                rec["is_cre"]    = bool(rec.get("is_cre"))
                rec["relevance"] = int(rec.get("relevance", 0))
            return records

    all_articles: list[dict] = []
    seen_links:   set[str]   = set()

    def _add(arts: list[dict]):
        for art in arts:
            if art["link"] not in seen_links:
                seen_links.add(art["link"])
                all_articles.append(art)

    # 1. Google News — RPM Living (highest priority; covers LinkedIn, press releases, all pubs)
    for label, url, force_rpm in _GOOGLE_NEWS_FEEDS:
        _add(_fetch_google_news(label, url, force_rpm=force_rpm))

    # 2. TRD full-text search for RPM Living (catches articles off the RSS window)
    _add(_scrape_trd_rpm_search())

    # 3. Standard RSS feeds
    for source_name, url in _FEEDS:
        _add(_fetch_feed(source_name, url))

    if not all_articles:
        return []

    df = pd.DataFrame(all_articles)
    df["date"] = df["date"].astype(str)
    write_cache(key, df)
    return all_articles
