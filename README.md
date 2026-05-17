# gh-momentum

[![PyPI](https://img.shields.io/pypi/v/gh-momentum.svg)](https://pypi.org/project/gh-momentum/)
[![Downloads](https://img.shields.io/pypi/dm/gh-momentum.svg)](https://pypi.org/project/gh-momentum/)
[![CI](https://github.com/Dheightsan/gh-momentum/actions/workflows/ci.yml/badge.svg)](https://github.com/Dheightsan/gh-momentum/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)

**Surface GitHub repos gaining traction fast — before they hit the front page.**

`gh-momentum` queries the GitHub Search API for newly-created repositories and
ranks them by *momentum* (stars per day), not by total stars. A repo with 800
stars that's 6 days old is a stronger signal than one with 40,000 stars that's
8 years old. This tool finds the former.

Zero dependencies. Pure Python standard library. One file of logic, one CLI.

```
$ gh-momentum --days 7 --min-velocity 50

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
`gh-momentum` ranks by velocity so you see things while they're still small.

## How it works

```mermaid
flowchart LR
    GH[GitHub Search API]
    Fetcher["github_api.py<br/>fetch + normalize"]
    Scorer["detector.py<br/>score 0-10"]
    CLI["gh-momentum<br/>CLI"]
    Lib["find_momentum<br/>library"]
    MCP["gh-momentum-mcp<br/>MCP server"]
    Terminal[Your terminal]
    Code[Your Python code]
    Agent[AI agent / Claude Desktop / Cursor]

    GH --> Fetcher
    Fetcher --> Scorer
    Scorer --> CLI --> Terminal
    Scorer --> Lib --> Code
    Scorer --> MCP --> Agent
```

One fetcher, one scoring function, three surfaces (CLI / library / MCP). The
core has zero dependencies; only the optional MCP server pulls in the `mcp`
package.

## Install

```bash
pip install gh-momentum
```

Or from source:

```bash
git clone https://github.com/Dheightsan/gh-momentum
cd gh-momentum
pip install -e .
```

## Usage

```bash
# Repos created in the last 7 days, gaining at least 50 stars/day
gh-momentum --days 7 --min-velocity 50

# Also pull in repos tagged with specific GitHub topics
gh-momentum --topic llm --topic rust

# Boost repos that match keywords you care about
gh-momentum --match "python,fastapi,cli"

# Machine-readable output
gh-momentum --json | jq '.[] | .name'
```

### Rate limits

The GitHub Search API allows **60 requests/hour unauthenticated**. Set a token
to raise that to **5,000/hour**:

```bash
export GITHUB_TOKEN=ghp_your_token_here
gh-momentum
# or: gh-momentum --token ghp_your_token_here
```

A token with **no scopes at all** is enough — `gh-momentum` only reads public data.

## Use as a library

```python
from gh_momentum import find_momentum

for repo in find_momentum(days_back=7, min_velocity=50, match=["llm"]):
    print(repo.score, repo.name, repo.star_velocity_per_day)
```

`find_momentum()` returns a list of `MomentumRepo` dataclasses, sorted by score.

## Use it as an MCP server with your AI assistant

gh-momentum ships an optional [Model Context Protocol](https://modelcontextprotocol.io)
server. Once installed, **any MCP-compatible AI client can call it as a tool**
— ask things like *"what Python repos are trending this week with high
velocity?"* and your assistant fetches live data from GitHub.

Install with the `mcp` extra:

```bash
pip install "gh-momentum[mcp]"
```

Then add it to your client's MCP config:

### Claude Desktop

Edit `claude_desktop_config.json`
([location](https://modelcontextprotocol.io/quickstart/user)) and add:

```json
{
  "mcpServers": {
    "gh-momentum": {
      "command": "gh-momentum-mcp",
      "env": {
        "GITHUB_TOKEN": "ghp_optional_for_higher_rate_limit"
      }
    }
  }
}
```

Restart Claude Desktop. The `find_trending_repos` tool appears in the tool list.

### Cursor / Cline / VS Code (MCP-enabled)

Add to your MCP config (e.g. `~/.cursor/mcp.json` or the equivalent for your
client):

```json
{
  "mcpServers": {
    "gh-momentum": {
      "command": "gh-momentum-mcp"
    }
  }
}
```

### Generic stdio clients

Any client that speaks MCP over stdio can spawn `gh-momentum-mcp` as a
subprocess. The `GITHUB_TOKEN` environment variable is optional and raises the
GitHub API rate limit from 60 to 5,000 requests/hour.

### The exposed tool

The server exposes one tool, **`find_trending_repos`**, with the same
parameters as the CLI (`days_back`, `min_stars`, `min_velocity`, `topics`,
`match`, `limit`). Returns a JSON list of repos with name, URL, description,
stars, star velocity, language, topics, score (0-10) and matched keywords.

Example questions that route through this tool well:

- *"Find Rust repos created in the last 14 days with at least 100 stars/day."*
- *"Show me LLM-related projects gaining traction this week — boost the ones
  matching agents, RAG, or vector search."*
- *"Compare star velocity on these two repos."*

## How the score works

The 0-10 score combines three signals:

| Signal              | Weight                                            |
|---------------------|---------------------------------------------------|
| **Star velocity**   | Primary. `stars/day`, saturates near 8.0          |
| **Absolute stars**  | Small confidence bonus (up to +1.0)               |
| **Keyword match**   | Optional boost when `--match` keywords hit (up to +1.5) |

The scoring lives in one function — `_score()` in
[`gh_momentum/detector.py`](gh_momentum/detector.py) — so it's easy to read,
fork, and tune to your own taste.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

Tests run fully offline. The one network test is opt-in:

```bash
GH_MOMENTUM_LIVE_TEST=1 pytest -q
```

## Contributing

Issues and PRs welcome. This is maintained on a best-effort basis — if you need
a feature, a PR is the fastest path. Keep the zero-dependency rule intact.

## License

MIT — see [LICENSE](LICENSE).
