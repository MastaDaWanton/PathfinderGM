"""The first run: what is missing, said in words, with a button under it.

The defect this exists to prevent, measured 2026-09-11 against the shipped defaults:
`gm.client.available()` returned `[]` for four different situations — Ollama not
installed, installed but not running, running with nothing pulled, and a mistyped host
— and every caller in the app treated all four as "no models". The only surface that
read it was the settings page's datalist, which offered the same empty dropdown to all
four. A player who double-clicked the exe on a machine with no Ollama got a home page
that looked perfectly healthy, picked a character, pressed Begin, and landed on a table
that answered with a model error over a scene that never arrived.

The second measurement behind this file: `settings.MODELS` points four roles at **two**
distinct models, 7.4 GB and 2.5 GB. Three of the four share one. A setup page that
listed them per role would tell a player they were about to download 22 GB.
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

from gm import client as gm_client
from play import preflight

# The genuine article, taken at import time — which is before any fixture runs.
# `conftest._the_model_gate_is_open_unless_a_test_shuts_it` replaces `gm_client.probe`
# for every test in the suite so the result never depends on whether Ollama happens to
# be running; the two tests below are about that function itself and need the real one.
_REAL_PROBE = gm_client.probe


# --- Telling the four situations apart ------------------------------------------------

def _probe(**kw):
    return mock.patch.object(gm_client, "probe",
                             return_value=gm_client.Probe(**kw))


def test_a_refused_port_is_not_the_same_as_an_empty_shelf():
    """`available()` answered `[]` to both, and they are not the same problem.

    One is "download Ollama"; the other is "download a model". Offering the wrong one
    is the whole failure this module exists to stop.
    """
    with _probe(reachable=False, refused=True, why="nothing is listening"):
        refused = preflight.check()
    with _probe(reachable=True, installed=()):
        empty = preflight.check()

    assert refused.state in ("not-installed", "not-running")
    assert empty.state == "missing-models"
    assert not refused.ok and not empty.ok


def test_installed_but_not_running_is_told_apart_by_the_filesystem():
    """The socket cannot answer this: a refused connection is refused either way.

    The fixes differ by a 900 MB download, so the question is asked of the disk.
    """
    with _probe(reachable=False, refused=True, why="nothing is listening"):
        with mock.patch.object(preflight, "ollama_on_disk", return_value=True):
            assert preflight.check().state == "not-running"
        with mock.patch.object(preflight, "ollama_on_disk", return_value=False):
            assert preflight.check().state == "not-installed"


def test_a_host_that_cannot_be_found_is_not_reported_as_missing_software():
    """A typo in the host field is not a reason to tell somebody to install Ollama."""
    with _probe(reachable=False, refused=False, why="cannot reach http://typo:11434"):
        report = preflight.check()
    assert report.state == "unreachable"
    assert "typo" in report.why


def test_probe_reports_a_refusal_as_a_refusal(monkeypatch):
    """The distinction is carried from `urllib`'s own exception, not guessed.

    ConnectionRefusedError is WinError 10061 on Windows and ECONNREFUSED elsewhere;
    urllib wraps whichever in `URLError.reason`.
    """
    import urllib.error

    def refuse(*a, **kw):
        raise urllib.error.URLError(ConnectionRefusedError(61, "refused"))

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    found = _REAL_PROBE("http://localhost:11434")
    assert found.reachable is False
    assert found.refused is True

    def vanish(*a, **kw):
        raise urllib.error.URLError("no such host")

    monkeypatch.setattr("urllib.request.urlopen", vanish)
    assert _REAL_PROBE("http://nowhere:11434").refused is False


def test_probe_reads_the_model_list_and_survives_junk(monkeypatch):
    """`available()` did `m["name"]` over whatever came back. A reply that is not the
    shape expected — an error object, a null in the list — raised out of a function
    whose entire contract was to return a list or an empty one."""
    import io

    def answer(body):
        return lambda *a, **kw: io.BytesIO(body.encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen",
                        answer('{"models": [{"name": "a:latest"}, {"name": "b:1"}]}'))
    assert _REAL_PROBE().installed == ("a:latest", "b:1")

    for junk in ('{"models": null}', '{"models": [null, 3, {"no": "name"}]}',
                 '{}', '[]', 'null'):
        monkeypatch.setattr("urllib.request.urlopen", answer(junk))
        got = _REAL_PROBE()
        assert got.reachable and got.installed == (), junk

    monkeypatch.setattr("urllib.request.urlopen", answer("not json at all"))
    assert _REAL_PROBE().reachable is False


# --- What is actually needed ----------------------------------------------------------

def test_the_four_roles_ask_for_two_models_not_four():
    """Three of the four shipped roles share one model. Counted per role, the setup
    page would have quoted 22 GB for a 9.9 GB download."""
    wanted = preflight.needs()
    assert len(wanted) == 2, [n.model for n in wanted]
    assert sum(len(n.roles) for n in wanted) == 4


def test_the_backup_narrator_alone_never_blocks_a_first_game():
    """It exists for the turns the narrator burns all five attempts on, and a campaign
    that never hits one never calls it. Required, it would make the mandatory download
    9.9 GB instead of 7.4 GB."""
    wanted = {n.model: n for n in preflight.needs()}
    backup = [n for n in wanted.values() if n.roles == ("fallback",)]
    assert backup and backup[0].required is False
    assert [n for n in wanted.values() if n.required], "something must still be required"


def test_a_missing_optional_model_still_reads_as_ready():
    narrator = next(n for n in preflight.needs() if n.required)
    with _probe(reachable=True, installed=(narrator.model,)):
        report = preflight.check()
    assert report.state == "ready" and report.ok
    assert any(not n.present for n in report.needs), "the optional one is still absent"


def test_an_untagged_model_matches_the_tag_ollama_lists_it_under():
    """`settings.MODELS` configures the fallback without a tag; `/api/tags` always
    answers with one. Compared raw, an installed model reads as missing and the player
    is offered a 2.5 GB download of something already on the disk."""
    assert preflight._norm("foo/bar") == "foo/bar:latest"
    assert preflight._norm("foo/bar:latest") == "foo/bar:latest"
    assert preflight._norm("foo/bar:Q8_0") == "foo/bar:Q8_0"
    # A digest-pinned reference still lives under its tag.
    assert preflight._norm("foo/bar@sha256:abc") == "foo/bar:latest"
    # A registry host carries a colon that is not a tag separator.
    assert preflight._norm("host:5000/bar") == "host:5000/bar:latest"


def test_every_shipped_default_has_a_size_to_quote():
    """A player is asked to agree to a download; the number has to be there to agree
    to. Fails deliberately when a default model is changed without its size."""
    for need in preflight.needs():
        assert need.bytes_estimate > 0, (
            f"{need.model} has no entry in preflight.KNOWN_SIZES — a setup page that "
            f"cannot say how big the download is cannot ask for consent to it")


# --- Hosted providers -----------------------------------------------------------------

def test_a_player_on_an_api_key_is_never_told_to_install_ollama():
    """Local is the default and must always be sufficient — it is not mandatory. A
    player who has solved this with a key must not be stopped by a check about a
    program they have no reason to own."""
    hosted = {r: {"provider": "openai", "model": "gpt-4o", "host": "https://x"}
              for r, _l, _w in __import__("play.modelcfg", fromlist=["x"]).ROLES}
    with mock.patch("play.modelcfg.roles", return_value=hosted):
        with _probe(reachable=False, refused=True, why="nothing is listening"):
            report = preflight.check()
    assert report.ok and report.state == "ready"
    assert report.needs == []
    assert len(report.hosted) == 4


# --- Disk ------------------------------------------------------------------------------

def test_no_room_is_said_before_the_download_rather_than_at_ninety_four_percent():
    """A pull that runs out of disk part way leaves a partial blob behind and reports
    a message about the disk rather than about the app having offered a download it
    had no room for."""
    report = preflight.Report(state="missing-models", host="http://localhost:11434",
                              disk_free=3_000_000_000, disk_needed=7_400_000_000)
    assert "free" in preflight.room_for(report)

    roomy = preflight.Report(state="missing-models", host="http://localhost:11434",
                             disk_free=90_000_000_000, disk_needed=7_400_000_000)
    assert preflight.room_for(roomy) == ""


def test_an_unknown_disk_says_nothing_rather_than_inventing_a_number():
    blind = preflight.Report(state="missing-models", host="http://localhost:11434",
                             disk_free=0, disk_needed=7_400_000_000)
    assert preflight.room_for(blind) == ""


def test_disk_and_install_questions_are_only_asked_of_this_machine():
    """The settings page allows pointing a role at Ollama on another box. Telling that
    player their own C: drive is too full would be a warning about the wrong disk."""
    assert preflight.is_local("http://localhost:11434")
    assert preflight.is_local("http://127.0.0.1:11434")
    assert not preflight.is_local("http://192.168.1.40:11434")

    with _probe(reachable=False, refused=True, why="nothing is listening"):
        with mock.patch("play.modelcfg.roles", return_value={
            "narrator": {"provider": "ollama", "model": "m",
                         "host": "http://192.168.1.40:11434"}}):
            report = preflight.check()
    assert report.state == "not-running", "never 'not-installed' about another machine"
    assert report.disk_free == 0


# --- The pull --------------------------------------------------------------------------

class _FakeStream:
    def __init__(self, lines):
        self._lines = [(line + "\n").encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def test_the_pull_streams_progress_and_closes_with_done(monkeypatch):
    frames = [json.dumps(f) for f in [
        {"status": "pulling manifest"},
        {"status": "pulling 1a2b", "total": 1000, "completed": 250},
        {"status": "pulling 1a2b", "total": 1000, "completed": 1000},
        {"status": "success"},
    ]]
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeStream(frames))
    got = list(preflight.pull("m", "http://localhost:11434"))
    assert got[1]["completed"] == 250
    assert got[-1] == {"done": True, "model": "m"}


def test_a_failure_ollama_reports_in_band_is_not_read_as_progress(monkeypatch):
    """Ollama answers a failed pull with HTTP 200 and an `error` key in the stream.
    Read as progress, that is a download that silently stopped moving and a bar that
    sits at 40% forever."""
    frames = [json.dumps({"status": "pulling manifest"}),
              json.dumps({"error": "file does not exist"})]
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeStream(frames))
    got = list(preflight.pull("nope", "http://localhost:11434"))
    assert got[-1] == {"error": "file does not exist"}
    assert not any("done" in f for f in got)


def test_a_dropped_connection_ends_the_stream_with_an_error(monkeypatch):
    """Not an exception out of a generator the view is already streaming: the headers
    have been sent by then and a 500 cannot be delivered, so the page would see the
    body simply stop."""
    import urllib.error

    def die(*a, **k):
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr("urllib.request.urlopen", die)
    got = list(preflight.pull("m", "http://localhost:11434"))
    assert len(got) == 1 and "error" in got[0]


# --- The two doors into play ----------------------------------------------------------
#
# Gated because both lead to a table whose very first act is a model call. Without the
# gate the failure lands one page later, as a red error over a scene that never
# arrived, and the player cannot tell "I have not downloaded the narrator yet" from
# "this app is broken".

def _shut(state="missing-models"):
    """Turn the gate's answer to no, whatever this machine actually has."""
    if state == "missing-models":
        return _probe(reachable=True, installed=())
    return _probe(reachable=False, refused=True, why="nothing is listening")


def test_starting_a_campaign_is_refused_when_no_model_can_answer(client):
    with _shut():
        r = client.post("/api/start",
                        data=json.dumps({"world": "pangrella-campaign",
                                         "source": "pc-borin"}),
                        content_type="application/json")
    assert r.status_code == 409
    body = r.json()
    assert "not downloaded" in body["error"]
    # The size travels with the refusal: a player asked to wait for a download is
    # owed the number before they agree to it.
    assert "GB" in body["error"]
    # And the report itself, so the page can put them in front of the fix rather than
    # in front of a sentence describing it.
    assert body["setup"]["state"] == "missing-models"
    assert body["setup"]["needs"]


def test_resuming_is_refused_too(client):
    with _shut():
        r = client.post("/api/resume", data=json.dumps({"id": "pc-borin"}),
                        content_type="application/json")
    assert r.status_code == 409
    assert r.json()["setup"]["state"] == "missing-models"


def test_the_refusal_names_the_cause_and_not_a_generic_failure(client):
    """Four situations, four fixes. "Something went wrong with the model" would send a
    player to download a 7.4 GB file when what they needed was to start a program that
    was already installed."""
    with _shut("refused"):
        with mock.patch.object(preflight, "ollama_on_disk", return_value=True):
            running = client.post("/api/resume", data=json.dumps({"id": "pc-borin"}),
                                  content_type="application/json").json()
        with mock.patch.object(preflight, "ollama_on_disk", return_value=False):
            absent = client.post("/api/resume", data=json.dumps({"id": "pc-borin"}),
                                 content_type="application/json").json()
    assert "not running" in running["error"]
    assert "not installed" in absent["error"]
    assert running["error"] != absent["error"]


def test_a_wrong_world_is_still_reported_as_a_wrong_world(client):
    """The gate is checked last on purpose. A player who picked a world that cannot be
    played should hear about the world; one HTTP call to Ollama must not stand in
    front of that, and must not relabel it as a model problem."""
    with _shut():
        r = client.post("/api/start",
                        data=json.dumps({"world": "nowhere", "source": "pc-borin"}),
                        content_type="application/json")
    assert r.status_code == 404


def test_nothing_else_in_the_app_is_gated(client):
    """The sheet, the forge, the benches and the whole homebrew side work with no model
    at all. Gating them would be refusing work the app can do."""
    with _shut("refused"):
        assert client.get("/").status_code == 200
        assert client.get("/api/worlds").status_code == 200
        assert client.get("/api/create/options").status_code == 200
        assert client.get("/api/classes/catalogue").status_code == 200


# --- The setup endpoints --------------------------------------------------------------

def test_the_setup_endpoint_tells_the_page_everything_it_needs(client):
    with _probe(reachable=True, installed=()):
        body = client.get("/api/setup").json()
    assert body["state"] == "missing-models" and body["ok"] is False
    assert body["download"].startswith("https://ollama.com")
    assert [n for n in body["needs"] if n["required"]]
    assert all("bytes" in n and "roles" in n for n in body["needs"])


def test_the_pull_endpoint_refuses_a_model_no_role_asked_for(client):
    """Otherwise this is an arbitrary-download button on a localhost port: anything
    that can reach the app could spend the player's disk on any model in the registry.
    """
    with _probe(reachable=True, installed=()):
        r = client.post("/api/setup/pull",
                        data=json.dumps({"model": "evil/enormous-thing"}),
                        content_type="application/json")
    assert r.status_code == 400
    assert "not a model any role" in r.json()["error"]


def test_the_pull_endpoint_streams_ndjson(client, monkeypatch):
    wanted = next(n for n in preflight.needs() if n.required)
    monkeypatch.setattr(preflight, "pull",
                        lambda *a, **k: iter([{"status": "pulling manifest"},
                                              {"done": True, "model": wanted.model}]))
    with _probe(reachable=True, installed=()):
        r = client.post("/api/setup/pull", data=json.dumps({"model": wanted.model}),
                        content_type="application/json")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/x-ndjson"
    lines = [json.loads(x) for x in
             b"".join(r.streaming_content).decode().strip().split("\n")]
    assert lines[0]["status"] == "pulling manifest"
    assert lines[-1]["done"] is True


def test_the_pull_endpoint_accepts_the_untagged_spelling(client, monkeypatch):
    """The player's own settings may carry `foo/bar` where `/api/tags` says
    `foo/bar:latest`. A pull button that 400s on the name the page itself rendered
    would be a dead button with a correct-looking label."""
    wanted = next(n for n in preflight.needs() if n.required)
    bare = wanted.model.rsplit(":", 1)[0]
    monkeypatch.setattr(preflight, "pull", lambda *a, **k: iter([{"done": True}]))
    with _probe(reachable=True, installed=()):
        r = client.post("/api/setup/pull", data=json.dumps({"model": bare}),
                        content_type="application/json")
    assert r.status_code == 200


def test_the_pull_endpoint_will_not_start_when_ollama_is_not_there(client):
    """A stream that opens and immediately errors reads, on the page, as a download
    that started and then broke. A 409 before the stream opens reads as what it is."""
    wanted = next(n for n in preflight.needs() if n.required)
    with _probe(reachable=False, refused=True, why="nothing is listening"):
        r = client.post("/api/setup/pull", data=json.dumps({"model": wanted.model}),
                        content_type="application/json")
    assert r.status_code == 409


def test_the_table_itself_is_the_gate_not_only_the_two_api_doors(client):
    """Found by driving the real UI, not by any test — which is why it is written down.

    `/api/start` and `/api/resume` were gated first, and both were walked straight past.
    The front page's Continue is a plain `<a href="/play/">`: the campaign is already
    current, so there is nothing to resume and no API call is made. That is the
    commonest path into play — a returning player's first click — and it reached a table
    that could not write a scene.

    So the check belongs at the destination every path shares. A bookmark on /play/ is
    the same hole, and this closes that too.
    """
    with _shut():
        r = client.get("/play/")
    assert r.status_code == 302
    assert r["Location"] == "/?setup=1", (
        "the redirect has to name where the fix is; bouncing to the bare shelf leaves "
        "the player looking at the page they just came from with no reason given")


def test_the_table_opens_normally_when_a_model_can_answer(client):
    """The other half, so a gate that refuses everything cannot pass as a working one."""
    assert client.get("/play/").status_code == 200


def test_the_benches_are_reachable_with_no_model_at_all(client):
    """`/craft/` leads to the crafting bench, which needs no model and must not be
    gated: refusing it would be refusing work the app can do perfectly well."""
    with _shut("refused"):
        assert client.get("/craft/").status_code == 200
        assert client.get("/homebrew/classes/").status_code == 200
