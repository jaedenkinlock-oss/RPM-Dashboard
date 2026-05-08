"""
SEC EDGAR FFO/AFFO scraper — Phase 2.
Uses EDGAR full-text search API to extract FFO from 10-K/10-Q press releases.
Ground truth source to replace yfinance FFO proxy.
"""
# TODO Phase 2: EDGAR full-text search API
# Endpoint: https://efts.sec.gov/LATEST/search-index?q=%22funds+from+operations%22&dateRange=custom&startdt=...


def fetch_ffo_from_edgar(ticker: str, cik: str):
    raise NotImplementedError("EDGAR fetcher implemented in Phase 2")
