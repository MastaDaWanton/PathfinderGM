"""Quitting gives a finishing turn its moment, and starts no new one.

Measured 2026-09-25: desktop.py said `server.shutdown()` "lets the request in flight
finish". The request threads are daemons; `main` returned and the turn died with the
process. The shell allows 3 seconds before taskkill, so a turn still waiting on the model
cannot be saved — and does not need to be, since every save lands by rename — but a
turn that has its answer and is writing it now gets two seconds, and nothing queued
behind it starts.
"""
from __future__ import annotations

import threading
import time

import desktop
from play import concurrency


def _release_if_held():
    try:
        concurrency._GAME.release()
    except RuntimeError:
        pass


def test_with_nothing_in_flight_the_lock_is_taken_at_once():
    try:
        started = time.monotonic()
        assert desktop._let_the_last_turn_land(timeout=2.0)
        assert time.monotonic() - started < 0.5
    finally:
        _release_if_held()


def test_a_turn_that_finishes_in_time_lands_first():
    order = []

    def turn():
        with concurrency.held(1.0):
            time.sleep(0.3)
            order.append("turn saved")

    t = threading.Thread(target=turn)
    t.start()
    time.sleep(0.05)
    try:
        assert desktop._let_the_last_turn_land(timeout=2.0)
        order.append("shut down")
    finally:
        _release_if_held()
        t.join()
    assert order == ["turn saved", "shut down"]


def test_a_turn_still_thinking_does_not_hold_the_exit_past_the_shells_window():
    release = threading.Event()

    def thinking():
        with concurrency.held(1.0):
            release.wait(5)

    t = threading.Thread(target=thinking)
    t.start()
    time.sleep(0.05)
    started = time.monotonic()
    try:
        assert not desktop._let_the_last_turn_land(timeout=0.3)
        assert time.monotonic() - started < 1.0
        assert desktop.LAST_TURN_WAIT < 3.0, "inside the shell's taskkill window"
    finally:
        release.set()
        t.join()
