"""Channel product posts: caption composition, editing and the "sold" mark."""
import json
import logging
from typing import Tuple

from . import bale_api as bale
from . import config, db
from .keyboards import kb_product, kb_product_sold

logger = logging.getLogger(__name__)

PHOTO_CAPTION_LIMIT = 1024  # Bale/Telegram limit for photo captions
TEXT_LIMIT = 4096           # limit for plain text messages
TAIL_RESERVE = 60           # room kept for the id line and the "sold" line


def caption_limit(has_photo: bool) -> int:
    return PHOTO_CAPTION_LIMIT if has_photo else TEXT_LIMIT


def max_user_caption_length(has_photo: bool) -> int:
    """Longest caption an admin may type, leaving room for the bot's own lines."""
    return caption_limit(has_photo) - TAIL_RESERVE


def compose_caption(p: dict) -> str:
    """Final post text = admin's text + product number + (if sold) the sold line."""
    tail = ""
    if p.get("num"):
        tail += f"\n\n🔖 شناسه: #{p['num']}"
    if p.get("sold"):
        tail += f"\n\n{config.SOLD_LINE}"
    limit = caption_limit(p.get("has_photo")) - len(tail)
    return (p.get("caption") or "")[:limit] + tail


def _chat_ref(value):
    """Channel ids may be numeric ids or @usernames."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def refresh_channel_post(product: dict) -> dict:
    """Edit the channel post (caption + buttons) to match the product's current state."""
    if not product.get("channel_id") or not product.get("message_id"):
        return {"ok": False, "description": "پست کانال ثبت نشده"}
    keyboard = kb_product_sold(product["pid"]) if product.get("sold") else kb_product(product["pid"])
    payload = {
        "chat_id": _chat_ref(product["channel_id"]),
        "message_id": int(product["message_id"]),
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(keyboard),
    }
    if product.get("has_photo"):
        method = "editMessageCaption"
        payload["caption"] = compose_caption(product)
    else:
        method = "editMessageText"
        payload["text"] = compose_caption(product)
    res = bale.api(method, payload)
    if not res.get("ok") and "not modified" in str(res.get("description", "")).lower():
        res = {"ok": True}  # nothing to change is not an error
    return res


def mark_product_sold(product: dict) -> Tuple[bool, str]:
    """Edit the post to show it is sold. Returns (success, message for the admin)."""
    if product.get("sold"):
        return False, "این محصول قبلاً فروخته شده."
    if not product.get("channel_id") or not product.get("message_id"):
        return False, "این محصول به پست کانال وصل نیست. پست رو از کانال برای ربات فوروارد کن."
    res = refresh_channel_post({**product, "sold": 1})
    if not res.get("ok"):
        desc = str(res.get("description", ""))[:100]
        logger.warning("Marking %s as sold failed: %s", product["pid"], desc)
        return False, f"ویرایش پست ناموفق بود: {desc}"
    db.mark_sold(product["pid"])
    return True, "✅ پست کانال ویرایش شد و دکمه خرید برداشته شد."
