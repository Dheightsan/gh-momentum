"""repo-radar command-line interface."""
from __future__ import annotations

import argparse
import json
import sys

from repo_radar import __version__
from repo_radar.detector import find_momentum


def _print_human(repos) -> None:
    if not repos:
        print("No repos matched. Try lowering --min-stars or --min-velocity.")
        return
    for r in repos:
        match = (
            f"  [matches: {', '.join(r.matched_keywords)}]"
            if r.matched_keywords
            else ""
        )
        print(
            f"\n  {r.score:>4}/10  {r.name}  "
            f"({r.stars}*, {r.star_velocity_per_day}/day, {r.language}){match}"
        )
        if r.description:
            print(f"          {r.description}")
        print(f"          {r.url}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-radar",
        description=(
            "Surface GitHub repos gaining traction fast, "
            "before they hit the front page."
        ),
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="look back N days for newly created repos (default: 7)",
    )
    parser.add_argument(
        "--min-stars", type=int, default=30,
        help="minimum total stars to consider (default: 30)",
    )
    parser.add_argument(
        "--min-velocity", type=float, default=0.0,
        help="minimum stars/day to include in results (default: 0)",
    )
    parser.add_argument(
        "--topic", action="append", default=[], metavar="TOPIC",
        help="also search this GitHub topic (repeatable)",
    )
    parser.add_argument(
        "--match", default="", metavar="KW1,KW2",
        help="comma-separated keywords that boost matching repos",
    )
    parser.add_argument(
        "--limit", type=int, default=15,
        help="maximum number of results (default: 15)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="output JSON instead of human-readable text",
    )
    parser.add_argument(
        "--token", default=None,
        help=(
            "GitHub token (or set the GITHUB_TOKEN env var) to raise the "
            "rate limit from 60 to 5,000 requests/hour"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"repo-radar {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    match = [m for m in args.match.split(",") if m.strip()]
    repos = find_momentum(
        days_back=args.days,
        min_stars=args.min_stars,
        min_velocity=args.min_velocity,
        topics=args.topic,
        match=match,
        limit=args.limit,
        token=args.token,
    )

    if args.json:
        print(json.dumps([r.to_dict() for r in repos], indent=2))
    else:
        _print_human(repos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
