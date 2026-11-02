"""User-facing message texts (Persian).

Customer-provided strings are passed through ``md_safe`` because messages are sent
with Markdown parsing; a stray ``*`` or ``_`` in a name would make the API reject
the whole message (e.g. the admin would never see a new order).
"""
from datetime import datetime

from . import config, db
from .pricing import resolve_price
from .utils import fmt, md_safe


def product_template() -> str:
    """Template the admin copies, fills in and sends back as the post caption."""
    lines = [
        config.SHOP_NAME,
        "نام محصول :",
        "وزن :",
        "اجرت تمام شده :",
        "ثبت سفارش از طریق :",
    ]
    if config.SHOP_ADDRESS:
        lines.append(f"آدرس :{config.SHOP_ADDRESS}")
    if config.SHOP_SHIPPING_NOTE:
        lines.append(config.SHOP_SHIPPING_NOTE)
    if config.SHOP_PHONE:
        lines.append(f"شماره تماس : {config.SHOP_PHONE}")
    if config.SHOP_LANDLINE:
        lines.append(f"تلفن گالری: {config.SHOP_LANDLINE}")
    if config.SHOP_NOTE:
        lines.append(config.SHOP_NOTE)
    if config.SHOP_CONTACT_HANDLE:
        lines += ["راه ارتباطی با ما :", config.SHOP_CONTACT_HANDLE]
    if config.SHOP_ETAA_URL:
        lines += ["جهت عضویت در کانال ایتا", config.SHOP_ETAA_URL]
    if config.SHOP_CHANNEL:
        lines += ["جهت عضویت در کانال", config.SHOP_CHANNEL]
    return "\n".join(lines)


# --- customer ------------------------------------------------------------------

def txt_welcome(user_name: str) -> str:
    return (
        f"درود بر شما {md_safe(user_name)} عزیز، به دنیای درخشان {config.SHOP_NAME} خوش آمدید. ✨\n\n"
        "جایی که اصالت هنر طلاکاری و امنیت سرمایه شما به هم گره می‌خورند. "
        "افتخار داریم که در انتخاب و تصاحب زیباترین و ماندگارترین آثار طلا، همراهِ خوش‌سلیقگی شما باشیم. 💎\n\n"
        "🛍 برای مشاهده ویترین و استعلام قیمت، می‌توانید از دکمه‌های زیر هر محصول در کانال استفاده کنید."
    )


def txt_inquiry(product: dict, calc: dict) -> str:
    return (
        "✨ انتخابی بی‌نظیر برای سرمایه‌گذاری!\n\n"
        f"💎 {product['name']}\n"
        f"🥇 قیمت لحظه‌ای هر گرم طلای ۱۸ عیار: {fmt(calc['gold_price'])} تومان\n"
        f"💳 ارزش نهایی این اثر: {fmt(calc['total'])} تومان"
    )


def txt_register_prompt() -> str:
    return (
        f"👋 به {config.SHOP_NAME} خوش آمدید!\n\n"
        "برای ثبت سفارش و مشاهده پیش‌فاکتور، لطفاً ابتدا *نام و نام خانوادگی* خود را ارسال کنید:"
    )


def txt_ask_full_name() -> str:
    return "لطفاً نام و نام خانوادگی خود را به صورت کامل جهت صدور فاکتور رسمی وارد کنید:"


def txt_ask_phone(name: str) -> str:
    return (
        f"ممنون از همراهی‌تان {md_safe(name)} عزیز. ✨\n"
        f"حالا برای تایید نهایی حساب امنیتی خود در {config.SHOP_NAME}، لطفا روی دکمه زیر کلیک کنید:"
    )


def txt_returning_confirm(product: dict, calc: dict) -> str:
    return (
        "سلام دوست عزیزم، خوشحالم که دوباره بهمون سر زدی! ❤️\n\n"
        f"آیا از خرید محصول *{md_safe(product['name'])}* "
        f"به وزن *{product['weight']} گرم* "
        f"و قیمت *{fmt(calc['total'])} تومان* مطمئن هستید تا سفارشتون ثبت بشه؟"
    )


def txt_new_customer_confirm(name: str, product: dict, calc: dict) -> str:
    return (
        f"👋 {md_safe(name)} عزیز، عضویت شما در باشگاه مشتریان ویژه {config.SHOP_NAME} با موفقیت فعال شد! ✨\n\n"
        f"پیش‌فاکتور رسمی و اختصاصی شما برای محصولِ خوش‌ساخت *{md_safe(product['name'])}* آماده است:\n"
        f"⚖️ وزن: {product['weight']} گرم\n"
        f"💰 ارزش نهایی: *{fmt(calc['total'])} تومان*\n\n"
        "آیا از ثبت نهایی این سرمایه‌گذاری درخشان مطمئن هستید؟"
    )


def txt_order_done(name: str, order_id: str) -> str:
    contact = f"تماس مستقیم: {config.SHOP_PHONE}\n" if config.SHOP_PHONE else ""
    return (
        "*سفارش ثبت شد!*\n\n"
        f"{md_safe(name)} عزیز\n"
        f"کد سفارش: `{order_id}`\n\n"
        "کارشناسان ما در اسرع وقت باهات تماس میگیرن.\n"
        f"{contact}"
        f"*{config.SHOP_NAME}*"
    )


# --- admin ---------------------------------------------------------------------

def txt_admin_order(name, user_id, phone, product_info, order_id, total) -> str:
    return (
        "🔔 *سفارش جدید!*\n\n"
        f"👤 نام: {md_safe(name)}\n"
        f"🆔 آیدی: `{user_id}`\n"
        f"📞 شماره: {phone}\n\n"
        f"📦 محصول: {md_safe(product_info)}\n\n"
        f"💰 فاکتور: *{fmt(total)} تومان*\n"
        f"🔖 کد: `{order_id}`"
    )


def txt_admin_menu() -> str:
    price, source = resolve_price()
    price_str = f"*{fmt(price)} تومان*  ({source})" if price > 0 else "❌ تنظیم نشده"
    return (
        f"*پنل مدیریت {config.SHOP_NAME}*\n\n"
        f"💰 قیمت طلا: {price_str}\n"
        f"📦 محصولات فعال: {len(db.get_all_products())}\n"
        f"🛒 سفارش‌های امروز: {len(db.get_today_orders())}\n\n"
        "یکی از گزینه‌ها رو انتخاب کن:"
    )


def txt_current_price() -> str:
    price, source = resolve_price()
    if price > 0:
        return f"💰 قیمت طلای ۱۸ عیار:\n*{fmt(price)} تومان*\nمنبع: {source}"
    return "⚠️ قیمت طلا هنوز تنظیم نشده."


def txt_today_report() -> str:
    orders = db.get_today_orders()
    date_str = datetime.now().strftime("%Y/%m/%d")
    if not orders:
        return f"📊 *گزارش امروز — {date_str}*\n\nهیچ سفارشی ثبت نشده."

    total_revenue = sum(o["total_price"] for o in orders)
    lines = [
        f"📊 *گزارش امروز — {date_str}*\n",
        f"🛒 تعداد سفارش‌ها: *{len(orders)}* عدد",
        f"💰 جمع فروش: *{fmt(total_revenue)} تومان*",
        f"\n{'─' * 25}",
    ]
    for i, o in enumerate(orders, 1):
        t = datetime.fromtimestamp(o["created_at"]).strftime("%H:%M")
        lines.append(
            f"\n*{i}.* {md_safe(o['user_name'])}\n"
            f"   📞 {o['phone']}\n"
            f"   📦 {md_safe(o['product_info'])}\n"
            f"   💰 {fmt(o['total_price'])} تومان  |  🕐 {t}\n"
            f"   🔖 `{o['order_id']}`"
        )
    return "\n".join(lines)


def txt_pm_menu() -> str:
    products = db.get_all_products()
    sold = sum(1 for p in products if p.get("sold"))
    return (
        "📦 *مدیریت محصولات*\n\n"
        f"تعداد کل: {len(products)}\n"
        f"🟢 موجود: {len(products) - sold}\n"
        f"🔴 فروخته شده: {sold}\n\n"
        "یکی از گزینه‌ها رو انتخاب کن.\n"
        "💡 راه سریع‌تر: پست محصول رو از کانال برای ربات فوروارد کن، "
        "یا شناسه‌اش (مثل #365) رو بفرست."
    )


def txt_pm_card(p: dict) -> str:
    tag = f"  #{p['num']}" if p.get("num") else ""
    status = "🔴 فروخته شده" if p.get("sold") else "🟢 موجود"
    linked = "✅ وصل است" if p.get("message_id") else "⚠️ وصل نیست (پست رو از کانال فوروارد کن)"
    return (
        f"📦 *{md_safe(p['name'])}*{tag}\n\n"
        f"⚖️ وزن: {p['weight']} گرم  |  اجرت: {p['wage_percent']}٪\n"
        f"وضعیت: {status}\n"
        f"پست کانال: {linked}"
    )
