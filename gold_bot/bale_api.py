"""Thin client for the Bale Bot API (Telegram-compatible)."""
import json
import logging
import threading
import time

import requests

from . import config
from .utils import redact

logger = logging.getLogger(__name__)

MIN_REQUEST_INTERVAL = 0.25  # seconds between API calls (simple rate limit)
_req_lock = threading.Lock()
_last_req = 0.0


def api(method: str, payload: dict, retries: int = 3) -> dict:
    """Call a Bot API method with rate limiting and exponential-backoff retries."""
    global _last_req
    for attempt in range(retries):
        try:
            with _req_lock:
                elapsed = time.time() - _last_req
                if elapsed < MIN_REQUEST_INTERVAL:
                    time.sleep(MIN_REQUEST_INTERVAL - elapsed)
                _last_req = time.time()
            res = requests.post(f"{config.BASE_URL}/{method}", json=payload, timeout=15)
            data = res.json()
            if not data.get("ok"):
                logger.warning("API %s: %s", method, data.get("description", ""))
            return data
        except Exception as exc:
            # redact(): the exception text contains the URL, i.e. the bot token
            logger.error("API %s attempt %d: %s", method, attempt + 1, redact(exc))
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return {"ok": False}


def send(chat_id, text: str, keyboard=None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    return api("sendMessage", payload)


def send_plain(chat_id, text: str, keyboard=None) -> dict:
    """Send without Markdown parsing (for text that must be shown verbatim)."""
    payload = {"chat_id": chat_id, "text": text or "-"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    return api("sendMessage", payload)


def send_photo(chat_id, file_id: str, caption: str, keyboard=None) -> dict:
    payload = {"chat_id": chat_id, "photo": file_id, "caption": caption, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    return api("sendPhoto", payload)


def answer_cb(callback_id: str, text: str = "", alert: bool = False) -> None:
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = alert
    api("answerCallbackQuery", payload)


def get_updates(offset=None) -> dict:
    """Long-poll for new updates."""
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        res = requests.get(f"{config.BASE_URL}/getUpdates", params=params, timeout=35)
        return res.json()
    except Exception as exc:
        logger.error("Polling failed: %s", redact(exc))
        return {"ok": False, "result": []}
