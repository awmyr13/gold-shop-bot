"""Application settings, read from environment variables (optionally via a .env file)."""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> List[int]:
    """Parse a comma-separated list of numeric ids, ignoring anything invalid."""
    parts = (p.strip() for p in (raw or "").split(","))
    return [int(p) for p in parts if p.isdigit()]


# --- Secrets (required) -------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS", ""))

# --- External gold price API (optional) ---------------------------------------
# TABAN_API_URL is accepted as a backwards-compatible alias of PRICE_API_URL.
PRICE_API_URL = os.getenv("PRICE_API_URL") or os.getenv("TABAN_API_URL")
PRICE_API_FIELD = os.getenv("PRICE_API_FIELD", "YekGram18")  # JSON key: price of 1g, 18k

# --- Shop details used in messages and in the product post template -----------
SHOP_NAME = os.getenv("SHOP_NAME", "My Gold Shop")
SHOP_PHONE = os.getenv("SHOP_PHONE", "")
SHOP_LANDLINE = os.getenv("SHOP_LANDLINE", "")
SHOP_ADDRESS = os.getenv("SHOP_ADDRESS", "")
SHOP_SHIPPING_NOTE = os.getenv("SHOP_SHIPPING_NOTE", "")
SHOP_NOTE = os.getenv("SHOP_NOTE", "")
SHOP_CONTACT_HANDLE = os.getenv("SHOP_CONTACT_HANDLE", "")
SHOP_ETAA_URL = os.getenv("SHOP_ETAA_URL", "")
SHOP_CHANNEL = os.getenv("SHOP_CHANNEL", "")

# Channel whose posts contain the daily gold price (e.g. "@my_price_channel").
GOLD_PRICE_CHANNEL = os.getenv("GOLD_PRICE_CHANNEL", "")

# --- Behaviour ----------------------------------------------------------------
PRODUCT_NUM_START = int(os.getenv("PRODUCT_NUM_START", "1"))  # first public product number
PAGE_SIZE = 8                                                  # products per admin list page
SOLD_LINE = "🔴 *فروخته شد* 🔴"                                 # appended to sold posts

# --- Storage ------------------------------------------------------------------
# Inside the production container /app/backups already exists and is a mounted volume,
# so it is picked up automatically. Elsewhere data goes to ./data.
_default_data_dir = "/app/backups" if os.path.isdir("/app/backups") else "data"
DATA_DIR = os.getenv("DATA_DIR", _default_data_dir)
DB_PATH = os.path.join(DATA_DIR, "gold_bot.db")
LOG_PATH = os.path.join(DATA_DIR, "bot.log")

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"


def validate() -> List[str]:
    """Return a list of human-readable configuration problems (empty if all is well)."""
    problems = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN is not set")
    if not ADMIN_IDS:
        problems.append("ADMIN_IDS is empty (comma-separated numeric Bale user ids)")
    return problems
