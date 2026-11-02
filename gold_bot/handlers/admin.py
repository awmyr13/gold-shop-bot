"""Messages from admins: product publishing flow, manual price, reports, product lookup."""
import re

from .. import bale_api as bale
from .. import db, posts, texts
from ..keyboards import (BTN_CURRENT_PRICE, BTN_MANUAL_PRICE, BTN_PRODUCTS, BTN_REPORT,
                         BTN_SEND_PRODUCT, kb_admin, kb_cancel, kb_pm_card, kb_pm_menu,
                         kb_product)
from ..utils import fa_to_en, fmt, make_pid, md_safe


def admin_menu(chat_id) -> None:
    bale.send(chat_id, texts.txt_admin_menu(), kb_admin())


def handle_admin_message(message: dict, user_id: int, chat_id, text: str) -> None:
    state_obj = db.get_user_state(user_id)
    state = state_obj["state"] if state_obj else None
    data = state_obj["data"] if state_obj else {}

    if state is None and _lookup_product(message, chat_id, text):
        return

    handler = _STATE_HANDLERS.get(state)
    if handler:
        handler(message, chat_id, user_id, text, data)
        return

    _menu_button(chat_id, user_id, text)


# --- quick product lookup (forwarded channel post or "#365") ------------------------

def _lookup_product(message: dict, chat_id, text: str) -> bool:
    """Open a product card from a forwarded post or a product number. True if handled."""
    fwd_chat = message.get("forward_from_chat")
    fwd_mid = message.get("forward_from_message_id")
    if fwd_chat and fwd_mid:
        product = db.find_product_by_post(fwd_chat, fwd_mid)
        if not product:
            # Old posts have no stored message id yet: match by caption, then link them.
            product = db.find_product_by_caption(text)
            if product:
                db.set_product_post(product["pid"], fwd_chat["id"], fwd_mid, bool(message.get("photo")))
                product = db.get_product(product["pid"])
        if product:
            bale.send(chat_id, texts.txt_pm_card(product), kb_pm_card(product))
        else:
            bale.send(chat_id, "⚠️ این پست به هیچ محصولی وصل نشد. شناسه‌ی محصول (مثل #365) "
                               "رو بفرست یا از «📦 محصولات» انتخابش کن.")
        return True

    match = None if "photo" in message else re.fullmatch(r"#?\s*(\d{1,7})", fa_to_en(text).strip())
    if match:
        product = db.find_product_by_num(int(match.group(1)))
        if product:
            bale.send(chat_id, texts.txt_pm_card(product), kb_pm_card(product))
        else:
            bale.send(chat_id, f"محصولی با شناسه #{match.group(1)} پیدا نشد.")
        return True
    return False


# --- editing one product field --------------------------------------------------------

def _edit_field(message, chat_id, user_id, text, data) -> None:
    pid, field = data.get("pid"), data.get("field")
    product = db.get_product(pid) if pid else None
    if not product:
        db.clear_user_state(user_id)
        bale.send(chat_id, "محصول یافت نشد.")
        admin_menu(chat_id)
        return
    if not text:
        return

    if field in ("weight", "wage_percent"):
        try:
            value = float(fa_to_en(text))
            if value < 0 or (field == "weight" and value == 0):
                raise ValueError
        except ValueError:
            bale.send(chat_id, "عدد معتبر وارد کن.", kb_cancel())
            return
    else:
        value = text
        limit = posts.max_user_caption_length(product.get("has_photo"))
        if len(value) > limit:
            bale.send(chat_id, f"متن خیلی بلنده؛ حداکثر {limit} کاراکتر.", kb_cancel())
            return

    db.update_product_field(pid, field, value)
    db.clear_user_state(user_id)
    product = db.get_product(pid)
    if field == "caption":
        res = posts.refresh_channel_post(product)
        if res.get("ok"):
            bale.send(chat_id, "✅ ذخیره شد و پست کانال ویرایش شد.")
        else:
            bale.send(chat_id, "⚠️ ذخیره شد ولی ویرایش پست کانال ناموفق بود:\n"
                      + str(res.get("description", ""))[:150])
    else:
        bale.send(chat_id, "✅ ذخیره شد.")
    bale.send(chat_id, texts.txt_pm_card(product), kb_pm_card(product))


# --- "send product" wizard: photo -> caption -> name -> weight -> wage -> channel -------

def _await_photo(message, chat_id, user_id, text, data) -> None:
    if "photo" not in message:
        bale.send(chat_id, "لطفاً یک عکس ارسال کن.", kb_cancel())
        return
    photo = message["photo"]
    file_id = photo[-1]["file_id"] if isinstance(photo, list) else photo.get("file_id")
    db.save_user_state(user_id, "await_caption", {"file_id": file_id})
    bale.send(chat_id,
              "✅ عکس دریافت شد!\n\n"
              "مرحله ۲/۵: متن زیر رو کپی کن، جاهای خالی (نام محصول، وزن، اجرت تمام شده، ثبت سفارش از طریق) "
              "رو جایگزاری کن و دوباره برام بفرست:\n"
              "(اگه نیاز به اصلاح داشت، همین کارو دوباره تکرار کن)\n\n"
              f"{texts.product_template()}",
              kb_cancel())


def _await_caption(message, chat_id, user_id, text, data) -> None:
    if text:
        db.save_user_state(user_id, "await_name", {**data, "caption": text})
        bale.send(chat_id, "مرحله ۳/۵: نام محصول رو وارد کن:", kb_cancel())


def _await_name(message, chat_id, user_id, text, data) -> None:
    if text:
        db.save_user_state(user_id, "await_weight", {**data, "product_name": text})
        bale.send(chat_id, "مرحله ۴/۵: وزن رو به گرم وارد کن (مثال: 1.13):", kb_cancel())


def _await_weight(message, chat_id, user_id, text, data) -> None:
    try:
        weight = float(fa_to_en(text))
        if weight <= 0:
            raise ValueError("weight <= 0")
    except ValueError:
        bale.send(chat_id, "عدد مثبت وارد کن.", kb_cancel())
        return
    db.save_user_state(user_id, "await_wage", {**data, "weight": weight})
    bale.send(chat_id, "مرحله ۵/۵: درصد اجرت رو وارد کن (مثال: 20):", kb_cancel())


def _await_wage(message, chat_id, user_id, text, data) -> None:
    try:
        wage = float(fa_to_en(text))
        if wage < 0:
            raise ValueError("wage < 0")
    except ValueError:
        bale.send(chat_id, "عدد معتبر وارد کن.", kb_cancel())
        return
    db.save_user_state(user_id, "await_channel", {**data, "wage": wage})
    bale.send(chat_id, "آیدی کانال رو وارد کن (مثال: @my_channel):", kb_cancel())


def _await_channel(message, chat_id, user_id, text, data) -> None:
    """Last step: save the product and publish it to the channel."""
    if not text:
        return
    channel_id = text if text.startswith(("@", "-")) else f"@{text}"
    pid = make_pid()
    name = data.get("product_name", "محصول")
    db.save_product(pid, name, data.get("weight", 0), data.get("wage", 0),
                    data.get("file_id", ""), data.get("caption", ""))

    num = db.assign_product_num(pid)
    has_photo = bool(data.get("file_id"))
    caption = posts.compose_caption({"caption": data.get("caption", ""), "num": num,
                                     "sold": 0, "has_photo": has_photo})
    if has_photo:
        result = bale.send_photo(channel_id, data["file_id"], caption, kb_product(pid))
    else:
        result = bale.send(channel_id, caption, kb_product(pid))

    db.clear_user_state(user_id)
    if result.get("ok"):
        posted = result.get("result") or {}
        db.set_product_post(pid, (posted.get("chat") or {}).get("id", channel_id),
                            posted.get("message_id"), has_photo)
        bale.send(chat_id, f"✅ محصول *{md_safe(name)}* با شناسه *#{num}* در کانال ارسال شد.")
    else:
        bale.send(chat_id,
                  f"⚠️ محصول *{md_safe(name)}* در دیتابیس ذخیره شد اما ارسال به کانال ناموفق بود.\n"
                  "مطمئن شوید ربات ادمین کانال است.")
    admin_menu(chat_id)


# --- manual price ------------------------------------------------------------------------

def _set_price(message, chat_id, user_id, text, data) -> None:
    try:
        price = int(re.sub(r"[^\d]", "", fa_to_en(text)))
        if price <= 0:
            raise ValueError
    except ValueError:
        bale.send(chat_id, "عدد صحیح وارد کن.", kb_cancel())
        return
    db.set_setting("manual_gold_price", str(price))
    db.clear_user_state(user_id)
    bale.send(chat_id, f"✅ قیمت دستی ذخیره شد: *{fmt(price)} تومان*")
    admin_menu(chat_id)


_STATE_HANDLERS = {
    "edit_field": _edit_field,
    "await_photo": _await_photo,
    "await_caption": _await_caption,
    "await_name": _await_name,
    "await_weight": _await_weight,
    "await_wage": _await_wage,
    "await_channel": _await_channel,
    "set_price": _set_price,
}


# --- main menu buttons ---------------------------------------------------------------------

def _menu_button(chat_id, user_id, text: str) -> None:
    if text == BTN_SEND_PRODUCT:
        db.save_user_state(user_id, "await_photo", {})
        bale.send(chat_id, "مرحله ۱/۵: عکس محصول رو ارسال کن:", kb_cancel())
    elif text == BTN_MANUAL_PRICE:
        db.save_user_state(user_id, "set_price", {})
        bale.send(chat_id, "قیمت طلای ۱۸ عیار را به تومان وارد کنید:", kb_cancel())
    elif text == BTN_CURRENT_PRICE:
        bale.send(chat_id, texts.txt_current_price())
    elif text == BTN_REPORT:
        bale.send(chat_id, texts.txt_today_report())
    elif text == BTN_PRODUCTS:
        bale.send(chat_id, texts.txt_pm_menu(), kb_pm_menu())
    else:
        admin_menu(chat_id)
