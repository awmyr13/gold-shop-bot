"""SQLite persistence layer: settings, products, orders, conversation state, users."""
import json
import logging
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator, List, Optional

from . import config
from .utils import fa_to_en

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 3600


def get_conn() -> sqlite3.Connection:
    """Open a new connection (one per call, so threads never share one)."""
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Connection that commits on success and is always closed."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables, apply lightweight migrations and seed default settings."""
    os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)), exist_ok=True)
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS products (
            pid           TEXT PRIMARY KEY,
            name          TEXT,
            weight        REAL,
            wage_percent  REAL,
            photo_file_id TEXT,
            caption       TEXT,
            created_at    INTEGER
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id     TEXT PRIMARY KEY,
            user_id      INTEGER,
            user_name    TEXT,
            phone        TEXT,
            product_info TEXT,
            pid          TEXT,
            total_price  INTEGER,
            status       TEXT DEFAULT 'pending',
            created_at   INTEGER
        );
        CREATE TABLE IF NOT EXISTS user_states (
            user_id    INTEGER PRIMARY KEY,
            state      TEXT,
            data       TEXT,
            expires_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            name       TEXT,
            phone      TEXT,
            created_at INTEGER
        );
        """)

        # Migration: columns added to `products` after the first release.
        existing = [r[1] for r in conn.execute("PRAGMA table_info(products)")]
        for col, ddl in [
            ("channel_id", "TEXT"),
            ("message_id", "INTEGER"),
            ("has_photo", "INTEGER DEFAULT 0"),
            ("sold", "INTEGER DEFAULT 0"),
            ("num", "INTEGER"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col} {ddl}")

        # Number old products in creation order.
        last = conn.execute("SELECT COALESCE(MAX(num),0) FROM products").fetchone()[0]
        last = max(last, config.PRODUCT_NUM_START - 1)
        rows = conn.execute("SELECT pid FROM products WHERE num IS NULL ORDER BY created_at").fetchall()
        for r in rows:
            last += 1
            conn.execute("UPDATE products SET num=? WHERE pid=?", (last, r[0]))

        now = int(time.time())
        for key in ("manual_gold_price", "channel_gold_price", "channel_price_time",
                    "api_gold_price", "api_price_time"):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key,value,updated_at) VALUES (?,?,?)",
                (key, "0", now),
            )
    logger.info("Database ready")


# --- settings -----------------------------------------------------------------

def get_setting(key: str) -> str:
    with connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else "0"


def set_setting(key: str, value: str) -> None:
    with connection() as conn:
        conn.execute(
            "REPLACE INTO settings (key,value,updated_at) VALUES (?,?,?)",
            (key, value, int(time.time())),
        )


# --- products -----------------------------------------------------------------

_PRODUCT_COLUMNS = ("pid,name,weight,wage_percent,photo_file_id,caption,"
                    "channel_id,message_id,has_photo,sold,num")


def save_product(pid, name, weight, wage, photo_id, caption) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO products "
            "(pid,name,weight,wage_percent,photo_file_id,caption,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (pid, name, weight, wage, photo_id, caption, int(time.time())),
        )


def delete_product(pid: str) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM products WHERE pid=?", (pid,))


def get_product(pid: str) -> Optional[dict]:
    with connection() as conn:
        row = conn.execute(f"SELECT {_PRODUCT_COLUMNS} FROM products WHERE pid=?", (pid,)).fetchone()
    return dict(row) if row else None


def get_all_products() -> List[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT pid,name,weight,wage_percent,sold,num FROM products ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def assign_product_num(pid: str) -> int:
    """Give the product the next public number (shown as #123 under the post)."""
    with connection() as conn:
        current = conn.execute("SELECT COALESCE(MAX(num),0) FROM products").fetchone()[0]
        nxt = max(current + 1, config.PRODUCT_NUM_START)
        conn.execute("UPDATE products SET num=? WHERE pid=?", (nxt, pid))
    return nxt


def set_product_post(pid, channel_id, message_id, has_photo) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE products SET channel_id=?, message_id=?, has_photo=? WHERE pid=?",
            (str(channel_id), message_id, 1 if has_photo else 0, pid),
        )


def mark_sold(pid: str) -> None:
    with connection() as conn:
        conn.execute("UPDATE products SET sold=1 WHERE pid=?", (pid,))


_EDITABLE_FIELDS = ("caption", "name", "weight", "wage_percent")


def update_product_field(pid: str, field: str, value) -> None:
    if field not in _EDITABLE_FIELDS:  # whitelist: the field name goes into the SQL text
        return
    with connection() as conn:
        conn.execute(f"UPDATE products SET {field}=? WHERE pid=?", (value, pid))


def find_product_by_num(num: int) -> Optional[dict]:
    with connection() as conn:
        row = conn.execute("SELECT pid FROM products WHERE num=?", (num,)).fetchone()
    return get_product(row["pid"]) if row else None


def find_product_by_post(chat: dict, message_id: int) -> Optional[dict]:
    """Find a product from a forwarded channel post (channel + message id)."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT pid,channel_id FROM products WHERE message_id=?", (message_id,)
        ).fetchall()
    chat_id = str(chat.get("id", ""))
    username = ("@" + chat["username"]).lower() if chat.get("username") else ""
    for r in rows:
        stored = (r["channel_id"] or "").lower()
        if stored == chat_id or (username and stored == username):
            return get_product(r["pid"])
    return None


def _normalize(s: str) -> str:
    return re.sub(r"[\s*_`]", "", fa_to_en(s or ""))


def find_product_by_caption(text: str) -> Optional[dict]:
    """Match old posts (no stored message id yet) by comparing the caption text."""
    target = _normalize(text)
    if not target:
        return None
    with connection() as conn:
        rows = conn.execute("SELECT pid,caption FROM products WHERE message_id IS NULL").fetchall()
    for r in rows:
        base = _normalize(r["caption"])
        if base and target.startswith(base):
            return get_product(r["pid"])
    return None


# --- orders -------------------------------------------------------------------

def save_order(order_id, user_id, user_name, phone, product_info, pid, total_price) -> bool:
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO orders "
                "(order_id,user_id,user_name,phone,product_info,pid,total_price,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (order_id, user_id, user_name, phone, product_info,
                 pid, total_price, "pending", int(time.time())),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_today_orders() -> List[dict]:
    """Orders since local midnight (the server timezone decides what 'today' means)."""
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with connection() as conn:
        rows = conn.execute(
            "SELECT order_id,user_name,phone,product_info,total_price,created_at "
            "FROM orders WHERE created_at>=? ORDER BY created_at DESC",
            (int(midnight.timestamp()),),
        ).fetchall()
    return [dict(r) for r in rows]


def is_duplicate_order(user_id: int, pid: str, minutes: int = 5) -> bool:
    limit = int((datetime.now() - timedelta(minutes=minutes)).timestamp())
    with connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM orders WHERE user_id=? AND pid=? AND created_at>=? LIMIT 1",
            (user_id, pid, limit),
        ).fetchone()
    return row is not None


# --- conversation state -------------------------------------------------------

def save_user_state(user_id: int, state: str, data: Optional[dict] = None) -> None:
    with connection() as conn:
        conn.execute(
            "REPLACE INTO user_states (user_id,state,data,expires_at) VALUES (?,?,?,?)",
            (user_id, state, json.dumps(data or {}), int(time.time()) + STATE_TTL_SECONDS),
        )


def get_user_state(user_id: int) -> Optional[dict]:
    with connection() as conn:
        row = conn.execute(
            "SELECT state,data,expires_at FROM user_states WHERE user_id=?", (user_id,)
        ).fetchone()
    if row:
        if row["expires_at"] > int(time.time()):
            return {"state": row["state"], "data": json.loads(row["data"])}
        clear_user_state(user_id)
    return None


def clear_user_state(user_id: int) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM user_states WHERE user_id=?", (user_id,))


def cleanup_expired_states() -> None:
    with connection() as conn:
        deleted = conn.execute(
            "DELETE FROM user_states WHERE expires_at<?", (int(time.time()),)
        ).rowcount
    if deleted:
        logger.info("Cleaned up %d expired states", deleted)


# --- users --------------------------------------------------------------------

def save_user(user_id: int, name: str, phone: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id,name,phone,created_at) VALUES (?,?,?,?)",
            (user_id, name, phone, int(time.time())),
        )


def get_user(user_id: int) -> Optional[dict]:
    with connection() as conn:
        row = conn.execute(
            "SELECT user_id,name,phone FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None
