# repo-radar

[![CI](https://github.com/<your-github-username>/repo-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-github-username>/repo-radar/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

**Surface GitHub repos gaining traction fast — before they hit the front page.**

`repo-radar` queries the GitHub Search API for newly-created repositories and
ranks them by *momentum* (stars per day), not by total stars. A repo with 800
stars that's 6 days old is a stronger signal than one with 40,000 stars that's
8 years old. This tool finds the former.

Zero dependencies. Pure Python standard library. One file of logic, one CLI.

```
$ repo-radar --days 7 --min-velocity 50

   9.1/10  acme/turbo-agent  (1240*, 177.1/day, Python)
          A minimal autonomous agent runtime that fits in 500 lines.
          https://github.com/acme/turbo-agent

   7.4/10  data-co/ducklake  (612*, 87.4/day, Rust)
          Embedded analytics database with a Postgres wire protocol.
          https://github.com/data-co/ducklake
```

## Why

Star count is a lagging indicator. By the time a repo has 20k stars, the
opportunity to be early — to contribute, to build on top of it, to write the
first tutorial — is mostly gone. **Star velocity is a leading indicator.**
`repo-radar` ranks by velocity so you see things while they're still small.

## Install

```bash
pip install repo-radar
```

Or from source:

```bash
git clone https://github.com/<your-github-username>/repo-radar
cd repo-radar
pip install -e .
```

## Usage

```bash
# Repos created in the last 7 days, gaining at least 50 stars/day
repo-radar --days 7 --min-velocity 50

# Also pull in repos tagged with specific GitHub topics
repo-radar --topic llm --topic rust

# Boost repos that match keywords you care about
repo-radar --match "python,fastapi,cli"

# Machine-readable output
repo-radar --json | jq '.[] | .name'
```

### Rate limits

The GitHub Search API allows **60 requests/hour unauthenticated**. Set a token
to raise that to **5,000/hour**:

```bash
export GITHUB_TOKEN=ghp_your_token_here
repo-radar
# or: repo-radar --token ghp_your_token_here
```

A token with **no scopes at all** is enough — `repo-radar` only reads public data.

## Use as a library

```python
from repo_radar import find_momentum

for repo in find_momentum(days_back=7, min_velocity=50, match=["llm"]):
    print(repo.score, repo.name, repo.star_velocity_per_day)
```

`find_momentum()` returns a list of `MomentumRepo` dataclasses, sorted by score.

## How the score works

The 0-10 score combines three signals:

| Signal              | Weight                                            |
|---------------------|---------------------------------------------------|
| **Star velocity**   | Primary. `stars/day`, saturates near 8.0          |
| **Absolute stars**  | Small confidence bonus (up to +1.0)               |
| **Keyword match**   | Optional boost when `--match` keywords hit (up to +1.5) |

The scoring lives in one function — `_score()` in
[`repo_radar/detector.py`](repo_radar/detector.py) — so it's easy to read,
fork, and tune to your own taste.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

Tests run fully offline. The one network test is opt-in:

```bash
REPO_RADAR_LIVE_TEST=1 pytest -q
```

## Contributing

Issues and PRs welcome. This is maintained on a best-effort basis — if you need
a feature, a PR is the fastest path. Keep the zero-dependency rule intact.

## License

MIT — see [LICENSE](LICENSE).
