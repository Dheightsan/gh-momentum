# Why I stopped sorting GitHub by stars

*A short walkthrough of `gh-momentum` — a tiny tool to find repos gaining traction before they hit the front page.*

---

## The problem with total stars

Sort any GitHub topic page by stars and the top results have been there for
years. `awesome-python` has 240k stars. It's been on the list of every "best
of" article since 2017. It's not news. It's archaeology.

By the time something has 20,000 stars, the interesting moments — the first
issue, the first PR, the first time someone built on top of it — are gone.

**Star count is a lagging indicator.** It tells you what *was* popular, not
what *is becoming* popular.

The signal I actually want is different: which small repos are growing
*right now*? A project with 800 stars that's six days old is a stronger
signal than one with 40,000 stars that's eight years old. The first is a
trend forming. The second is a trend that finished.

I wanted a tool that ranks by that. I didn't find one. So I wrote one in an
afternoon and put it on GitHub: [gh-momentum](https://github.com/Dheightsan/gh-momentum).

---

## What it does, in one example

```bash
$ pip install gh-momentum
$ gh-momentum --days 7 --min-velocity 50

   9.0/10  antirez/ds4  (8728*, 623.4/day, C)
          DeepSeek 4 Flash local inference engine for Metal and CUDA
          https://github.com/antirez/ds4

   8.7/10  darrylmorley/whatcable  (3484*, 248.9/day, Swift)
          macOS menu bar app that tells you, in plain English, what each
          USB-C cable plugged into your Mac can actually do
          https://github.com/darrylmorley/whatcable
```

Both of those repos are less than two weeks old. Both are pulling hundreds
of stars per day. Neither shows up at the top of a default GitHub search,
because they don't have the *total* star count yet.

That's the point.

---

## How the score works

The score is a single 0-10 number combining three things:

1. **Star velocity** — `stars / days_alive`. This is the dominant signal,
   capped near 8.0 to avoid one viral day saturating the rest of the score.
2. **Total stars** — a small confidence bonus (up to +1.0). A repo with
   2,000 stars at 100/day is more believable than one with 50 stars at
   100/day on its first day.
3. **Keyword match** — optional. If you pass `--match llm,rust`, repos
   whose topics, language, name or description hit those keywords get a
   small bump.

The whole scoring function is one function in
[`detector.py`](https://github.com/Dheightsan/gh-momentum/blob/main/gh_momentum/detector.py)
— easy to fork and tune.

---

## A few queries that work well

**What's blowing up in AI/LLM land this week?**

```bash
gh-momentum --days 7 --topic llm --topic ai --match "agent,rag,llm"
```

**Rust projects gaining traction this month, ignore noise:**

```bash
gh-momentum --days 30 --min-stars 200 --min-velocity 30 --topic rust
```

**Quick read on what's hot right now, machine-readable:**

```bash
gh-momentum --days 3 --min-velocity 100 --json
```

---

## Using it as an MCP tool

If you use Claude Desktop, Cursor, Cline, or any MCP-capable AI client,
`gh-momentum` ships an optional MCP server. Install with
`pip install "gh-momentum[mcp]"` and add this to your client config:

```json
{
  "mcpServers": {
    "gh-momentum": {
      "command": "gh-momentum-mcp"
    }
  }
}
```

Then ask your assistant things like *"what Rust repos are trending this
week with at least 100 stars/day?"* and it'll fetch live data from GitHub
and tell you.

This is the use case I personally cared about most: I don't want to remember
to run a CLI. I want my AI assistant to know how to look this up when the
topic comes up in conversation.

---

## Notes for users in low-rate-limit territory

The GitHub Search API allows 60 requests/hour unauthenticated. If you query
more than that, set a token:

```bash
export GITHUB_TOKEN=ghp_your_token
gh-momentum
```

A token with **no scopes at all** is enough — `gh-momentum` only reads
public data. That gets you to 5,000 requests/hour.

---

## What it isn't

This isn't a replacement for GitHub's trending page. The trending page is
opinionated (curated by GitHub, hard to query programmatically, no momentum
score). `gh-momentum` is the opposite: small, scriptable, sortable, and the
score logic is in one function you can rewrite.

It also isn't a recommender. It doesn't know what *you* care about. The
`--match` flag is a crude bias, not personalization.

---

## Where it lives

- GitHub: <https://github.com/Dheightsan/gh-momentum>
- PyPI: `pip install gh-momentum`
- MIT licensed, zero runtime dependencies, under 500 lines.

If you find a useful query, post it in the
[issues](https://github.com/Dheightsan/gh-momentum/issues) — I'd like to
collect a list of good ones in the README.
