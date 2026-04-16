from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from sg_grad_jobs_bot.config import Settings
from sg_grad_jobs_bot.sources import fetch_jobs, format_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I can find fresh graduate Software Engineer / DevOps jobs in Singapore.\n"
        "Use /search to fetch current roles."
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text("Scraping now... this can take ~10-20 seconds.")

    jobs = await asyncio.to_thread(
        fetch_jobs,
        days_back=settings.default_days_back,
        max_results=settings.max_results,
    )
    message = format_jobs(jobs)
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


def run() -> None:
    load_dotenv()
    settings = Settings.from_env()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run()
