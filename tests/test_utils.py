from gold_bot import config
from gold_bot.utils import fa_to_en, fmt, md_safe, redact


def test_fa_to_en():
    assert fa_to_en("۱۲۳٫۵") == "123.5"
    assert fa_to_en("٠١٢") == "012"
    assert fa_to_en(None) == ""


def test_fmt():
    assert fmt(18500000) == "18,500,000"
    assert fmt("abc") == "abc"


def test_md_safe():
    assert md_safe("Ali_*Reza`[x]") == "AliRezax"


def test_redact_hides_bot_token():
    err = f"HTTPSConnectionPool: Max retries exceeded with url: /bot{config.BOT_TOKEN}/sendMessage"
    assert config.BOT_TOKEN not in redact(err)
    assert "***" in redact(err)


def test_admin_ids_are_parsed():
    assert config.ADMIN_IDS == [1001, 1002]
    assert config._parse_ids("1, 2,x,,3") == [1, 2, 3]
