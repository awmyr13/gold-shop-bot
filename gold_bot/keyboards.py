"""Reply and inline keyboards."""
from . import config

# Labels of the admin reply-keyboard buttons (also matched in the message handler).
BTN_SEND_PRODUCT = "📤 ارسال محصول"
BTN_MANUAL_PRICE = "✏️ قیمت دستی"
BTN_REPORT = "📊 گزارش امروز"
BTN_PRODUCTS = "📦 محصولات"
BTN_CURRENT_PRICE = "💰 قیمت فعلی"
BTN_CANCEL = "❌ لغو عملیات"


def kb_admin() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_SEND_PRODUCT}, {"text": BTN_MANUAL_PRICE}],
            [{"text": BTN_REPORT}, {"text": BTN_PRODUCTS}],
            [{"text": BTN_CURRENT_PRICE}],
            [{"text": BTN_CANCEL}],
        ],
        "resize_keyboard": True,
    }


def kb_cancel() -> dict:
    return {"keyboard": [[{"text": BTN_CANCEL}]], "resize_keyboard": True}


def kb_remove() -> dict:
    return {"remove_keyboard": True}


def kb_request_contact() -> dict:
    return {
        "keyboard": [[{"text": "📱 ارسال شماره موبایل رسمی بله", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def kb_product(pid: str) -> dict:
    """Buttons under a product post in the channel."""
    return {"inline_keyboard": [[
        {"text": "💰 استعلام قیمت", "callback_data": f"inq:{pid}"},
        {"text": "🛒 خرید", "callback_data": f"buy:{pid}"},
    ]]}


def kb_product_sold(pid: str) -> dict:
    """After a sale only the price inquiry button remains."""
    return {"inline_keyboard": [[{"text": "💰 استعلام قیمت", "callback_data": f"inq:{pid}"}]]}


def kb_confirm_order(pid: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ بله، مطمئنم - ثبت نهایی", "callback_data": f"conf_order:{pid}"},
        {"text": "❌ خیر، انصراف", "callback_data": "cancel_order"},
    ]]}


def kb_pm_menu() -> dict:
    return {"inline_keyboard": [
        [{"text": "✅ فروخته شد", "callback_data": "pm:list:sold:0"}],
        [{"text": "🗑 حذف محصول", "callback_data": "pm:list:del:0"}],
        [{"text": "✖️ بستن", "callback_data": "pm:close"}],
    ]}


def kb_pm_list(products: list, mode: str, page: int):
    """Paged product list. Returns (keyboard, clamped page, total pages)."""
    pages = max(1, (len(products) + config.PAGE_SIZE - 1) // config.PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = products[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]
    rows = []
    for p in chunk:
        tag = f"#{p['num']} " if p.get("num") else ""
        mark = "🔴 " if p.get("sold") else ""
        rows.append([{
            "text": f"{mark}{tag}{p['name'][:22]} ({p['weight']}گرم)",
            "callback_data": f"pm:ask:{mode}:{p['pid']}",
        }])
    nav = []
    if page > 0:
        nav.append({"text": "⬅️ قبلی", "callback_data": f"pm:list:{mode}:{page - 1}"})
    if page < pages - 1:
        nav.append({"text": "بعدی ➡️", "callback_data": f"pm:list:{mode}:{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "↩️ بازگشت", "callback_data": "pm:menu"}])
    return {"inline_keyboard": rows}, page, pages


def kb_pm_card(p: dict) -> dict:
    """Management buttons shown under a product card."""
    pid = p["pid"]
    rows = []
    if not p.get("sold"):
        rows.append([{"text": "✅ ثبت به‌عنوان فروخته شده", "callback_data": f"pm:do:sold:{pid}"}])
    rows.append([
        {"text": "✏️ متن پست", "callback_data": f"pm:edit:caption:{pid}"},
        {"text": "⚖️ وزن", "callback_data": f"pm:edit:weight:{pid}"},
        {"text": "💹 اجرت", "callback_data": f"pm:edit:wage_percent:{pid}"},
    ])
    rows.append([
        {"text": "🗑 حذف محصول", "callback_data": f"pm:ask:del:{pid}"},
        {"text": "✖️ بستن", "callback_data": "pm:close"},
    ])
    return {"inline_keyboard": rows}
