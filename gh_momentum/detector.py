"""Momentum scoring — ranks repos by how fast they are gaining traction.

The score (0-10) combines three signals:
  * **star velocity** (stars/day) — the primary signal
  * **absolute stars** — a small confidence bonus
  * **keyword match** — an optional boost when a repo matches topics you care about
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from gh_momentum.github_api import fetch_repos_by_topic, fetch_trending_repos


@dataclass
class MomentumRepo:
    """A repo that is gaining traction, with a computed momentum score."""

    name: str
    url: str
    description: str
    stars: int
    star_velocity_per_day: float
    language: str
    topics: list
    score: float
    matched_keywords: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _score(repo: dict, keywords: set[str]) -> tuple[float, list[str]]:
    """Compute a 0-10 momentum score for a single repo dict."""
    velocity = repo.get("star_velocity_per_day", 0) or 0
    stars = repo.get("stars", 0) or 0

    # Base score from velocity: linear-ish, saturates near 8.0
    base = min(8.0, velocity / 25)
    # Small confidence bonus from absolute star count
    base += min(1.0, stars / 5000)

    # Optional keyword-match boost
    haystack: set[str] = set()
    haystack.update(t.lower() for t in repo.get("topics", []) or [])
    haystack.update(
        repo.get("name", "").lower().replace("/", " ").replace("-", " ").split()
    )
    language = (repo.get("language") or "").lower()
    if language:
        haystack.add(language)
    haystack.update((repo.get("description") or "").lower().split())

    matched = sorted(keywords & haystack)
    if matched:
        base += min(1.5, 0.5 * len(matched))

    return round(min(10.0, base), 1), matched


def find_momentum(
    days_back: int = 7,
    min_stars: int = 30,
    min_velocity: float = 0.0,
    topics: list[str] | None = None,
    match: list[str] | None = None,
    limit: int = 15,
    token: str | None = None,
) -> list[MomentumRepo]:
    """Find repos gaining traction, ranked by momentum score.

    Args:
        days_back: how far back to look for newly-created repos.
        min_stars: minimum total stars for a repo to be considered.
        min_velocity: minimum stars/day required to appear in results.
        topics: optional GitHub topics to additionally search.
        match: optional keywords that boost a repo's score when matched.
        limit: maximum number of results to return.
        token: GitHub token (falls back to the ``GITHUB_TOKEN`` env var).

    Returns:
        A list of :class:`MomentumRepo`, sorted by score descending.
    """
    keywords = {k.lower().strip() for k in (match or []) if k.strip()}

    repos: dict[str, dict] = {}
    for repo in fetch_trending_repos(
        days_back=days_back, min_stars=min_stars, token=token
    ):
        if repo["name"]:
            repos[repo["name"]] = repo

    for topic in topics or []:
        for repo in fetch_repos_by_topic(topic, token=token):
            if repo["name"]:
                repos.setdefault(repo["name"], repo)

    results: list[MomentumRepo] = []
    for repo in repos.values():
        if (repo.get("star_velocity_per_day", 0) or 0) < min_velocity:
            continue
        score, matched = _score(repo, keywords)
        results.append(
            MomentumRepo(
                name=repo["name"],
                url=repo["url"],
                description=repo["description"],
                stars=repo["stars"],
                star_velocity_per_day=repo["star_velocity_per_day"],
                language=repo["language"],
                topics=repo.get("topics", []),
                score=score,
                matched_keywords=matched,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
