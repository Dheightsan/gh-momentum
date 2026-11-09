"""Thin GitHub Search API client. Pure standard library, zero dependencies.

The GitHub Search API is free: 10 requests per minute without a token and 30
per minute with a personal access token. Set the ``GITHUB_TOKEN`` environment
variable (or pass ``token=``) to raise the limit.

Star velocity is stars divided by the repo's real age (from ``created_at``,
in UTC, with a floor of one day). If ``created_at`` is missing or unreadable,
the age falls back to the ``days_back`` window and a warning is logged.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger("gh_momentum.github_api")

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 12
_SECONDS_PER_DAY = 86400.0


def _headers(token: str | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gh-momentum",
    }
    token = token or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, token: str | None = None) -> dict | list | None:
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            log.warning(
                "GitHub API rate limit hit (HTTP %s). The Search API allows "
                "10 requests/min without a token and 30/min with one; set "
                "GITHUB_TOKEN to use the higher limit.",
                e.code,
            )
        else:
            log.warning("GitHub API HTTP %s: %s", e.code, url)
        return None
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        log.warning("GitHub API request failed (%s): %s", e, url)
        return None
    except ValueError as e:
        log.warning("GitHub API returned invalid JSON (%s): %s", e, url)
        return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and convert aware ones to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_created_at(value: object) -> datetime | None:
    """Parse a GitHub ``created_at`` (ISO 8601) into an aware UTC datetime.

    Returns None if the value is missing or unreadable. The trailing ``Z`` is
    rewritten to ``+00:00`` because ``datetime.fromisoformat`` rejects it on
    Python 3.9 and 3.10.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return _as_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _normalise(
    item: dict, days_back: int, now: datetime | None = None
) -> dict:
    """Turn a GitHub search item into the dict the scorer expects.

    ``star_velocity_per_day`` is ``stars / age``, where age is the time since
    ``created_at`` in fractional days (UTC, at least 1 day). When
    ``created_at`` cannot be read, the age is ``days_back``. ``now`` can be
    injected for deterministic tests.
    """
    stars = item.get("stargazers_count", 0) or 0
    name = item.get("full_name", "")
    raw_created = item.get("created_at", "")

    created = _parse_created_at(raw_created)
    if created is None:
        age_days = float(max(1, days_back))
        log.warning(
            "%s: created_at %r is missing or unreadable; using days_back=%s "
            "as the age for star velocity.",
            name or "<unnamed repo>", raw_created, days_back,
        )
    else:
        current = _as_utc(now) if now is not None else _utcnow()
        age_days = max(
            1.0, (current - created).total_seconds() / _SECONDS_PER_DAY
        )

    return {
        "name": name,
        "description": (item.get("description") or "")[:280],
        "stars": stars,
        "star_velocity_per_day": round(stars / age_days, 1),
        "language": item.get("language") or "unknown",
        "topics": (item.get("topics") or [])[:10],
        "url": item.get("html_url", ""),
        "created_at": raw_created,
        "forks": item.get("forks_count", 0),
    }


def _normalise_items(
    data: object, days_back: int, now: datetime, source: str
) -> list[dict]:
    """Normalise a search response, logging every item it has to skip."""
    if data is None:
        return []  # _get already logged why the request failed
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        log.warning(
            "%s: response has no 'items' list; returning no repos.", source
        )
        return []
    repos: list[dict] = []
    skipped = 0
    for index, item in enumerate(data["items"]):
        if not isinstance(item, dict):
            skipped += 1
            log.warning(
                "%s: item %d is %s, not an object; skipped.",
                source, index, type(item).__name__,
            )
            continue
        repos.append(_normalise(item, days_back, now=now))
    log.info(
        "%s: %d items received, %d normalised, %d skipped.",
        source, len(data["items"]), len(repos), skipped,
    )
    return repos


def _search_url(query: str, max_results: int) -> str:
    return (
        f"{_GITHUB_API}/search/repositories"
        f"?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={min(max_results, 100)}"
    )


def fetch_trending_repos(
    days_back: int = 7,
    min_stars: int = 30,
    max_results: int = 30,
    token: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Repos created in the last ``days_back`` days, ranked by stars."""
    current = _as_utc(now) if now is not None else _utcnow()
    since = (current - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>{min_stars}"
    data = _get(_search_url(query, max_results), token)
    return _normalise_items(data, days_back, current, "trending search")


def fetch_repos_by_topic(
    topic: str,
    days_back: int = 30,
    min_stars: int = 10,
    max_results: int = 15,
    token: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Repos tagged with ``topic`` that were pushed in the last ``days_back`` days."""
    current = _as_utc(now) if now is not None else _utcnow()
    since = (current - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"topic:{topic} pushed:>{since} stars:>{min_stars}"
    data = _get(_search_url(query, max_results), token)
    return _normalise_items(data, days_back, current, f"topic search '{topic}'")
