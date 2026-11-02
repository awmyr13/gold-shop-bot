"""Entry point for incoming messages: routes them to the price, admin or customer handler."""
import logging

from .. import bale_api as bale
from .. import config, db
from ..keyboards import BTN_CANCEL, kb_remove
from ..pricing import update_price_from_channel
from .admin import admin_menu, handle_admin_message
from .customer import handle_customer_message

logger = logging.getLogger(__name__)


def _is_price_channel(chat: dict) -> bool:
    configured = config.GOLD_PRICE_CHANNEL
    if not configured:
        return False
    username = chat.get("username") or ""
    return str(chat.get("id")) == configured or f"@{username}" == configured


def handle_message(message: dict) -> None:
    chat = message["chat"]
    chat_id = chat["id"]
    # Bale puts a channel post's text in `caption` when it has a photo.
    text = (message.get("text") or message.get("caption") or "").strip()

    # Posts in the price channel update the stored price (no sender info needed).
    if _is_price_channel(chat):
        if text:
            update_price_from_channel(text)
        return

    sender = message.get("from")
    if not sender:
        return
    user_id = sender["id"]
    user_name = sender.get("first_name", "کاربر")
    is_admin = user_id in config.ADMIN_IDS

    if text == BTN_CANCEL:
        db.clear_user_state(user_id)
        if is_admin:
            admin_menu(chat_id)
        else:
            bale.send(chat_id, "عملیات لغو شد.", kb_remove())
        return

    if is_admin:
        handle_admin_message(message, user_id, chat_id, text)
    else:
        handle_customer_message(message, user_id, user_name, chat_id, text)
