import time

from gold_bot import config, db


def _product(pid="P1", name="Ring"):
    db.save_product(pid, name, 2.5, 18, "file123", "caption text")
    return db.assign_product_num(pid)


def test_product_numbering_is_sequential(database):
    assert _product("A") == 1
    assert _product("B") == 2
    assert db.find_product_by_num(2)["pid"] == "B"


def test_product_num_start(database, monkeypatch):
    monkeypatch.setattr(config, "PRODUCT_NUM_START", 365)
    assert _product("A") == 365


def test_update_field_whitelist(database):
    _product()
    db.update_product_field("P1", "weight", 3.0)
    assert db.get_product("P1")["weight"] == 3.0
    db.update_product_field("P1", "pid; DROP TABLE products;--", "x")  # must be ignored
    assert db.get_product("P1") is not None


def test_find_product_by_forwarded_post(database):
    _product()
    db.set_product_post("P1", -100123, 77, True)
    assert db.find_product_by_post({"id": -100123}, 77)["pid"] == "P1"
    assert db.find_product_by_post({"id": -999}, 77) is None


def test_find_product_by_caption_for_legacy_posts(database):
    _product()  # no message_id stored yet
    assert db.find_product_by_caption("caption text\n\n🔖 شناسه: #1")["pid"] == "P1"


def test_duplicate_order_detection(database):
    assert db.save_order("O1", 5, "Ali", "0912", "Ring", "P1", 100)
    assert db.is_duplicate_order(5, "P1")
    assert not db.is_duplicate_order(6, "P1")
    assert not db.save_order("O1", 5, "Ali", "0912", "Ring", "P1", 100)  # same order id


def test_today_orders(database):
    db.save_order("O1", 5, "Ali", "0912", "Ring", "P1", 100)
    assert [o["order_id"] for o in db.get_today_orders()] == ["O1"]


def test_user_state_expires(database):
    db.save_user_state(1, "await_photo", {"a": 1})
    assert db.get_user_state(1) == {"state": "await_photo", "data": {"a": 1}}
    with db.connection() as conn:
        conn.execute("UPDATE user_states SET expires_at=?", (int(time.time()) - 1,))
    assert db.get_user_state(1) is None


def test_users(database):
    db.save_user(9, "Sara", "09121234567")
    assert db.get_user(9)["phone"] == "09121234567"
