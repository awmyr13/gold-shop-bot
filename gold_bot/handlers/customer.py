"""Messages from regular customers (registration flow before the first order)."""
from .. import bale_api as bale
from .. import db, texts
from ..keyboards import kb_confirm_order, kb_remove, kb_request_contact
from ..pricing import calculate_price, get_gold_price
from ..utils import fa_to_en, md_safe

MIN_NAME_LENGTH = 3


def handle_customer_message(message: dict, user_id: int, user_name: str, chat_id, text: str) -> None:
    if text == "/start":
        bale.send(chat_id, texts.txt_welcome(user_name))
        return

    state_obj = db.get_user_state(user_id)
    if state_obj:
        state, data = state_obj["state"], state_obj["data"]
        if state == "waiting_reg_name":
            _registration_name(chat_id, user_id, text, data)
            return
        if state == "waiting_reg_phone":
            _registration_phone(message, chat_id, user_id, data)
            return

    bale.send(chat_id, "برای خرید یا استعلام قیمت، لطفاً روی دکمه‌های شیشه‌ای زیر محصولات در کانال کلیک کنید. ✨")


def _registration_name(chat_id, user_id: int, text: str, data: dict) -> None:
    if not text or len(text) < MIN_NAME_LENGTH:
        bale.send(chat_id, texts.txt_ask_full_name())
        return
    db.save_user_state(user_id, "waiting_reg_phone", {**data, "name": text})
    bale.send(chat_id, texts.txt_ask_phone(text), kb_request_contact())


def _normalize_phone(raw) -> str:
    """'+98 912...' / '98912...' / Persian digits -> '0912...'."""
    phone = fa_to_en(str(raw)).replace("+", "")
    if not phone.startswith("0") and phone.startswith("98"):
        phone = "0" + phone[2:]
    return phone


def _registration_phone(message: dict, chat_id, user_id: int, data: dict) -> None:
    contact = message.get("contact")
    if not (contact and "phone_number" in contact):
        bale.send(chat_id, "لطفاً صرفاً از دکمه «📱 ارسال شماره موبایل رسمی بله» استفاده کنید.",
                  kb_request_contact())
        return

    phone = _normalize_phone(contact["phone_number"])
    name = data["name"]
    db.save_user(user_id, name, phone)

    pid = data.get("pid")
    product = db.get_product(pid) if pid else None
    db.clear_user_state(user_id)

    if not product:
        bale.send(chat_id, "ثبت نام انجام شد اما محصول یافت نشد. مجدداً از کانال اقدام کنید.", kb_remove())
        return

    gold_price = get_gold_price()
    if gold_price <= 0:
        bale.send(chat_id,
                  f"✅ {md_safe(name)} عزیز، ثبت‌نام شما انجام شد!\n\n"
                  "⚠️ در حال حاضر قیمت طلا تنظیم نشده. بعداً از کانال اقدام کنید.",
                  kb_remove())
        return

    calc = calculate_price(product["weight"], product["wage_percent"], gold_price)
    bale.send(chat_id, texts.txt_new_customer_confirm(name, product, calc), kb_confirm_order(pid))
