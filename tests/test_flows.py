"""End-to-end conversation tests with the Bale API replaced by a recorder."""
from gold_bot import db, posts
from gold_bot.handlers import process_update

ADMIN, CUSTOMER = 1001, 2001


def msg(user_id, text=None, **extra):
    m = {"chat": {"id": user_id}, "from": {"id": user_id, "first_name": "Tester"}}
    if text is not None:
        m["text"] = text
    m.update(extra)
    return {"message": m}


def click(user_id, data):
    return {"callback_query": {"id": "cb1", "from": {"id": user_id}, "data": data,
                               "message": {"chat": {"id": user_id}, "message_id": 9}}}


def publish_product(fake):
    """Run the admin wizard and return the created product."""
    process_update(msg(ADMIN, "📤 ارسال محصول"))
    process_update(msg(ADMIN, photo=[{"file_id": "small"}, {"file_id": "big"}]))
    process_update(msg(ADMIN, "Gold ring\nweight: 2"))
    process_update(msg(ADMIN, "Gold ring"))
    process_update(msg(ADMIN, "۲"))
    process_update(msg(ADMIN, "۲۰"))
    process_update(msg(ADMIN, "@my_channel"))
    return db.get_all_products()[0]


def test_admin_publishes_product(fake):
    product = publish_product(fake)
    assert (product["name"], product["weight"], product["wage_percent"], product["num"]) == ("Gold ring", 2.0, 20.0, 1)

    photo = fake.of("sendPhoto")[0]
    assert photo["chat_id"] == "@my_channel" and photo["photo"] == "big"
    assert "#1" in photo["caption"]

    stored = db.get_product(product["pid"])
    assert stored["message_id"] == 555 and stored["has_photo"] == 1


def test_non_admin_cannot_use_admin_menu_or_pm_buttons(fake):
    process_update(msg(CUSTOMER, "📤 ارسال محصول"))
    assert db.get_user_state(CUSTOMER) is None
    process_update(click(CUSTOMER, "pm:menu"))
    assert fake.of("answerCallbackQuery")[-1]["text"] == "دسترسی غیرمجاز."


def test_price_inquiry_popup(fake):
    product = publish_product(fake)
    db.set_setting("manual_gold_price", "10000000")
    process_update(click(CUSTOMER, f"inq:{product['pid']}"))
    answer = fake.of("answerCallbackQuery")[-1]
    assert answer["show_alert"] is True and "24,000,000" in answer["text"]


def test_new_customer_buys_product(fake):
    product = publish_product(fake)
    db.set_setting("manual_gold_price", "10000000")

    process_update(click(CUSTOMER, f"buy:{product['pid']}"))                   # asks for the name
    process_update(msg(CUSTOMER, "Ali_Reza*"))                                # Markdown chars in name
    process_update(msg(CUSTOMER, contact={"phone_number": "+989121234567"}))   # shares the phone
    assert db.get_user(CUSTOMER)["phone"] == "09121234567"

    process_update(click(CUSTOMER, f"conf_order:{product['pid']}"))
    orders = db.get_today_orders()
    assert len(orders) == 1 and orders[0]["total_price"] == 24_000_000

    admin_notices = [p for p in fake.of("sendMessage") if p["chat_id"] == ADMIN and "سفارش جدید" in p["text"]]
    assert len(admin_notices) == 1
    assert "Ali_Reza*" not in admin_notices[0]["text"]  # sanitized, so Markdown stays valid

    process_update(click(CUSTOMER, f"conf_order:{product['pid']}"))            # double click
    assert len(db.get_today_orders()) == 1
    assert fake.of("answerCallbackQuery")[-1]["text"] == "سفارش شما قبلاً ثبت شده است."


def test_cannot_buy_without_price(fake):
    product = publish_product(fake)
    process_update(click(CUSTOMER, f"buy:{product['pid']}"))
    assert "قیمت طلا" in fake.of("answerCallbackQuery")[-1]["text"]
    assert db.get_user_state(CUSTOMER) is None


def test_mark_sold_edits_channel_post(fake):
    product = publish_product(fake)
    process_update(click(ADMIN, f"pm:do:sold:{product['pid']}"))

    edit = fake.of("editMessageCaption")[0]
    assert edit["message_id"] == 555 and "فروخته شد" in edit["caption"]
    assert "buy:" not in edit["reply_markup"] and "inq:" in edit["reply_markup"]
    assert db.get_product(product["pid"])["sold"] == 1

    process_update(click(CUSTOMER, f"buy:{product['pid']}"))
    assert fake.of("answerCallbackQuery")[-1]["text"] == "این محصول فروخته شده است."


def test_admin_finds_product_by_number_and_edits_weight(fake):
    product = publish_product(fake)
    process_update(msg(ADMIN, "#۱"))
    assert "Gold ring" in fake.texts()[-1]

    process_update(click(ADMIN, f"pm:edit:weight:{product['pid']}"))
    process_update(msg(ADMIN, "3.5"))
    assert db.get_product(product["pid"])["weight"] == 3.5


def test_price_channel_post_updates_price(fake):
    update = {"channel_post": {"chat": {"id": -5, "username": "price_channel"},
                               "text": "طلای ۱۸ عیار: ۱۹,۰۰۰,۰۰۰"}}
    process_update(update)
    assert db.get_setting("channel_gold_price") == "19000000"


def test_compose_caption_respects_telegram_limits():
    p = {"caption": "x" * 5000, "num": 7, "sold": 1, "has_photo": True}
    caption = posts.compose_caption(p)
    assert len(caption) <= 1024 and caption.endswith("🔴")
