"""Update dispatching."""
import logging

from .callbacks import handle_callback
from .messages import handle_message

logger = logging.getLogger(__name__)


def process_update(update: dict) -> None:
    """Handle one update; never raises, so a bad update cannot kill a worker thread."""
    try:
        if "message" in update:
            handle_message(update["message"])
        elif "channel_post" in update:
            handle_message(update["channel_post"])
        elif "callback_query" in update:
            handle_callback(update["callback_query"])
    except Exception:
        logger.exception("Update handler failed")
