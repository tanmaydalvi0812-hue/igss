import os
import threading
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
TARGET_URL = os.environ.get("TARGET_URL", "https://www.instagram.com/").strip()

if not BOT_TOKEN:
    print("WARNING: TELEGRAM_BOT_TOKEN is not set.")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

state = {
    "running": False,
    "last_url": None,
    "last_title": None,
    "last_error": None,
}


def telegram(method, payload=None):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    r = requests.post(f"{TG_API}/{method}", json=payload or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def send_message(chat_id, text):
    return telegram("sendMessage", {
        "chat_id": chat_id,
        "text": text,
    })


def allowed_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.netloc.lower().endswith(
        ("instagram.com", "www.instagram.com")
    )


def visit_instagram(chat_id, url=None):
    if state["running"]:
        send_message(chat_id, "⏳ A browser task is already running.")
        return

    target = url or TARGET_URL

    if not allowed_url(target):
        send_message(chat_id, "❌ Only Instagram URLs are allowed.")
        return

    state["running"] = True
    state["last_error"] = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()

            page.goto(target, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            state["last_url"] = page.url
            state["last_title"] = page.title()

            send_message(
                chat_id,
                f"✅ Browser task completed.\n\n"
                f"URL: {page.url}\n"
                f"Title: {page.title() or '(no title)'}"
            )

            browser.close()

    except Exception as exc:
        state["last_error"] = str(exc)
        send_message(chat_id, f"❌ Browser error:\n{exc}")

    finally:
        state["running"] = False


def handle_update(update):
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == "/start":
        send_message(
            chat_id,
            "🤖 Render Instagram Playwright Bot\n\n"
            "/status - show service status\n"
            "/open - open Instagram\n"
            "/open <Instagram URL> - open an Instagram URL\n\n"
            "This bot does not create accounts, collect passwords/2FA codes, "
            "rotate proxies, or bypass Instagram security."
        )

    elif text == "/status":
        error = state["last_error"] or "none"
        send_message(
            chat_id,
            f"🟢 Service: online\n"
            f"🌐 Browser: {'running' if state['running'] else 'idle'}\n"
            f"🔗 Last URL: {state['last_url'] or 'none'}\n"
            f"⚠️ Last error: {error}"
        )

    elif text == "/open":
        threading.Thread(
            target=visit_instagram,
            args=(chat_id, TARGET_URL),
            daemon=True,
        ).start()
        send_message(chat_id, "🌐 Starting Playwright...")

    elif text.startswith("/open "):
        url = text[6:].strip()
        threading.Thread(
            target=visit_instagram,
            args=(chat_id, url),
            daemon=True,
        ).start()
        send_message(chat_id, "🌐 Starting Playwright...")

    else:
        send_message(chat_id, "Use /start to see the available commands.")


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "Telegram + Playwright Render bot",
        "browser_running": state["running"],
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    try:
        update = request.get_json(silent=True) or {}
        handle_update(update)
        return jsonify({"ok": True})
    except Exception as exc:
        print("Webhook error:", exc)
        return jsonify({"ok": False}), 500


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    if not PUBLIC_URL:
        return jsonify({
            "ok": False,
            "error": "Set PUBLIC_URL to your Render service URL first."
        }), 400

    webhook_url = f"{PUBLIC_URL}/telegram/webhook"
    result = telegram("setWebhook", {"url": webhook_url})
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
