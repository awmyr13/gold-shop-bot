# Gold Shop Bot

A production Bale messenger bot that runs the sales channel of a real gold & jewelry shop in Iran.
It publishes products to a channel, answers live price inquiries, takes customer orders and gives the shop
owners an admin panel, all from inside the messenger.

> **Portfolio note:** this project is in daily use by a real business. It is published as a work sample;
> it is tied to Bale and to a Persian-language shop, so it is not meant as a drop-in product for others.
> The code and documentation are in English; the messages the bot sends to customers are in Persian.

## What it does

**Customers**
- See a product post in the shop channel with **Price inquiry** and **Buy** buttons.
- *Price inquiry* shows the current price in a pop-up: `(weight x gold price) + making charge`.
- *Buy* walks a new customer through registration (name, phone via Bale's contact button), shows a
  pre-invoice and, after confirmation, places the order. Returning customers skip registration.

**Admins** (a fixed list of Bale user ids)
- **Publish a product** with a step-by-step wizard (photo, caption from a template, weight, making charge,
  channel). The bot posts it with a public number such as `#365`.
- **Mark as sold**: the channel post is edited in place (a "SOLD" line is appended and the *Buy* button is
  removed; *Price inquiry* stays).
- **Find a product** by forwarding its channel post to the bot or by sending its number, then edit its
  text, weight or making charge, or delete it.
- Set a manual gold price, see the current price and its source, and get a daily orders report.
- Every new order is sent to all admins instantly.

## How the price is resolved

The 18k price per gram comes from the first source that works:

1. **External JSON API** (optional, always the freshest)
2. **The shop's price channel**: the bot reads posts like `طلای ۱۸ عیار: ۱۸,۵۰۰,۰۰۰` (valid for 2 hours)
3. **Manual price** entered by an admin (permanent fallback)

## Architecture

```
main.py                 entry point
gold_bot/
  app.py                polling loop, bounded thread pool, graceful shutdown, logging
  config.py             all settings from environment variables, startup validation
  bale_api.py           Bale Bot API client (rate limiting, retries, token redaction in logs)
  db.py                 SQLite layer (WAL mode, migrations, conversation state with expiry)
  pricing.py            price sources and price calculation
  posts.py              channel post caption building / editing / "sold" mark
  keyboards.py          reply and inline keyboards
  texts.py              user-facing message texts
  handlers/
    messages.py         routes messages: price channel / admin / customer
    admin.py            admin wizard, product lookup, menu buttons
    customer.py         customer registration flow
    callbacks.py        inline button actions (inquiry, buy, confirm, product management)
tests/                  pytest suite (unit tests + end-to-end conversation flows)
```

Design notes:
- **Long polling** with a bounded `ThreadPoolExecutor`, so a burst of updates cannot spawn unlimited threads.
- **Per-call SQLite connections** in WAL mode with a busy timeout, safe for concurrent handlers.
- **Conversation state is stored in the database** with a one-hour expiry, so a restart does not lose a
  half-finished wizard.
- **Secrets stay out of the code and the logs.** The bot token and price API URL come from the environment,
  and exception text is redacted before logging (HTTP errors include the request URL, which contains the token).
- **User input is sanitized** before being placed into Markdown messages, so a customer name like `Ali_*`
  cannot make Bale reject the admin's order notification.
- Duplicate-order protection, parameterized SQL, and a whitelist for editable product fields.

## Setup

Tested on Python 3.12. Requires a bot token from Bale's BotFather.

```bash
git clone <this repo> && cd gold-shop-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then edit .env: BOT_TOKEN, ADMIN_IDS, shop details
python main.py
```

The bot must be an **administrator of the product channel** to post and edit there. To use the price channel
as a source, add the bot to it as well.

### Docker

```bash
cp .env.example .env      # fill it in
docker compose up -d --build
```

The SQLite database and logs are stored in `./data` (mounted at `/app/backups`).

### Configuration

All settings are environment variables; see [`.env.example`](.env.example) for the full list.
`BOT_TOKEN` and `ADMIN_IDS` are required, the bot refuses to start without them.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite replaces the Bale API with a recorder, so it runs offline. It covers price parsing and priority,
order flow including duplicate clicks, the admin publishing wizard, marking products as sold, and that
non-admins cannot reach admin features.

## Security notes

- Never commit `.env`, the database or log files (all are in `.gitignore`). The database contains customer
  names and phone numbers.
- If a token was ever committed, revoke it in BotFather; deleting it from a later commit is not enough.

## Tech stack

Python, SQLite, `requests`, `python-dotenv`, pytest, Docker, GitHub Actions.

## License

MIT, see [LICENSE](LICENSE). Author: Amir Jafarian.
