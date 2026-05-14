"""repo-radar MCP server.

Exposes repo-radar's momentum detection over the Model Context Protocol,
so AI agents can query GitHub for repositories gaining traction fast.

This module is an OPTIONAL extra. Install it with:

    pip install "repo-radar[mcp]"

The core repo-radar CLI and library stay dependency-free — only this
server needs the ``mcp`` package.

Run the server (stdio transport, for MCP clients):

    repo-radar-mcp

Set ``GITHUB_TOKEN`` in the environment to raise the GitHub API rate
limit from 60 to 5,000 requests/hour.
"""
from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The repo-radar MCP server needs the 'mcp' package. Install it with:\n"
        '    pip install "repo-radar[mcp]"'
    ) from exc

from repo_radar.detector import find_momentum

mcp = FastMCP("repo-radar")


@mcp.tool()
def find_trending_repos(
    days_back: int = 7,
    min_stars: int = 30,
    min_velocity: float = 0.0,
    topics: list[str] | None = None,
    match: list[str] | None = None,
    limit: int = 15,
) -> list[dict]:
    """Find GitHub repos gaining traction fast, ranked by star velocity.

    Ranks newly-created repositories by stars-per-day rather than total
    stars, surfacing projects before they hit the front page. A repo with
    800 stars that is 6 days old is a stronger signal than one with 40,000
    stars that is 8 years old.

    Args:
        days_back: How far back to look for newly-created repos (default 7).
        min_stars: Minimum total stars for a repo to be considered (default 30).
        min_velocity: Minimum stars/day required to appear in results (default 0).
        topics: Optional GitHub topics to additionally search (e.g. ["llm", "rust"]).
        match: Optional keywords that boost a repo's score when matched.
        limit: Maximum number of results to return (default 15).

    Returns:
        A list of repos, each with: name, url, description, stars,
        star_velocity_per_day, language, topics, score (0-10) and
        matched_keywords. Sorted by score descending.
    """
    repos = find_momentum(
        days_back=days_back,
        min_stars=min_stars,
        min_velocity=min_velocity,
        topics=topics,
        match=match,
        limit=limit,
    )
    return [r.to_dict() for r in repos]


def main() -> None:
    """Entry point for the ``repo-radar-mcp`` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
