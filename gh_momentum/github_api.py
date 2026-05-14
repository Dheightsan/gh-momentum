"""Thin GitHub Search API client — pure standard library, zero dependencies.

The GitHub Search API is free: 60 requests/hour unauthenticated, 5,000/hour
with a personal access token. Set the ``GITHUB_TOKEN`` environment variable
(or pass ``token=``) to raise the limit.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

log = logging.getLogger("gh_momentum.github_api")

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 12


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
                "GitHub API rate limit hit. Set GITHUB_TOKEN to raise it "
                "(60 -> 5,000 requests/hour)."
            )
        else:
            log.warning("GitHub API HTTP %s: %s", e.code, url)
        return None
    except Exception as e:  # noqa: BLE001 - network is best-effort
        log.warning("GitHub API error %s: %s", url, e)
        return None


def _normalise(item: dict, age_days: int) -> dict:
    stars = item.get("stargazers_count", 0)
    return {
        "name": item.get("full_name", ""),
        "description": (item.get("description") or "")[:280],
        "stars": stars,
        "star_velocity_per_day": round(stars / max(1, age_days), 1),
        "language": item.get("language") or "unknown",
        "topics": (item.get("topics") or [])[:10],
        "url": item.get("html_url", ""),
        "created_at": item.get("created_at", ""),
        "forks": item.get("forks_count", 0),
    }


def fetch_trending_repos(
    days_back: int = 7,
    min_stars: int = 30,
    max_results: int = 30,
    token: str | None = None,
) -> list[dict]:
    """Repos created in the last ``days_back`` days, ranked by stars."""
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>{min_stars}"
    url = (
        f"{_GITHUB_API}/search/repositories"
        f"?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={min(max_results, 100)}"
    )
    data = _get(url, token)
    if not data or "items" not in data:
        return []
    return [_normalise(item, days_back) for item in data["items"]]


def fetch_repos_by_topic(
    topic: str,
    days_back: int = 30,
    min_stars: int = 10,
    max_results: int = 15,
    token: str | None = None,
) -> list[dict]:
    """Repos tagged with ``topic`` that were pushed in the last ``days_back`` days."""
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"topic:{topic} pushed:>{since} stars:>{min_stars}"
    url = (
        f"{_GITHUB_API}/search/repositories"
        f"?q={urllib.parse.quote(query)}"
        f"&sort=stars&order=desc&per_page={min(max_results, 100)}"
    )
    data = _get(url, token)
    if not data or "items" not in data:
        return []
    return [_normalise(item, days_back) for item in data["items"]]
