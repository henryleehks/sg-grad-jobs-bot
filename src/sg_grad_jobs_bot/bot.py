from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from sg_grad_jobs_bot.config import Settings
from sg_grad_jobs_bot.sources import fetch_jobs, format_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_TELEGRAM_MESSAGE_LENGTH = 4000


def _chunk_message(message: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    if len(message) <= max_length:
        return [message]

    chunks: list[str] = []
    remaining = message.strip()
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n\n", 0, max_length)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:max_length].strip()
            split_at = max_length
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I can find fresh graduate Software Engineer / DevOps jobs in Singapore.\n"
        "Use /search to fetch current roles."
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text("Scraping now... this can take ~10-20 seconds.")
    try:
        jobs = await asyncio.to_thread(
            fetch_jobs,
            days_back=settings.default_days_back,
            max_results=settings.max_results,
        )
        message = format_jobs(jobs)
        for chunk in _chunk_message(message):
            await update.message.reply_text(
                chunk,
                disable_web_page_preview=True,
            )
    except Exception:
        logger.exception("Search command failed")
        await update.message.reply_text(
            "Something went wrong while fetching jobs. Please try again in a bit."
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
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except RuntimeError as exc:
        # Work around event-loop bootstrap differences seen on some Python 3.14 setups.
        if "no running event loop" not in str(exc).lower():
            raise
        logger.warning("Retrying run_polling with an explicit event loop: %s", exc)
        asyncio.set_event_loop(asyncio.new_event_loop())
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run()
