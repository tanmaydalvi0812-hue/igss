# Telegram + Playwright Render bot

This is a Render-compatible Telegram webhook bot using Playwright/Chromium.
It intentionally does not include account creation, proxy rotation, password
collection, verification-code harvesting, or 2FA bypass/setup.

## Render

Build command:
pip install -r requirements.txt && playwright install --with-deps chromium

Start command:
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 bot:app

Environment variables:
TELEGRAM_BOT_TOKEN = your BotFather token
PUBLIC_URL = your Render URL, e.g. https://telegram-playwright-ig-bot.onrender.com
TARGET_URL = https://www.instagram.com/

After deployment, open:
https://YOUR-RENDER-URL/setup-webhook

Then open Telegram and send /start.
