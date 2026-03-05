# Telegram Ledger Bot

A production-grade Telegram bot that tracks IN/OUT transactions across linked groups and posts live totals.

## Features

- **Transaction tracking** – Posts in IN/OUT groups matching `<amount> to <person>` are automatically recorded
- **Live totals** – A single message in the DAILY REPORT group is continuously edited with current totals
- **Edit handling** – Message edits are processed with delta correction (only final amount counts)
- **Void support** – Admins can `/void` a transaction by replying to it
- **Daily cutover** – Accounting periods run 8:00 PM → 8:00 PM (Asia/Kathmandu), with automatic "Day Closed" summaries
- **Race-safe** – Uses MongoDB `$inc` upserts and `find_one_and_update` for atomic operations

## Prerequisites

- Python 3.11+
- MongoDB 6+ (or 7 recommended)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Bot Setup in BotFather

1. Create a bot via `/newbot`
2. **Disable Privacy Mode**: Go to Bot Settings → Group Privacy → Turn Off
3. Add the bot as **admin** to all three groups (IN, OUT, DAILY REPORT)

## Quick Start (Local)

```bash
# 1. Clone and enter the directory
cd telegram

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your bot token and chat IDs

# 5. Start MongoDB (must be running on localhost:27017)

# 6. Run the bot
python -m app.main
```

## Quick Start (Docker)

```bash
# 1. Configure environment
copy .env.example .env
# Edit .env with your bot token

# 2. Build and run
docker-compose up --build -d

# 3. View logs
docker-compose logs -f bot
```

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
telegram/
├── app/
│   ├── __init__.py
│   ├── config.py            # Pydantic settings from .env
│   ├── logging_config.py    # Structured JSON logging
│   ├── models.py            # Domain models (Pydantic + dataclasses)
│   ├── timeutils.py         # Period boundary computation
│   ├── parsing.py           # Transaction text parser
│   ├── db.py                # MongoDB connection + indexes
│   ├── repositories.py      # Data access layer
│   ├── services.py          # Business logic (delta, void, totals)
│   ├── telegram_handlers.py # Message & command handlers
│   ├── scheduler.py         # APScheduler daily cutover job
│   └── main.py              # Application entry point
├── tests/
│   ├── conftest.py
│   ├── test_parsing.py
│   ├── test_timeutils.py
│   └── test_services.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Transaction Format

Post messages in the IN or OUT groups in this format:

```
<amount> to <person>
```

Examples:
- `15 to jazz13gv`
- `10.5 to quanshan13gv`
- `100 TO BigPlayer`

## Commands

| Command | Where | Who | Description |
|---------|-------|-----|-------------|
| `/void` | IN/OUT group | Admins only | Reply to a transaction to void it |

## Accounting Periods

- A "day" runs from **8:00 PM NPT** to the next day's **8:00 PM NPT**
- At 8:00 PM, the bot posts a "Day Closed" summary and starts a new period
- Totals message resets for each new period

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather | *required* |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB_NAME` | Database name | `ledger_bot` |
| `IN_CHAT_ID` | Chat ID of the IN group | `-1001852638516` |
| `OUT_CHAT_ID` | Chat ID of the OUT group | `-1001816909345` |
| `REPORT_CHAT_ID` | Chat ID of the DAILY REPORT group | `-1003746938542` |
| `TIMEZONE` | Timezone for accounting | `Asia/Kathmandu` |
| `DAY_CUTOVER_HOUR` | Hour (24h) when periods roll over | `20` |
| `LOG_LEVEL` | Logging level | `INFO` |
