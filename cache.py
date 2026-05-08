from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

from config import CACHE_DIR, CACHE_TTL_HOURS
from src.utils.logger import get_logger

logger = get_logger(__name__)

_cache_dir = Path(CACHE_DIR)
_cache_dir.mkdir(parents=True, exist_ok=True)


def _today_path(key: str) -> Path:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    return _cache_dir / f"{key}_{date_str}.parquet"


def read_cache(key: str, ttl_hours: int = CACHE_TTL_HOURS) -> Optional[pd.DataFrame]:
    """Return cached DataFrame if a fresh file exists, else None."""
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)

    candidates = sorted(_cache_dir.glob(f"{key}_*.parquet"), reverse=True)
    for path in candidates:
        mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        if mtime >= cutoff:
            try:
                df = pd.read_parquet(path)
                logger.info("Cache hit: %s (%s)", path.name, mtime.strftime("%Y-%m-%d %H:%M UTC"))
                return df
            except Exception as exc:
                logger.warning("Cache read failed for %s: %s", path.name, exc)
    return None


def write_cache(key: str, df: pd.DataFrame) -> None:
    """Write DataFrame to a date-stamped parquet file."""
    path = _today_path(key)
    try:
        df.to_parquet(path, index=True, compression="snappy")
        logger.info("Cache written: %s (%d rows)", path.name, len(df))
    except Exception as exc:
        logger.error("Cache write failed for %s: %s", path.name, exc)


def cache_timestamp(key: str) -> Optional[str]:
    """Return ISO timestamp string of most recent cache file, or None."""
    candidates = sorted(_cache_dir.glob(f"{key}_*.parquet"), reverse=True)
    if not candidates:
        return None
    mtime = datetime.utcfromtimestamp(candidates[0].stat().st_mtime)
    return mtime.strftime("%Y-%m-%d %H:%M UTC")
