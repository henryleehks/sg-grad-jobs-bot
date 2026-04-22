from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; sg-grad-jobs-bot/1.0)"
ROLE_KEYWORDS = ("software engineer", "devops")
ENTRY_LEVEL_KEYWORDS = ("graduate", "fresh", "entry", "junior", "associate", "new grad")


@dataclass(frozen=True)
class Job:
    source: str
    company: str
    title: str
    location: str
    url: str
    posted_at: datetime | None


class BaseSource:
    name = "base"

    def fetch(self, days_back: int) -> list[Job]:
        raise NotImplementedError


class IndeedRssSource(BaseSource):
    name = "Indeed (SG)"

    def __init__(self, query: str):
        self.query = query

    def fetch(self, days_back: int) -> list[Job]:
        url = "https://sg.indeed.com/rss"
        resp = requests.get(
            url,
            params={"q": self.query, "l": "Singapore", "sort": "date"},
            timeout=20,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.text)
        min_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        jobs: list[Job] = []
        for item in root.findall("./channel/item"):
            title = _text(item, "title")
            company = _parse_company(_text(item, "author"))
            link = _text(item, "link")
            description = _text(item, "description")
            location = _extract_location(description)
            pub_date = _parse_rfc822(_text(item, "pubDate"))

            if pub_date and pub_date < min_date:
                continue
            if not _is_relevant(title, description):
                continue

            jobs.append(
                Job(
                    source=self.name,
                    company=company or "Unknown",
                    title=title,
                    location=location or "Singapore",
                    url=link,
                    posted_at=pub_date,
                )
            )
        return jobs


class GreenhouseSource(BaseSource):
    name = "Greenhouse"

    def __init__(self, board_token: str):
        self.board_token = board_token

    def fetch(self, days_back: int) -> list[Job]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
        resp = requests.get(
            url,
            params={"content": "true"},
            timeout=25,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json().get("jobs", [])
        min_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        jobs: list[Job] = []
        for row in data:
            title = row.get("title", "")
            location = (row.get("location") or {}).get("name", "")
            if "singapore" not in location.lower():
                continue

            updated_at = _parse_iso_datetime(row.get("updated_at"))
            if updated_at and updated_at < min_date:
                continue

            content = BeautifulSoup(row.get("content", ""), "html.parser").get_text(" ")
            if not _is_relevant(title, content):
                continue

            jobs.append(
                Job(
                    source=f"{self.name}:{self.board_token}",
                    company=self.board_token,
                    title=title,
                    location=location,
                    url=row.get("absolute_url", ""),
                    posted_at=updated_at,
                )
            )
        return jobs


class LeverSource(BaseSource):
    name = "Lever"

    def __init__(self, company: str):
        self.company = company

    def fetch(self, days_back: int) -> list[Job]:
        url = f"https://api.lever.co/v0/postings/{self.company}"
        resp = requests.get(
            url,
            params={"mode": "json"},
            timeout=25,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()
        min_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        jobs: list[Job] = []
        for row in data:
            title = row.get("text", "")
            location = (row.get("categories") or {}).get("location", "")
            if "singapore" not in location.lower():
                continue

            created_at = _parse_epoch_ms(row.get("createdAt"))
            if created_at and created_at < min_date:
                continue

            description = BeautifulSoup(row.get("description", ""), "html.parser").get_text(" ")
            if not _is_relevant(title, description):
                continue

            jobs.append(
                Job(
                    source=f"{self.name}:{self.company}",
                    company=self.company,
                    title=title,
                    location=location,
                    url=row.get("hostedUrl", ""),
                    posted_at=created_at,
                )
            )
        return jobs


def fetch_jobs(days_back: int, max_results: int) -> list[Job]:
    sources: Iterable[BaseSource] = [
        IndeedRssSource("software engineer graduate"),
        IndeedRssSource("devops engineer graduate"),
        GreenhouseSource("stripe"),
        GreenhouseSource("airwallex"),
        GreenhouseSource("datadog"),
        LeverSource("nubank"),
        LeverSource("coinbase"),
        LeverSource("shopback"),
    ]

    jobs: list[Job] = []
    for source in sources:
        try:
            jobs.extend(source.fetch(days_back=days_back))
        except Exception:
            continue

    dedup: dict[str, Job] = {}
    for job in jobs:
        key = job.url or f"{job.company}-{job.title}-{job.location}"
        dedup[key] = job

    sorted_jobs = sorted(
        dedup.values(),
        key=lambda j: j.posted_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )
    return sorted_jobs[:max_results]


def format_jobs(jobs: list[Job]) -> str:
    if not jobs:
        return "No fresh SG graduate Software/DevOps roles found right now. Try again later."

    lines = ["Fresh Graduate SE / DevOps roles in Singapore", ""]
    for idx, job in enumerate(jobs, start=1):
        when = job.posted_at.date().isoformat() if job.posted_at else "Unknown date"
        lines.append(
            f"{idx}. {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"Source: {job.source}\n"
            f"Posted: {when}\n"
            f"Apply: {job.url}"
        )
    return "\n\n".join(lines)


def _is_relevant(title: str, body: str) -> bool:
    text = f"{title} {body}".lower()
    role_ok = any(k in text for k in ROLE_KEYWORDS)
    level_ok = any(k in text for k in ENTRY_LEVEL_KEYWORDS)
    return role_ok and level_ok


def _extract_location(description_html: str) -> str:
    txt = BeautifulSoup(description_html, "html.parser").get_text(" ")
    if "Singapore" in txt:
        return "Singapore"
    return ""


def _parse_company(author: str) -> str:
    # Indeed author often looks like "Company Name"
    return author.strip()


def _parse_rfc822(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        clean = value.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).astimezone(timezone.utc)
    except Exception:
        return None


def _parse_epoch_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except Exception:
        return None


def _text(item: ElementTree.Element, tag: str) -> str:
    node = item.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text.strip()
