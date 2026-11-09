"""Star velocity uses the repo's real age. Fully offline: fake API data only."""
import io
import json
import logging
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from gh_momentum import cli, detector, github_api
from gh_momentum.github_api import _normalise, _parse_created_at

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)


def _iso(days_ago: float, z: bool = True) -> str:
    created = NOW - timedelta(days=days_ago)
    text = created.strftime("%Y-%m-%dT%H:%M:%S")
    return text + ("Z" if z else "+00:00")


def _item(name: str, stars: int, created_at, **extra) -> dict:
    item = {
        "full_name": name,
        "stargazers_count": stars,
        "created_at": created_at,
        "html_url": f"https://github.com/{name}",
        "description": "",
        "language": "Python",
        "topics": [],
        "forks_count": 0,
    }
    item.update(extra)
    return item


def _patch_trending(monkeypatch, items, days_back=30):
    normalised = [_normalise(i, days_back, now=NOW) for i in items]
    monkeypatch.setattr(detector, "fetch_trending_repos", lambda **kw: normalised)


def test_same_stars_different_age_gives_different_velocity():
    old = _normalise(_item("a/old", 1000, _iso(10)), 30, now=NOW)
    new = _normalise(_item("b/new", 1000, _iso(2)), 30, now=NOW)
    assert old["star_velocity_per_day"] == 100.0
    assert new["star_velocity_per_day"] == 500.0


def test_velocity_is_not_divided_by_days_back():
    repo = _normalise(_item("a/x", 600, _iso(3)), 30, now=NOW)
    assert repo["star_velocity_per_day"] == 200.0  # not 600 / 30


def test_fractional_days_and_one_day_floor():
    half_day = _normalise(_item("a/h", 90, _iso(1.5)), 7, now=NOW)
    assert half_day["star_velocity_per_day"] == 60.0
    hours_old = _normalise(_item("a/n", 90, _iso(0.1)), 7, now=NOW)
    assert hours_old["star_velocity_per_day"] == 90.0  # floor of 1 day
    future_stamp = (NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future = _normalise(_item("a/f", 50, future_stamp), 7, now=NOW)
    assert future["star_velocity_per_day"] == 50.0  # clock skew, still floored


def test_created_at_with_z_suffix():
    parsed = _parse_created_at("2026-11-01T12:00:00Z")
    assert parsed == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    repo = _normalise(_item("a/z", 700, "2026-11-01T12:00:00Z"), 30, now=NOW)
    assert repo["star_velocity_per_day"] == 100.0  # 7 days exactly


def test_created_at_with_offset_and_naive_are_utc():
    offset = _parse_created_at("2026-11-01T09:00:00-03:00")
    assert offset == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    naive = _parse_created_at("2026-11-01T12:00:00")
    assert naive == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "bad", ["not-a-date", "", None, 12345, "2026-13-45T00:00:00Z"]
)
def test_invalid_created_at_falls_back_to_days_back(bad, caplog):
    with caplog.at_level(logging.WARNING, logger="gh_momentum.github_api"):
        repo = _normalise(_item("a/bad", 300, bad), 6, now=NOW)
    assert repo["star_velocity_per_day"] == 50.0  # 300 / days_back
    assert "a/bad" in caplog.text
    assert "days_back=6" in caplog.text


def test_missing_created_at_key_falls_back_to_days_back():
    item = _item("a/none", 300, None)
    del item["created_at"]
    assert _normalise(item, 6, now=NOW)["star_velocity_per_day"] == 50.0


def test_days_back_zero_does_not_divide_by_zero():
    repo = _normalise(_item("a/z", 40, "bad"), 0, now=NOW)
    assert repo["star_velocity_per_day"] == 40.0


def _fake_get(items):
    def fake(url, token=None):
        return {"items": items}

    return fake


def test_fetch_trending_repos_uses_real_age(monkeypatch):
    items = [
        _item("a/old", 1000, _iso(10)),
        _item("b/new", 1000, _iso(2)),
    ]
    monkeypatch.setattr(github_api, "_get", _fake_get(items))
    repos = github_api.fetch_trending_repos(days_back=30, now=NOW)
    assert [r["star_velocity_per_day"] for r in repos] == [100.0, 500.0]


def test_since_date_is_utc(monkeypatch):
    seen = {}

    def fake(url, token=None):
        seen["url"] = url
        return {"items": []}

    monkeypatch.setattr(github_api, "_get", fake)
    github_api.fetch_trending_repos(days_back=7, now=NOW)
    assert "created%3A%3E2026-11-01" in seen["url"]


def test_ranking_follows_velocity_not_total_stars(monkeypatch):
    # The API returns these sorted by stars. The younger repo has fewer
    # stars but a much higher velocity, so it must come first.
    _patch_trending(monkeypatch, [
        _item("big/old", 3000, _iso(30)),    # 100/day
        _item("small/new", 1200, _iso(3)),   # 400/day
    ])
    result = detector.find_momentum(days_back=30)
    assert [r.name for r in result] == ["small/new", "big/old"]
    assert result[0].star_velocity_per_day == 400.0
    assert result[0].score > result[1].score


def test_same_stars_newer_repo_goes_first(monkeypatch):
    _patch_trending(monkeypatch, [
        _item("a/older", 1000, _iso(10)),
        _item("b/newer", 1000, _iso(2)),
    ])
    result = detector.find_momentum(days_back=30)
    assert [r.name for r in result] == ["b/newer", "a/older"]
    assert result[0].star_velocity_per_day != result[1].star_velocity_per_day


def test_velocity_breaks_ties_when_score_is_capped(monkeypatch):
    # Both saturate the velocity part of the score and share the same stars
    # bonus, so only velocity can tell them apart.
    _patch_trending(monkeypatch, [
        _item("a/fast", 6000, _iso(5)),    # 1200/day
        _item("b/faster", 6000, _iso(2)),  # 3000/day
    ])
    result = detector.find_momentum(days_back=30)
    assert result[0].score == result[1].score
    assert [r.name for r in result] == ["b/faster", "a/fast"]


def test_min_velocity_uses_real_age(monkeypatch):
    _patch_trending(monkeypatch, [
        _item("a/old", 1000, _iso(30)),  # 33.3/day
        _item("b/new", 1000, _iso(4)),   # 250/day
    ])
    result = detector.find_momentum(days_back=30, min_velocity=100)
    assert [r.name for r in result] == ["b/new"]


def test_cli_prints_the_new_velocity(monkeypatch, capsys):
    _patch_trending(monkeypatch, [
        _item("big/old", 3000, _iso(30)),
        _item("small/new", 1200, _iso(3)),
    ])
    assert cli.main(["--days", "30"]) == 0
    out = capsys.readouterr().out
    assert "400.0/day" in out and "100.0/day" in out
    assert out.index("small/new") < out.index("big/old")

    assert cli.main(["--days", "30", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in data] == ["small/new", "big/old"]
    assert data[0]["star_velocity_per_day"] == 400.0


def test_mcp_tool_returns_the_new_velocity(monkeypatch):
    pytest.importorskip("mcp")
    from gh_momentum import mcp_server

    _patch_trending(monkeypatch, [
        _item("big/old", 3000, _iso(30)),
        _item("small/new", 1200, _iso(3)),
    ])
    result = mcp_server.find_trending_repos(days_back=30)
    assert [r["name"] for r in result] == ["small/new", "big/old"]
    assert result[0]["star_velocity_per_day"] == 400.0


# Visible errors: nothing is swallowed silently.


def test_non_object_item_is_skipped_and_logged(monkeypatch, caplog):
    items = ["oops", _item("a/ok", 100, _iso(2))]
    monkeypatch.setattr(github_api, "_get", _fake_get(items))
    with caplog.at_level(logging.INFO, logger="gh_momentum.github_api"):
        repos = github_api.fetch_trending_repos(now=NOW)
    assert [r["name"] for r in repos] == ["a/ok"]
    assert "item 0 is str" in caplog.text
    assert "1 skipped" in caplog.text


def test_response_without_items_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(
        github_api, "_get", lambda url, token=None: {"message": "x"}
    )
    with caplog.at_level(logging.WARNING, logger="gh_momentum.github_api"):
        assert github_api.fetch_trending_repos(now=NOW) == []
    assert "no 'items' list" in caplog.text


def test_get_logs_http_errors(monkeypatch, caplog):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 403, "rate", {}, io.BytesIO(b"")
        )

    monkeypatch.setattr(github_api.urllib.request, "urlopen", boom)
    with caplog.at_level(logging.WARNING, logger="gh_momentum.github_api"):
        assert github_api._get("https://api.github.com/x") is None
    assert "rate limit" in caplog.text
    assert "10 requests/min" in caplog.text


def test_get_logs_network_and_json_errors(monkeypatch, caplog):
    def down(req, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(github_api.urllib.request, "urlopen", down)
    with caplog.at_level(logging.WARNING, logger="gh_momentum.github_api"):
        assert github_api._get("https://api.github.com/x") is None
    assert "no route" in caplog.text

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"<html>"

    caplog.clear()
    monkeypatch.setattr(
        github_api.urllib.request, "urlopen", lambda req, timeout=None: Resp()
    )
    with caplog.at_level(logging.WARNING, logger="gh_momentum.github_api"):
        assert github_api._get("https://api.github.com/x") is None
    assert "invalid JSON" in caplog.text


def test_get_does_not_swallow_unexpected_errors(monkeypatch):
    def bug(req, timeout=None):
        raise RuntimeError("bug")

    monkeypatch.setattr(github_api.urllib.request, "urlopen", bug)
    with pytest.raises(RuntimeError):
        github_api._get("https://api.github.com/x")


def test_run_summary_is_logged(monkeypatch, caplog):
    _patch_trending(monkeypatch, [
        _item("a/old", 1000, _iso(30)),
        _item("b/new", 1000, _iso(4)),
    ])
    with caplog.at_level(logging.INFO, logger="gh_momentum.detector"):
        detector.find_momentum(days_back=30, min_velocity=100)
    assert "2 unique repos, 1 below min_velocity=100" in caplog.text
    assert "1 returned" in caplog.text


def test_z_suffix_is_rewritten_before_fromisoformat(monkeypatch):
    # Python 3.9 and 3.10 reject a trailing "Z" in fromisoformat. Emulate
    # that here so the test also guards the 3.9 CI job on newer Pythons.
    class Strict(datetime):
        @classmethod
        def fromisoformat(cls, text):
            if text.endswith("Z"):
                raise ValueError("Invalid isoformat string: " + repr(text))
            return datetime.fromisoformat(text)

    monkeypatch.setattr(github_api, "datetime", Strict)
    parsed = _parse_created_at("2026-11-01T12:00:00Z")
    assert parsed == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
