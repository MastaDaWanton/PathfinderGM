"""The report a player makes for the developer (`play/report.py`, owner's design 2026-10-08).

Every "never in the zip" rule is pinned here the way it can actually fail: a real data
folder is seeded with the secret key, the API keys, a LAN pass in a request line and the
user's name in every spelling of a path, a real zip is built from it, and every byte of
every member is searched. A test that only asked the redaction function about one string
would have passed Signal Desktop's redaction too, which handled `C:\\Users\\name` and
shipped `file:///C:/Users/name` (signalapp/Signal-Desktop#2869).
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote

import pytest
from django.test import Client

from pathfindergm import redact
from play import report

ROOT = Path(__file__).resolve().parent.parent

SECRET_KEY = "seeded-secret-" + "Q" * 60
OPENAI = "sk-proj-SEEDEDopenaiKEY0123456789abcdef"
UNSHAPED = "unshaped-key-NOBODYS-PATTERN-4471"     # a key no shape regex knows
LEAKED = "sk-ant-api03-LEAKEDinAnERRORmessage0123456789"
PASS = "PASSWORD99"
NAME = "Seededname"
HOST_PASSWORD = "hunter2"


def _home() -> str:
    return str(Path.home())


@pytest.fixture
def seeded(tmp_path, settings, monkeypatch):
    """A data folder holding everything a report must never carry."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    camps = tmp_path / "campaigns"
    camps.mkdir()
    (tmp_path / "secret.key").write_text(SECRET_KEY, encoding="utf-8")
    (tmp_path / "models.json").write_text(json.dumps({
        "roles": {"narrator": {"provider": "ollama", "model": "llama3.1:8b",
                               "host": f"http://bob:{HOST_PASSWORD}@10.0.0.5:11434/x?y=1"}},
        "keys": {"openai": OPENAI, "mistral": UNSHAPED},
    }), encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "pathfindergm.log").write_text("\n".join([
        "=== launch 2026-10-08 10:00:00 ===",
        f'"GET /?k={PASS} HTTP/1.1" 302 0',
        f"  your data C:\\Users\\{NAME}\\AppData\\Local\\PathfinderGM",
        f"  loaded file:///C:/Users/{NAME}/AppData/Local/Programs/pathfindergm/app.asar",
        f"  json said \"C:\\\\Users\\\\{NAME}\\\\Downloads\\\\world.json\"",
        f"  url said http://x/open?path=C%3A%5CUsers%5C{NAME}%5Cworld.json",
        f"  error: 401 from hosted model, Authorization: Bearer {LEAKED}",
        f"  the client was given {OPENAI} and {UNSHAPED}",
        f"  secret {SECRET_KEY}",
        f"  home {_home()}\\campaigns",
        "  installed C:\\Program Files\\Pathfinder GM",
    ]), encoding="utf-8")
    (logs / "update.log").write_text(
        f"2026-10-08T10:00:00Z [update] info: cache C:/Users/{NAME}/AppData/Local/x\n",
        encoding="utf-8")
    beats = [{"who": "gm" if i % 2 else "player", "text": f"beat number {i}"}
             for i in range(100)]
    beats[-1]["text"] = f"The guard reads the note: ?k={PASS}. A mark on the wall."
    save = {"save_version": 2, "id": "seeded",
            "world_source": f"C:\\Users\\{NAME}\\Downloads\\world.json",
            "transcript": beats,
            "turn_log": [{"kind": "turn", "n": i, "roll": 7 + i} for i in range(12)]}
    (camps / "seeded.json").write_text(json.dumps(save), encoding="utf-8")
    (camps / "active.txt").write_text("seeded", encoding="utf-8")
    from pathfindergm import lan

    monkeypatch.setattr(lan, "_token", PASS)
    return tmp_path


def _members(data: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n).decode("utf-8") for n in zf.namelist()}


def _assert_clean(blobs: dict[str, str]) -> None:
    for name, text in blobs.items():
        assert "secret.key" not in name and "models.json" not in name, name
        for bad in (SECRET_KEY, OPENAI, UNSHAPED, LEAKED, PASS, HOST_PASSWORD):
            assert bad not in text, f"{name} carried {bad!r}"
        assert NAME.lower() not in text.lower(), f"{name} carried the user name"
        home = _home()
        for spelling in (home, home.replace("\\", "/"), home.replace("\\", "\\\\")):
            assert spelling.lower() not in text.lower(), f"{name} carried {spelling!r}"


def test_a_report_zip_built_from_a_seeded_data_folder_carries_no_secret(seeded):
    """The owner's never-list, every one at once: secret.key, models.json, the API keys
    (saved ones by value, a leaked one by shape), the LAN pass in a request line and in
    the save, and the Windows user name in a backslash path, a `file:///` URL, a JSON
    doubled-backslash string and a percent-encoded URL."""
    blobs = _members(report.build("it broke at the gate", probe=False))
    _assert_clean(blobs)
    log = blobs["logs/pathfindergm.log"]
    # Masked, not deleted: the developer still sees that a pass arrived and where the
    # data folder was.
    assert "?k=(the pass)" in log
    assert "C:\\Users\\<user>\\AppData" in log
    assert "file:///C:/Users/<user>/AppData" in log
    assert "Bearer <api key>" in log
    assert "C:\\Program Files\\Pathfinder GM" in log


def test_the_save_is_in_by_default_and_out_when_unticked(seeded):
    """Owner, 2026-10-08: "included by default so we can see and track the full
    context", with a box the player may untick."""
    with_save = _members(report.build("", probe=False))
    assert "campaign/save/seeded.json" in with_save
    assert json.loads(with_save["campaign/save/seeded.json"])["id"] == "seeded"
    without = _members(report.build("", include_save=False, probe=False))
    assert not any(n.startswith("campaign/save/") for n in without)
    manifest = json.loads(without["manifest.json"])
    assert manifest["campaign"]["save_included"] is False
    # The turn log and the readable tail ride along either way.
    assert "campaign/turn-log.json" in without
    assert "campaign/transcript-tail.txt" in without


def test_the_saved_game_is_still_json_after_its_secrets_come_out(seeded):
    """The first pass-masking pattern (`[^&\\s]+`) ate the closing quote of a JSON string
    along with the pass; inside a save that is a file the developer cannot open."""
    blobs = _members(report.build("", probe=False))
    save = json.loads(blobs["campaign/save/seeded.json"])
    assert save["transcript"][-1]["text"].endswith("A mark on the wall.")
    assert save["world_source"] == "C:\\Users\\<user>\\Downloads\\world.json"


def test_the_transcript_tail_is_the_end_of_the_game_and_the_turn_log_is_whole(seeded):
    blobs = _members(report.build("", probe=False))
    tail = blobs["campaign/transcript-tail.txt"]
    assert "beat number 99" not in tail             # the last beat's text was replaced
    assert "beat number 98" in tail and "beat number 20" in tail
    assert "beat number 19" not in tail             # 100 beats, the last 80
    assert len(json.loads(blobs["campaign/turn-log.json"])) == 12


def test_the_manifest_names_the_models_and_never_their_keys_or_credentials(seeded):
    """Names only: `llama3.1:8b` per role, which providers have a key, and the host with
    its `user:password@`, path and query taken off."""
    manifest = json.loads(_members(report.build("", probe=False))["manifest.json"])
    narrator = manifest["models"]["roles"]["narrator"]
    assert narrator["model"] == "llama3.1:8b"
    assert narrator["host"] == "http://10.0.0.5:11434"
    assert manifest["models"]["providers_with_a_key"] == ["mistral", "openai"]
    for key in ("app", "system", "shell", "campaign", "files", "left_out_on_purpose"):
        assert key in manifest
    assert manifest["system"]["python"].startswith("CPython") or manifest["system"]["python"]
    assert manifest["campaign"]["turns_logged"] == 12


def test_the_release_number_comes_from_the_shell(seeded, monkeypatch):
    """The backend exe has no copy of package.json; the shell hands it `app.getVersion()`
    (`electron/main.js`, `backendEnv`)."""
    monkeypatch.setenv("PATHFINDER_GM_APP_VERSION", "9.8.7")
    monkeypatch.setenv("PATHFINDER_GM_ELECTRON_VERSION", "33.2.1")
    manifest = json.loads(_members(report.build("", probe=False))["manifest.json"])
    assert manifest["app"]["version"] == "9.8.7"
    assert manifest["shell"] == {"kind": "desktop app", "electron": "33.2.1",
                                 "chrome": manifest["shell"]["chrome"]}


def test_the_players_words_are_in_the_zip_scrubbed_too(seeded):
    """A player who pastes a log line into the box pastes its secrets with it."""
    blobs = _members(report.build(f"I pasted this: {OPENAI} from C:\\Users\\{NAME}",
                                  probe=False, note="The model has stopped answering."))
    words = blobs["what-went-wrong.txt"]
    assert "I pasted this:" in words and "The model has stopped answering." in words
    _assert_clean(blobs)


def test_a_fresh_install_still_makes_a_report(tmp_path, settings):
    """No campaign, no logs: the report still carries the manifest and the words."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    blobs = _members(report.build("nothing works", probe=False))
    assert set(blobs) == {"manifest.json", "what-went-wrong.txt"}
    assert json.loads(blobs["manifest.json"])["campaign"] == {"played": False}


def test_what_the_player_is_shown_is_what_goes_in(seeded):
    """The listing and the zip come from one function, so the list the player reads
    before saving cannot drift from the file they get."""
    listed = report.listing()
    names = [f["name"] for f in listed["files"]]
    built = list(_members(report.build("", probe=False)))
    assert names == built
    assert listed["has_save"] is True
    save_row = next(f for f in listed["files"] if f["kind"] == "save")
    assert save_row["bytes"] > 0


# --- the routes -------------------------------------------------------------------

def test_the_zip_comes_back_as_an_attachment_the_shell_recognises(seeded):
    """`electron/main.js` decides Downloads-and-show-in-folder by the file name alone. A
    name the shell's pattern did not match would fall back to Chromium's Save dialog."""
    resp = Client().post("/api/report", json.dumps({"description": "x"}),
                         content_type="application/json")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/zip"
    assert "attachment" in resp["Content-Disposition"]
    name = resp["X-Report-Name"]
    main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
    pattern = re.search(r"const REPORT_NAME = /(.+)/;", main).group(1)
    assert re.fullmatch(pattern, name), (pattern, name)
    assert re.fullmatch(pattern, name.replace(".zip", "-3.zip"))
    blobs = _members(b"".join(resp.streaming_content))
    assert "campaign/save/seeded.json" in blobs
    _assert_clean(blobs)


def test_an_unticked_box_reaches_the_server_as_unticked(seeded):
    resp = Client().post("/api/report", json.dumps({"include_save": False}),
                         content_type="application/json")
    blobs = _members(b"".join(resp.streaming_content))
    assert not any(n.startswith("campaign/save/") for n in blobs)


def test_a_phone_on_the_wifi_is_not_handed_the_logs(seeded):
    """The pass lets a phone play; it does not make the phone the desktop's owner."""
    from pathfindergm import lan

    assert lan.token() == PASS
    resp = Client().post("/api/report", "{}", content_type="application/json",
                         REMOTE_ADDR="192.168.1.20")
    assert resp.status_code == 403


def test_making_a_report_waits_for_no_turn_and_moves_no_revision(seeded):
    """Wanted most while a turn is stuck on a stalled model, which is when the game lock
    is held; and a POST under the lock would bump the revision and send every device to
    re-fetch a game nothing changed."""
    from play import concurrency

    assert any("/api/report".startswith(p) for p in concurrency.EXEMPT)
    before = concurrency.revision()
    Client().post("/api/report", "{}", content_type="application/json")
    assert concurrency.revision() == before


# --- sending it -------------------------------------------------------------------

def test_the_issue_and_the_email_stay_under_what_their_handlers_accept(seeded):
    """GitHub answers 414 past about 8 KB; Windows mail handlers drop a mailto past about
    2,000 characters. Twenty thousand characters of description must fit both."""
    words = "The orc would not move. " * 900
    found = report.links(words, "pathfindergm-report-20261008-101010.zip")
    assert len(found["github"]) <= report.GITHUB_URL_LIMIT
    assert len(found["mailto"]) <= report.MAILTO_LIMIT
    assert found["github"].startswith(
        "https://github.com/MastaDaWanton/PathfinderGM/issues/new?title=")
    assert found["mailto"].startswith("mailto:mastadawanton@gmail.com?subject=")
    body = unquote(found["mailto"].split("&body=", 1)[1])
    assert "cut short here" in body
    assert "Attach pathfindergm-report-20261008-101010.zip" in body
    issue = unquote(found["github"])
    assert "Drag it into this box" in issue and "Version:" in issue


def test_the_links_carry_no_secret_the_player_pasted(seeded):
    found = report.links(f"see {OPENAI} and ?k={PASS} at C:/Users/{NAME}/x", "r.zip")
    for url in found.values():
        text = unquote(url)
        assert OPENAI not in text and PASS not in text and NAME not in text


def test_the_links_route_answers_with_both(seeded):
    resp = Client().post("/api/report/links",
                         json.dumps({"description": "hi", "zip": "..\\..\\evil.zip"}),
                         content_type="application/json")
    d = resp.json()
    assert d["github"].startswith("https://github.com/") and d["mailto"].startswith("mailto:")
    assert d["zip"] == "evil.zip"


# --- the desktop shell's door ------------------------------------------------------

def test_the_startup_failure_box_builds_the_same_report(seeded, tmp_path, monkeypatch, capsys):
    """`desktop.py --report`: the shell's "Make a report" when the game never started.
    One implementation of what goes in and what comes out, run from a second door."""
    import desktop

    monkeypatch.setenv("PATHFINDER_GM_REPORT_NOTE",
                       f"The game server stopped unexpectedly (exit 1). C:\\Users\\{NAME}\\x")
    out = tmp_path / "Downloads"
    assert desktop._report_only(["--report", "--report-dir", str(out)]) == 0
    line = [ln for ln in capsys.readouterr().out.splitlines()
            if ln.startswith(desktop.REPORT_LINE)][-1]
    said = json.loads(line[len(desktop.REPORT_LINE):])
    path = Path(said["path"])
    assert path.parent == out and path.is_file()
    blobs = _members(path.read_bytes())
    assert "stopped unexpectedly" in blobs["what-went-wrong.txt"]
    _assert_clean(blobs)
    assert said["mailto"].startswith("mailto:") and said["github"].startswith("https://")
    # A second report in the same second does not overwrite the first.
    again = report.save_to(out, "", True, probe=False)
    assert again != path and again.is_file()


def test_the_log_and_the_report_mask_the_pass_with_one_rule():
    """`desktop._without_pass` and the report's scrub were two copies of one regex; now
    there is one (`pathfindergm/redact.py`)."""
    import desktop

    address = f"http://192.168.1.5:50000/?k={PASS}"
    assert desktop._without_pass(address) == redact.without_pass(address)
    assert PASS not in desktop._without_pass(address)


def test_a_word_that_is_also_the_users_name_survives_outside_a_path():
    """Paths, not words: a player called Mark keeps "a mark on the wall"."""
    text = "Mark found a mark on the wall. C:\\Users\\Mark\\x and /Users/Mark/y"
    out = redact.paths_without_user(text)
    assert out.startswith("Mark found a mark on the wall.")
    assert "C:\\Users\\<user>\\x" in out and "/Users/<user>/y" in out


# --- the pages ---------------------------------------------------------------------

def test_the_settings_page_offers_the_report_with_the_save_ticked():
    page = (ROOT / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    assert "Make a report for the developer" in page
    assert re.search(r'id="reportsave" checked', page)
    assert "Open a GitHub issue" in page and "Email it" in page
    # External links leave through the shell's window-open handler, never this window.
    assert re.search(r'id="reportgithub" target="_blank"', page)
    block = page[page.index("/* --- Make a report for the developer"):
                 page.index("async function saveModelSettings")]
    # The owner's rule for UI copy: no em-dashes.
    assert "\u2014" not in block


def test_a_stalled_model_offers_a_report_beside_its_sentence():
    """The owner asked for the button on "the model stopped answering" (ModelStalled)."""
    from gm.client import ModelStalled, ModelUnavailable
    from play.views import _model_down

    stalled = json.loads(_model_down(ModelStalled("stopped")).content)
    assert stalled["report"] is True
    assert "report" not in json.loads(_model_down(ModelUnavailable("down")).content)
    js = (ROOT / "play" / "static" / "js" / "table" / "04-combat-and-turns.js").read_text(
        encoding="utf-8")
    assert "showStalled" in js and "showSettingsAt(\"report\"" in js
    state = (ROOT / "play" / "static" / "js" / "table" / "02-state.js").read_text(
        encoding="utf-8")
    assert "if (data.report) e.report = true;" in state


def test_the_shell_saves_reports_to_downloads_and_shows_them_without_a_bridge():
    """No preload, no IPC: the page keeps no Node and no new ability. The shell picks the
    report download out by name and does the rest itself."""
    main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
    assert "session.on('will-download'" in main
    assert "item.setSavePath(target)" in main
    assert "shell.showItemInFolder(target)" in main
    assert "app.getPath('downloads')" in main
    assert "preload:" not in main and "contextBridge" not in main and "ipcMain" not in main
    assert "nodeIntegration: false" in main and "contextIsolation: true" in main
    assert "PATHFINDER_GM_APP_VERSION: app.getVersion()" in main
    assert "'Make a report'" in main and "'--report'" in main
