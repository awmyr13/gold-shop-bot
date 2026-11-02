"""Inline-button (callback query) handlers."""
import json
import logging

from .. import bale_api as bale
from .. import config, db, posts, texts
from ..keyboards import (kb_cancel, kb_confirm_order, kb_pm_card, kb_pm_list,
                         kb_pm_menu, kb_remove)
from ..pricing import calculate_price, get_gold_price
from ..utils import make_order_id, md_safe

logger = logging.getLogger(__name__)


def handle_callback(callback_query: dict) -> None:
    qid = callback_query["id"]
    user_id = callback_query["from"]["id"]
    action, _, arg = callback_query.get("data", "").partition(":")

    if action == "pm":  # admin product management
        if user_id not in config.ADMIN_IDS:
            bale.answer_cb(qid, "دسترسی غیرمجاز.", True)
            return
        _handle_pm(callback_query, arg)
        return

    handler = _CUSTOMER_ACTIONS.get(action)
    if handler:
        handler(qid, user_id, arg)
        return

    logger.warning("Unknown callback action %r from user %s", action, user_id)
    bale.answer_cb(qid, "عملیات نامعتبر.", True)  # otherwise the client spins forever


# --- customer actions ------------------------------------------------------------

def _inquiry(qid: str, user_id: int, pid: str) -> None:
    product = db.get_product(pid) if pid else None
    if not product:
        bale.answer_cb(qid, "محصول یافت نشد.", True)
        return
    gold_price = get_gold_price()
    if gold_price <= 0:
        bale.answer_cb(qid, "در حال حاضر قیمت طلا در دسترس نیست.", True)
        return
    calc = calculate_price(product["weight"], product["wage_percent"], gold_price)
    bale.answer_cb(qid, texts.txt_inquiry(product, calc), alert=True)  # pop-up, no chat message


def _buy(qid: str, user_id: int, pid: str) -> None:
    product = db.get_product(pid) if pid else None
    if not product:
        bale.answer_cb(qid, "محصول یافت نشد.", True)
        return
    if product.get("sold"):
        bale.answer_cb(qid, "این محصول فروخته شده است.", True)
        return
    gold_price = get_gold_price()
    if gold_price <= 0:
        bale.answer_cb(qid, "امکان ثبت سفارش به دلیل عدم دسترسی به قیمت طلا وجود ندارد.", True)
        return

    if db.get_user(user_id):
        # Returning customer: go straight to the pre-invoice.
        calc = calculate_price(product["weight"], product["wage_percent"], gold_price)
        bale.send(user_id, texts.txt_returning_confirm(product, calc), kb_confirm_order(pid))
        bale.answer_cb(qid, "پیش‌فاکتور به پی‌وی شما ارسال شد. لطفاً برای تایید نهایی به چت ربات بروید.", True)
    else:
        # New customer: collect name and phone first.
        db.save_user_state(user_id, "waiting_reg_name", {"pid": pid})
        bale.send(user_id, texts.txt_register_prompt())
        bale.answer_cb(qid, "لطفاً برای تکمیل خرید به پی‌وی ربات بروید.", True)


def _confirm_order(qid: str, user_id: int, pid: str) -> None:
    user = db.get_user(user_id)
    product = db.get_product(pid) if pid else None
    gold_price = get_gold_price()

    if not user or not product:
        bale.answer_cb(qid, "خطا: اطلاعات منقضی شده است. مجدداً از کانال اقدام کنید.", True)
        return
    if product.get("sold"):
        bale.answer_cb(qid, "این محصول فروخته شده است.", True)
        return
    if gold_price <= 0:
        bale.answer_cb(qid, "قیمت طلا در دسترس نیست. لطفاً بعداً تلاش کنید.", True)
        return
    if db.is_duplicate_order(user_id, pid, minutes=5):
        bale.answer_cb(qid, "سفارش شما قبلاً ثبت شده است.", True)
        return

    calc = calculate_price(product["weight"], product["wage_percent"], gold_price)
    order_id = make_order_id()
    product_info = f"{product['name']} ({product['weight']}گرم)"
    db.save_order(order_id, user_id, user["name"], user["phone"], product_info, pid, calc["total"])

    notice = texts.txt_admin_order(user["name"], user_id, user["phone"],
                                   product_info, order_id, calc["total"])
    for admin_id in config.ADMIN_IDS:
        bale.send(admin_id, notice)

    bale.send(user_id,
              "🎉 سفارش شما با موفقیت تایید و ثبت شد!\n\n" + texts.txt_order_done(user["name"], order_id),
              kb_remove())
    bale.answer_cb(qid)


def _cancel_order(qid: str, user_id: int, _arg: str) -> None:
    bale.send(user_id, "❌ عملیات خرید لغو شد. هر زمان مایل بودید می‌توانید مجدداً از کانال اقدام کنید.",
              kb_remove())
    bale.answer_cb(qid)


_CUSTOMER_ACTIONS = {
    "inq": _inquiry,
    "buy": _buy,
    "conf_order": _confirm_order,
    "cancel_order": _cancel_order,
}


# --- admin product management (callback data "pm:<command>:...") -------------------

def show_screen(cq: dict, text: str, keyboard: dict) -> None:
    """Edit the current message in place; fall back to a new message if that fails."""
    msg = cq.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id") or cq["from"]["id"]
    message_id = msg.get("message_id")
    if message_id:
        res = bale.api("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text,
            "parse_mode": "Markdown", "reply_markup": json.dumps(keyboard),
        })
        if res.get("ok") or "not modified" in str(res.get("description", "")).lower():
            return
    bale.send(chat_id, text, keyboard)


def _handle_pm(cq: dict, rest: str) -> None:
    qid = cq["id"]
    args = rest.split(":")
    cmd = args[0]

    if cmd == "close":
        bale.answer_cb(qid)
        msg = cq.get("message") or {}
        if msg.get("message_id"):
            bale.api("deleteMessage", {"chat_id": msg["chat"]["id"], "message_id": msg["message_id"]})
        return

    if cmd == "menu":
        bale.answer_cb(qid)
        show_screen(cq, texts.txt_pm_menu(), kb_pm_menu())
        return

    if cmd == "list" and len(args) >= 3:
        _pm_list(cq, mode=args[1], page_arg=args[2])
        return

    if cmd in ("ask", "do", "edit") and len(args) >= 3:
        mode, pid = args[1], args[2]
        product = db.get_product(pid)
        if not product:
            bale.answer_cb(qid, "محصول یافت نشد (احتمالاً حذف شده).", True)
            return
        if cmd == "ask":
            _pm_ask(cq, mode, product)
            return
        if cmd == "do" and _pm_do(cq, mode, product):
            return
        if cmd == "edit" and _pm_edit(cq, mode, product):
            return

    bale.answer_cb(qid, "عملیات نامعتبر.", True)


def _pm_list(cq: dict, mode: str, page_arg: str) -> None:
    bale.answer_cb(cq["id"])
    try:
        page = int(page_arg)
    except ValueError:
        page = 0
    products = db.get_all_products()
    if mode == "sold":  # only unsold products can be marked as sold
        products = [p for p in products if not p.get("sold")]
    if not products:
        back = [{"text": "↩️ بازگشت", "callback_data": "pm:menu"}]
        show_screen(cq, "محصولی برای نمایش وجود نداره.", {"inline_keyboard": [back]})
        return
    keyboard, page, pages = kb_pm_list(products, mode, page)
    title = "✅ *کدوم محصول فروخته شد؟*" if mode == "sold" else "🗑 *کدوم محصول حذف بشه؟*"
    show_screen(cq, f"{title}\n\nصفحه {page + 1} از {pages}  ({len(products)} محصول)", keyboard)


def _pm_ask(cq: dict, mode: str, product: dict) -> None:
    """Ask the admin to confirm marking a product as sold or deleting it."""
    bale.answer_cb(cq["id"])
    pid = product["pid"]
    tag = f" (#{product['num']})" if product.get("num") else ""
    if mode == "sold":
        text = (
            f"✅ *تایید فروخته شدن*\n\nمحصول: {md_safe(product['name'])}{tag}\n\n"
            "بعد از تایید، به پست کانال «فروخته شد» اضافه میشه و دکمه «خرید» "
            "برداشته میشه. دکمه «استعلام قیمت» می‌مونه.\n\nمطمئنی؟"
        )
        keyboard = {"inline_keyboard": [[
            {"text": "✅ بله، فروخته شد", "callback_data": f"pm:do:sold:{pid}"},
            {"text": "❌ انصراف", "callback_data": "pm:list:sold:0"},
        ]]}
    else:
        text = (
            f"🗑 *حذف محصول*\n\n{md_safe(product['name'])}{tag}\n\n"
            "محصول از دیتابیس پاک میشه (پست کانال حذف نمیشه). مطمئنی؟"
        )
        keyboard = {"inline_keyboard": [[
            {"text": "🗑 بله، حذف شود", "callback_data": f"pm:do:del:{pid}"},
            {"text": "❌ انصراف", "callback_data": "pm:menu"},
        ]]}
    show_screen(cq, text, keyboard)


def _pm_do(cq: dict, mode: str, product: dict) -> bool:
    """Execute a confirmed action. Returns False if the mode is unknown."""
    qid = cq["id"]
    pid = product["pid"]
    if mode == "sold":
        ok, message = posts.mark_product_sold(product)
        bale.answer_cb(qid, message, True)
        if ok:
            product = db.get_product(pid)
            show_screen(cq, texts.txt_pm_card(product), kb_pm_card(product))
        return True
    if mode == "del":
        db.delete_product(pid)
        bale.answer_cb(qid, "✅ محصول حذف شد.", True)
        show_screen(cq, texts.txt_pm_menu(), kb_pm_menu())
        return True
    return False


_EDIT_PROMPTS = {
    "caption": "✏️ متن جدید پست رو بفرست.\n(خط شناسه و «فروخته شد» رو خود ربات اضافه می‌کنه.) "
               "متن فعلی پایین‌تره، می‌تونی کپی و ویرایشش کنی:",
    "weight": "⚖️ وزن جدید رو به گرم بفرست (مثال: 1.13):\n"
              "(وزن فقط قیمت استعلام رو عوض می‌کنه. اگه توی متن پست هم نوشته شده، «متن پست» رو هم ویرایش کن.)",
    "wage_percent": "💹 درصد اجرت جدید رو بفرست (مثال: 20):\n"
                    "(اگه توی متن پست هم نوشته شده، «متن پست» رو هم ویرایش کن.)",
}


def _pm_edit(cq: dict, field: str, product: dict) -> bool:
    """Start editing one product field. Returns False if the field is unknown."""
    qid = cq["id"]
    user_id = cq["from"]["id"]
    if field not in _EDIT_PROMPTS:
        return False
    db.save_user_state(user_id, "edit_field", {"pid": product["pid"], "field": field})
    bale.answer_cb(qid)
    bale.send(user_id, _EDIT_PROMPTS[field], kb_cancel())
    if field == "caption":
        bale.send_plain(user_id, product.get("caption") or "")  # verbatim, easy to copy
    return True
