"""Tests for repo-radar.

The scoring tests run fully offline. The single network test is opt-in:
set ``REPO_RADAR_LIVE_TEST=1`` to enable it.
"""
import os

import pytest

from repo_radar import MomentumRepo, __version__, find_momentum
from repo_radar.cli import build_parser
from repo_radar.detector import _score


def test_imports_and_version():
    assert __version__
    assert callable(find_momentum)


def test_score_velocity_drives_ranking():
    fast = {
        "star_velocity_per_day": 150, "stars": 2000, "topics": [],
        "name": "a/fast", "language": "Python", "description": "",
    }
    slow = {
        "star_velocity_per_day": 5, "stars": 100, "topics": [],
        "name": "b/slow", "language": "Python", "description": "",
    }
    fast_score, _ = _score(fast, set())
    slow_score, _ = _score(slow, set())
    assert fast_score > slow_score
    assert 0 <= slow_score <= 10
    assert 0 <= fast_score <= 10


def test_score_keyword_match_boosts():
    repo = {
        "star_velocity_per_day": 20, "stars": 500, "topics": ["llm", "agent"],
        "name": "x/cool-agent", "language": "Python", "description": "an llm tool",
    }
    no_match, matched_empty = _score(repo, set())
    with_match, matched = _score(repo, {"llm"})
    assert with_match > no_match
    assert "llm" in matched
    assert matched_empty == []


def test_score_capped_at_10():
    insane = {
        "star_velocity_per_day": 99999, "stars": 999999, "topics": ["llm"],
        "name": "z/llm", "language": "llm", "description": "llm llm llm",
    }
    score, _ = _score(insane, {"llm"})
    assert score <= 10.0


def test_momentum_repo_to_dict():
    r = MomentumRepo(
        name="a/b", url="u", description="d", stars=1,
        star_velocity_per_day=1.0, language="Python", topics=[], score=5.0,
    )
    d = r.to_dict()
    assert d["name"] == "a/b"
    assert d["score"] == 5.0
    assert d["matched_keywords"] == []


def test_cli_parser_defaults():
    args = build_parser().parse_args([])
    assert args.days == 7
    assert args.min_stars == 30
    assert args.json is False


def test_mcp_server_imports():
    pytest.importorskip("mcp")
    from repo_radar import mcp_server

    assert mcp_server.mcp is not None
    assert mcp_server.mcp.name == "repo-radar"
    assert callable(mcp_server.main)


@pytest.mark.skipif(
    os.getenv("REPO_RADAR_LIVE_TEST") != "1",
    reason="network test — set REPO_RADAR_LIVE_TEST=1 to enable",
)
def test_live_fetch_smoke():
    repos = find_momentum(days_back=14, min_stars=100, limit=5)
    assert isinstance(repos, list)
    for r in repos:
        assert isinstance(r, MomentumRepo)
        assert 0 <= r.score <= 10
