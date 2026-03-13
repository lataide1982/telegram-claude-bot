import os
import logging
import anthropic
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ── Env vars ───────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not set")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Flask health check ─────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot is running!", 200

# ── Telegram handlers ──────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm Claude. Ask me anything!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    logger.info(f"Message from {update.effective_user.id}: {user_message[:50]}")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": user_message}]
        )
        reply = message.content[0].text
        await update.message.reply_text(reply)

    except anthropic.APIConnectionError as e:
        logger.error(f"Claude connection error: {e}")
        await update.message.reply_text("⚠️ Connection issue. Please try again in a moment.")

    except anthropic.RateLimitError as e:
        logger.error(f"Claude rate limit: {e}")
        await update.message.reply_text("⚠️ Too many requests. Please wait a few seconds.")

    except anthropic.APIStatusError as e:
        logger.error(f"Claude API error {e.status_code}: {e.message}")
        await update.message.reply_text("⚠️ API error. Please try again.")

    except Exception as e:
        logger.error(f"Unexpected error in handle_message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")

# ── Global error handler ───────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Telegram bot error: {context.error}", exc_info=context.error)

# ── Bot runner with auto-restart ───────────────────────────────
async def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("Bot is polling...")

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:  # Auto-restart loop
        try:
            logger.info("Starting bot...")
            loop.run_until_complete(run_bot())
            loop.run_forever()
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            logger.info("Restarting bot in 5 seconds...")
            import time
            time.sleep(5)

# ── Entry point ────────────────────────────────────────────────
thread = threading.Thread(target=start_bot_thread, daemon=True)
thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask on port {port}")
    app_flask.run(host="0.0.0.0", port=port)
