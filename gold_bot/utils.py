"""Small helpers shared across the bot."""
import re
import uuid

from . import config

# Persian and Arabic-Indic digits, plus the Persian decimal separator.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "0123456789" "0123456789" ".")


def fa_to_en(text) -> str:
    """Convert Persian/Arabic digits to ASCII digits."""
    if not text:
        return ""
    return str(text).translate(_DIGITS)


def fmt(n) -> str:
    """Format a number with thousands separators."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def md_safe(s) -> str:
    """Strip Markdown control characters from user-provided text."""
    return re.sub(r"[*_`\[\]]", "", str(s or ""))


def make_pid() -> str:
    return f"P{uuid.uuid4().hex[:8].upper()}"


def make_order_id() -> str:
    return f"ORD-{uuid.uuid4().hex[:10].upper()}"


def redact(text) -> str:
    """Hide secrets (bot token, price API URL) before text is written to a log.

    Exceptions raised by ``requests`` include the full request URL, which for the
    Bale API contains the bot token.
    """
    out = str(text)
    for secret in (config.BOT_TOKEN, config.PRICE_API_URL):
        if secret:
            out = out.replace(secret, "***")
    return out
