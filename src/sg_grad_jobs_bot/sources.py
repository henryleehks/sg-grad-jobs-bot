from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; sg-grad-jobs-bot/1.0)"
MIN_RESULTS_BEFORE_RELAXING = 5
ROLE_KEYWORDS = (
    "software engineer",
    "software developer",
    "backend engineer",
    "backend developer",
    "frontend engineer",
    "frontend developer",
    "front end engineer",
    "front end developer",
    "full stack engineer",
    "fullstack engineer",
    "platform engineer",
    "devops",
    "site reliability engineer",
    "sre",
)
ENTRY_LEVEL_KEYWORDS = (
    "graduate",
    "graduate program",
    "graduate programme",
    "fresh",
    "entry",
    "entry-level",
    "junior",
    "associate",
    "new grad",
    "newgrad",
    "early career",
    "campus",
    "university graduate",
    "0-2 years",
    "0 to 2 years",
    "1-2 years",
    "1 to 2 years",
    "intern",
    "internship",
)
SENIORITY_EXCLUDE_KEYWORDS = (
    "senior",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "head of",
    "vp",
)
INDEED_QUERIES = (
    "software engineer graduate",
    "graduate software engineer",
    "junior software engineer",
    "entry level software engineer",
    "backend engineer graduate",
    "junior backend engineer",
    "frontend engineer graduate",
    "junior frontend engineer",
    "platform engineer graduate",
    "junior platform engineer",
    "devops engineer graduate",
    "junior devops engineer",
    "site reliability engineer graduate",
    "software engineer internship",
)
GREENHOUSE_BOARD_TOKENS = (
    "stripe",
    "airwallex",
    "datadog",
)
LEVER_COMPANIES = (
    "nubank",
    "coinbase",
    "shopback",
    "csit",
    "palantir",
    "addx",
)


@dataclass(frozen=True)
class Job:
    source: str
    company: str
    title: str
    location: str
    url: str
    posted_at: datetime | None
    match_strength: str = "strict"


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
            match_strength = _match_strength(title, description)

            if pub_date and pub_date < min_date:
                continue
            if match_strength == "none":
                continue

            jobs.append(
                Job(
                    source=self.name,
                    company=company or "Unknown",
                    title=title,
                    location=location or "Singapore",
                    url=link,
                    posted_at=pub_date,
                    match_strength=match_strength,
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
            match_strength = _match_strength(title, content)
            if match_strength == "none":
                continue

            jobs.append(
                Job(
                    source=f"{self.name}:{self.board_token}",
                    company=self.board_token,
                    title=title,
                    location=location,
                    url=row.get("absolute_url", ""),
                    posted_at=updated_at,
                    match_strength=match_strength,
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
            match_strength = _match_strength(title, description)
            if match_strength == "none":
                continue

            jobs.append(
                Job(
                    source=f"{self.name}:{self.company}",
                    company=self.company,
                    title=title,
                    location=location,
                    url=row.get("hostedUrl", ""),
                    posted_at=created_at,
                    match_strength=match_strength,
                )
            )
        return jobs


def fetch_jobs(days_back: int, max_results: int) -> list[Job]:
    sources: Iterable[BaseSource] = [
        *(IndeedRssSource(query) for query in INDEED_QUERIES),
        *(GreenhouseSource(token) for token in GREENHOUSE_BOARD_TOKENS),
        *(LeverSource(company) for company in LEVER_COMPANIES),
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
        key=lambda j: (
            j.match_strength != "strict",
            -(j.posted_at or datetime(1970, 1, 1, tzinfo=timezone.utc)).timestamp(),
        ),
    )

    strict_jobs = [job for job in sorted_jobs if job.match_strength == "strict"]
    if len(strict_jobs) >= min(max_results, MIN_RESULTS_BEFORE_RELAXING):
        return strict_jobs[:max_results]

    final_jobs: list[Job] = []
    seen_keys: set[str] = set()
    for job in sorted_jobs:
        key = job.url or f"{job.company}-{job.title}-{job.location}"
        if key in seen_keys:
            continue

        if job.match_strength == "strict" or len(strict_jobs) < MIN_RESULTS_BEFORE_RELAXING:
            final_jobs.append(job)
            seen_keys.add(key)

        if len(final_jobs) >= max_results:
            break

    return final_jobs


def format_jobs(jobs: list[Job]) -> str:
    if not jobs:
        return "No fresh SG graduate Software/DevOps roles found right now. Try again later."

    lines = ["Fresh / Early-Career SE / DevOps roles in Singapore", ""]
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
    return _match_strength(title, body) != "none"


def _match_strength(title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    title_lower = title.lower()
    role_ok = any(k in text for k in ROLE_KEYWORDS)
    level_ok = any(k in text for k in ENTRY_LEVEL_KEYWORDS)
    seniority_excluded = any(k in title_lower for k in SENIORITY_EXCLUDE_KEYWORDS)
    if not role_ok or seniority_excluded:
        return "none"
    if level_ok:
        return "strict"
    return "relaxed"


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
