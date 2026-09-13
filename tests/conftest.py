"""Test setup.

Django is configured here rather than through pytest-django, because the rules engine and
the world loader do not touch the ORM and the app has no models — one fewer dependency for
PyInstaller to be told about, which is a real cost in the frozen build.

Tests run from the repository root so that the fixture paths in them are the same paths a
person would type.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Campaign saves must never land in the real user data directory during a test run.
os.environ.setdefault("PATHFINDER_GM_DATA", str(ROOT / ".test-data"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from django.test.signals import setting_changed  # noqa: E402

# Every module that caches shipped content merged with a homebrew overlay read from
# under CAMPAIGN_DIR. Each holds its catalogue in a module-level `_NAME = None` and
# fills it on first use, so a cache filled while one test pointed CAMPAIGN_DIR at its
# own tmp_path is still holding that test's homebrew when the next one asks.
#
# Hand-listed and mechanically checked: `test_every_content_cache_is_isolated` walks
# rules/ for the declaration pattern and fails if this tuple has drifted, which is the
# same arrangement `test_packaging.py` uses for the spec's content directories.
_CACHED = (
    "rules.alchemist", "rules.bestiary", "rules.blacksmith", "rules.classes",
    "rules.enchanter", "rules.feats", "rules.hazards", "rules.ingredients",
    "rules.leatherworker",
    "rules.magicitem", "rules.market", "rules.spells", "rules.weapons",
    "rules.worldclass",
)


def clear_content_caches() -> None:
    """Drop every content cache, so the next read rebuilds against the current dir.

    A cache is found by its own declaration — `_ALL: dict[str, Spell] | None = None` —
    rather than by matching upper-case names, because `rules/spells.py` alone holds
    eight module-level `_UPPER` dicts that are constants (`_RANGE_BANDS`, `_SAVES`,
    `_ENERGY_WORDS`) and nulling those breaks the module outright. The optional
    annotation is exactly what separates "filled on first use" from "written down once".

    Caches with a companion (`bestiary._INDEX` beside `_IMPORTED`, `feats._META` beside
    `_ALL`) need no entry: their loader rebuilds both under one `global`, keyed on the
    annotated one.
    """
    import importlib
    import re
    import sys

    for name in _CACHED:
        mod = sys.modules.get(name) or importlib.import_module(name)
        for attr, annotation in getattr(mod, "__annotations__", {}).items():
            if re.fullmatch(r"_[A-Z][A-Z_]*", attr) and "None" in str(annotation):
                setattr(mod, attr, None)


@pytest.fixture(autouse=True)
def _no_test_waits_on_the_written_opening(monkeypatch):
    """Starting a campaign asks the prose model to write the opening. Measured the
    day it landed: 166 tests start one, and with Ollama up the two-minute suite ran
    past ten minutes at ten seconds a call. The template is what every test that
    is not about the written opening gets; `tests/test_opening_prose.py` turns the
    model back on and stubs the client."""
    from play import opening_prose

    monkeypatch.setattr(opening_prose, "ENABLED", False)
    # And the quest schemes, for the same reason: "The lost thing" opens at any
    # market, which a test about hit points did not ask for. tests/test_schemes.py
    # turns it back on.
    from rules import schemes as schemes_mod

    monkeypatch.setattr(schemes_mod, "ENABLED", False)


@pytest.fixture(autouse=True)
def _the_model_gate_is_open_unless_a_test_shuts_it(monkeypatch):
    """`/api/start` and `/api/resume` ask Ollama whether it can answer before they let
    anybody through. Left live, that makes the suite's result depend on whether Ollama
    happens to be running on the machine — 166 tests start a campaign, and every one of
    them would pass at a desk with the daemon up and fail in a fresh checkout, which is
    the worst shape a test failure can have.

    The probe is stubbed rather than the gate, so the *gate itself* still runs on every
    one of those tests: a mistake in `_model_gate` that refuses a healthy machine is
    still caught here. `tests/test_preflight.py` and `test_home.py` shut it deliberately
    to check the refusals."""
    from gm import client as gm_client
    from play import preflight

    def answers_with_whatever_is_configured(*_a, **_kw):
        # Computed per call, not once at setup. A test that overrides CAMPAIGN_DIR and
        # writes its own model settings changes what `needs()` asks for, and a list
        # captured at fixture time would then read as "the model is missing" and refuse
        # a door the test was not testing.
        return gm_client.Probe(True, installed=tuple(n.model for n in preflight.needs()))

    monkeypatch.setattr(gm_client, "probe", answers_with_whatever_is_configured)


@pytest.fixture(autouse=True)
def _house_rules_start_at_the_defaults():
    """Every test begins with the shipped rules, whatever the last one chose.

    `.test-data/` is a real directory that survives between runs, and house rules are
    a file in it, so a test that sets one leaves it set for every run afterwards.
    Measured 2026-09-08: an earlier session had left `point_buy: 0` — Unlimited — in
    that file, and `test_creation.py::test_the_point_budget_is_a_wall` then failed on
    a clean checkout of the code, because there is no wall when the budget is
    unlimited. The failure had nothing to do with the change being tested, and
    `test_houserules.py` asserting the default budget of 20 was one run away from the
    same fate.

    Same class as `_campaign_dir_never_leaks` below: a real regression cannot be told
    from a leak, and a suite whose result depends on how the player last set their
    game is not a gate at all.
    """
    from rules import houserules

    def clear():
        try:
            houserules._path().unlink(missing_ok=True)
        except OSError:
            pass

    clear()
    yield
    clear()


@pytest.fixture(autouse=True)
def _campaign_dir_never_leaks():
    """No test may leave CAMPAIGN_DIR pointing somewhere the next one can see.

    Sixteen tests assign `settings.CAMPAIGN_DIR = str(tmp_path)` outright rather than
    through `override_settings`, and never put it back — so every test that ran after
    one of them resolved house rules and homebrew against a directory pytest had
    already deleted, and any content cache filled in the meantime kept that test's
    homebrew for the rest of the session. That is a whole class of order-dependent
    failure, and it makes the suite unusable as the gate the compliance work is judged
    by: a real regression cannot be told from a leak.

    Restoring is not enough on its own — a cache filled under the borrowed directory
    outlives the setting — so the caches are dropped whenever the directory moved.
    """
    before = settings.CAMPAIGN_DIR
    yield
    if settings.CAMPAIGN_DIR != before:
        settings.CAMPAIGN_DIR = before
        clear_content_caches()


def _cache_follows_the_directory(sender, setting, **kwargs):
    """`override_settings` is honest about CAMPAIGN_DIR moving; the caches were not.

    Django announces the change on the way in and on the way out, so this is the one
    place both directions are covered — including the tests that use the context
    manager correctly and still shared a stale catalogue with their neighbours.
    """
    if setting == "CAMPAIGN_DIR":
        clear_content_caches()


setting_changed.connect(_cache_follows_the_directory)
