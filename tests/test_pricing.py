import time

from gold_bot import db, pricing


def test_calculate_price():
    calc = pricing.calculate_price(weight=2.0, wage_pct=20, gold_price=10_000_000)
    assert calc == {"gold_price": 10_000_000, "base": 20_000_000, "wage": 4_000_000, "total": 24_000_000}


def test_calculate_price_rounds_to_whole_toman():
    calc = pricing.calculate_price(1.13, 18, 18_555_000)
    assert calc["base"] == 20_967_150          # 1.13 g * 18,555,000
    assert calc["wage"] == 3_774_087           # 18% of base, rounded
    assert calc["total"] == calc["base"] + calc["wage"] == 24_741_237


def test_channel_price_parsing(database):
    assert pricing.update_price_from_channel("طلای ۱۸ عیار: ۱۸,۵۰۰,۰۰۰") == 18_500_000
    assert db.get_setting("channel_gold_price") == "18500000"


def test_channel_price_parsing_variants(database):
    assert pricing.update_price_from_channel("قیمت امروز\nطلا 18 عیار - 17،900،000 تومان") == 17_900_000


def test_channel_price_ignores_unrelated_and_implausible(database):
    assert pricing.update_price_from_channel("سلام، خوش آمدید") is None
    assert pricing.update_price_from_channel("طلای ۱۸ عیار: ۱۲۳") is None


def test_price_priority_api_first(database, monkeypatch):
    db.set_setting("manual_gold_price", "1000000")
    monkeypatch.setattr(pricing, "fetch_price_from_api", lambda: 20_000_000)
    assert pricing.resolve_price() == (20_000_000, "🌐 API")


def test_price_priority_channel_then_manual(database, monkeypatch):
    monkeypatch.setattr(pricing, "fetch_price_from_api", lambda: None)
    db.set_setting("manual_gold_price", "1000000")
    assert pricing.resolve_price() == (1_000_000, "✏️ دستی")

    db.set_setting("channel_gold_price", "19000000")
    db.set_setting("channel_price_time", str(int(time.time()) - 600))
    price, source = pricing.resolve_price()
    assert price == 19_000_000 and "کانال" in source and "10" in source


def test_stale_channel_price_falls_back_to_manual(database, monkeypatch):
    monkeypatch.setattr(pricing, "fetch_price_from_api", lambda: None)
    db.set_setting("manual_gold_price", "1000000")
    db.set_setting("channel_gold_price", "19000000")
    db.set_setting("channel_price_time", str(int(time.time()) - pricing.CHANNEL_PRICE_TTL - 5))
    assert pricing.resolve_price()[0] == 1_000_000


def test_no_price_at_all(database, monkeypatch):
    monkeypatch.setattr(pricing, "fetch_price_from_api", lambda: None)
    assert pricing.resolve_price() == (0, "❌ تنظیم نشده")
