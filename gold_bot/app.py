"""Application entry point: logging, polling loop and graceful shutdown."""
import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler

from . import bale_api, config, db
from .handlers import process_update

logger = logging.getLogger(__name__)

MAX_WORKERS = 20           # bounded thread pool instead of one thread per update
CLEANUP_EVERY_POLLS = 200  # purge expired conversation states every N polling cycles


def setup_logging() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(config.LOG_PATH, maxBytes=5 * 1024 * 1024,
                                backupCount=5, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def run() -> None:
    db.init_db()
    logger.info("Bot '%s' started (%d admins)", config.SHOP_NAME, len(config.ADMIN_IDS))

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def handle_sigterm(*_args):
        logger.info("SIGTERM received, shutting down")
        executor.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    offset = None
    polls = 0
    while True:
        try:
            updates = bale_api.get_updates(offset)
            if updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1
                    executor.submit(process_update, update)
            else:
                time.sleep(2)

            polls += 1
            if polls >= CLEANUP_EVERY_POLLS:
                polls = 0
                executor.submit(db.cleanup_expired_states)
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            executor.shutdown(wait=False)
            break
        except Exception as exc:
            logger.error("Polling loop error: %s", exc)
            time.sleep(5)


def main() -> None:
    problems = config.validate()
    if problems:
        print("Configuration error:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        print("Copy .env.example to .env and fill it in.", file=sys.stderr)
        sys.exit(1)
    setup_logging()
    run()
