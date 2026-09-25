"""The suite does not depend on the machine it runs on.

Measured 2026-09-25: three tests reached the live Ollama model and one of them had
already flaked on what the narrator invented; campaign dice rolled from the clock in 61
test set-ups; and `PATHFINDER_GM_DATA` was `setdefault`, so an exported variable could
point the suite at a real data directory. conftest.py closes each; these pin it.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_no_test_reaches_a_live_model_by_accident():
    from gm import client

    with pytest.raises(client.ModelUnavailable, match="live_model"):
        client.chat([{"role": "user", "content": "hello"}], model="llama3.1:8b")
    assert client.warm("llama3.1:8b", "http://localhost:11434") is False


def test_unseeded_dice_roll_the_same_every_run():
    """The seed is the test's own id: two runs of this test roll the same numbers, and
    two unseeded Dice inside it do not share a stream."""
    import random
    import zlib

    from rules.dice import Dice

    a, b = Dice(), Dice()
    first = [a._rng.randrange(1000) for _ in range(5)]
    second = [b._rng.randrange(1000) for _ in range(5)]
    assert first != second, "two unseeded dice in one test were handed one stream"

    stream = random.Random(zlib.crc32(os.environ["PYTEST_CURRENT_TEST"]
                                      .rsplit(" ", 1)[0].encode("utf-8")))
    expect = random.Random(stream.randrange(2 ** 32))
    assert first == [expect.randrange(1000) for _ in range(5)]


def test_an_explicit_seed_is_left_alone():
    from rules.dice import Dice

    assert ([Dice(7)._rng.random() for _ in range(1)]
            == [__import__("random").Random(7).random()])


def test_the_data_directory_is_the_repos_own():
    root = Path(__file__).resolve().parent.parent
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    assert Path(os.environ["PATHFINDER_GM_DATA"]) == root / ".test-data" / worker
