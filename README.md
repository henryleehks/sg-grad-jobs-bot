# SG Grad Jobs Bot (Telegram)

A Telegram bot + CLI that scrapes fresh graduate **Software Engineer** and **DevOps Engineer** roles in **Singapore**.

## What it does

- Aggregates job postings from:
  - Indeed Singapore RSS queries
  - Greenhouse public boards
  - Lever public postings
- Filters for:
  - Singapore location
  - Software Engineer / DevOps roles
  - Fresh grad / entry-level intent (keywords like "graduate", "junior", "new grad")
- Returns newest-first results.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Recommended: Python 3.10+ (tested broadly on 3.10-3.14 with current dependencies).

Create `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
DAYS_BACK=14
MAX_RESULTS=20
```

## Run as Telegram bot

```bash
PYTHONPATH=src python -m sg_grad_jobs_bot.bot
```

Commands:

- `/start`
- `/search`

### If you hit a startup traceback on Python 3.14

- Upgrade dependencies: `pip install -U -r requirements.txt`
- This repo pins `python-telegram-bot==22.7`, which includes newer Python 3.14 compatibility improvements.

## Run as CLI

```bash
PYTHONPATH=src python -m sg_grad_jobs_bot.cli --days-back 14 --max-results 20
```

## Notes

- This project uses only publicly accessible endpoints/pages.
- Some sources may rate-limit or block requests over time.
- You can edit company sources in `src/sg_grad_jobs_bot/sources.py`.
