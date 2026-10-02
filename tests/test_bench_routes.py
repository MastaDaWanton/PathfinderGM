"""The herbalism bench's routes reach the bench, not the homebrew benches.

Measured by Lane D on 2026-10-02: `GET /api/bench/state` answered 404 "no bench 'state'",
because the homebrew editor's `api/bench/<bench_id>` was declared first and Django takes
the first pattern that matches. Every bench call the new page makes was unreachable.
"""
from django.urls import resolve

from play import bench_views, home_views


def test_every_herbalism_bench_route_resolves_to_the_bench():
    for name in ("state", "check", "roll", "finish", "perks", "recipe"):
        assert resolve(f"/api/bench/{name}").func is getattr(bench_views, f"bench_{name}")


def test_a_homebrew_bench_is_still_the_homebrew_editor():
    assert resolve("/api/bench/weapons").func is home_views.bench
