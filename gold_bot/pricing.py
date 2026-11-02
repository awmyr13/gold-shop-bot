"""Gold price resolution and product price calculation.

The 18k price per gram comes from the first available source:
  1. an external JSON API (always freshest),
  2. the latest price posted in the shop's Bale price channel (valid for 2 hours),
  3. a price entered manually by an admin (permanent fallback).
"""
import logging
import re
import time
from typing import Optional, Tuple

import requests

from . import config, db
from .utils import fa_to_en, fmt, redact

logger = logging.getLogger(__name__)

CHANNEL_PRICE_TTL = 7200       # seconds a channel price stays valid
MIN_PLAUSIBLE_PRICE = 100_000  # ignore smaller numbers matched by accident

_CHANNEL_PRICE_RE = re.compile(r"(?:طلا|طلای)\s*18\s*عیار\s*[:\-–—]?\s*([\d/,]+)")


def fetch_price_from_api() -> Optional[int]:
    """Ask the external price API; return the 18k gram price or None."""
    url = config.PRICE_API_URL
    if not url:
        logger.debug("PRICE_API_URL is not set; skipping the price API")
        return None
    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            logger.warning("Price API returned HTTP %s", res.status_code)
            return None
        data = res.json()
        logger.debug("Price API payload: %s", data)
        raw_price = data.get(config.PRICE_API_FIELD)
        if not raw_price:
            logger.warning("Price API response has no %r field", config.PRICE_API_FIELD)
            return None
        return int(raw_price)
    except Exception as exc:  # network errors, bad JSON, non-numeric price
        logger.error("Price API request failed: %s", redact(exc))
        return None


def update_price_from_channel(text: str) -> Optional[int]:
    """Parse a price post such as 'طلای ۱۸ عیار: ۱۸,۵۰۰,۰۰۰' and store it."""
    try:
        normalized = fa_to_en(text).replace("،", ",").replace("٬", ",")
        match = _CHANNEL_PRICE_RE.search(normalized)
        if match:
            price = int(re.sub(r"[^\d]", "", match.group(1)))
            if price > MIN_PLAUSIBLE_PRICE:
                db.set_setting("channel_gold_price", str(price))
                db.set_setting("channel_price_time", str(int(time.time())))
                logger.info("Price updated from channel: %s", fmt(price))
                return price
    except Exception as exc:
        logger.error("Could not parse channel price: %s", exc)
    return None


def resolve_price() -> Tuple[int, str]:
    """Return (price, human-readable source). Price is 0 when nothing is available."""
    api_price = fetch_price_from_api()
    if api_price and api_price > 0:
        db.set_setting("api_gold_price", str(api_price))  # shown in the admin panel
        db.set_setting("api_price_time", str(int(time.time())))
        return api_price, "🌐 API"

    cached = int(db.get_setting("channel_gold_price") or 0)
    age = int(time.time()) - int(db.get_setting("channel_price_time") or 0)
    if cached > 0 and age < CHANNEL_PRICE_TTL:
        return cached, f"📢 کانال ({age // 60} دقیقه پیش)"

    manual = int(db.get_setting("manual_gold_price") or 0)
    if manual > 0:
        return manual, "✏️ دستی"

    return 0, "❌ تنظیم نشده"


def get_gold_price() -> int:
    return resolve_price()[0]


def calculate_price(weight: float, wage_pct: float, gold_price: int) -> dict:
    """Final price = raw gold value + making charge (a percentage of the raw value)."""
    base = round(weight * gold_price)
    wage = round(base * wage_pct / 100)
    return {"gold_price": gold_price, "base": base, "wage": wage, "total": base + wage}
