import os
import tempfile

# Configure the app BEFORE gold_bot is imported anywhere.
_TMP = tempfile.mkdtemp(prefix="gold_bot_tests_")
os.environ.update({
    "BOT_TOKEN": "123456:TEST-TOKEN",
    "ADMIN_IDS": "1001,1002",
    "DATA_DIR": _TMP,
    "GOLD_PRICE_CHANNEL": "@price_channel",
    "SHOP_NAME": "Test Gallery",
    "SHOP_PHONE": "09120000000",
})
os.environ.pop("PRICE_API_URL", None)
os.environ.pop("TABAN_API_URL", None)

import pytest  # noqa: E402

from gold_bot import bale_api, config, db  # noqa: E402


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A fresh, empty database for every test."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return config.DB_PATH


class FakeBale:
    """Records every Bot API call instead of hitting the network."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, payload, retries=3):
        self.calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 555, "chat": {"id": -100123}}}

    def of(self, method):
        return [p for m, p in self.calls if m == method]

    def texts(self):
        return [p.get("text") or p.get("caption") or "" for _, p in self.calls]


@pytest.fixture
def fake(monkeypatch, database):
    f = FakeBale()
    monkeypatch.setattr(bale_api, "api", f)
    return f
