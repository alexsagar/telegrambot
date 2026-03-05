"""conftest – set dummy environment variables before any app imports."""

import os

# Must be set before app.config is imported
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-not-real")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB_NAME", "ledger_bot_test")
