"""The owner's soundtrack: two looped playlists, calm and battle, that follow the fight.

Added 2026-10-02 from the owner's own tracks. Each test names what it keeps from breaking:
a track named in the player and missing from the folder plays as silence with nothing
said, so the lists and the files are held to each other here.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.test import Client

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "play" / "static"
MUSIC_JS = (STATIC / "js" / "music.js").read_text(encoding="utf-8")


def _lists() -> dict[str, list[str]]:
    out = {}
    for name in ("ambient", "battle"):
        m = re.search(name + r":\s*\[([^\]]*)\]", MUSIC_JS)
        out[name] = re.findall(r'"([a-z0-9-]+)"', m.group(1)) if m else []
    return out


def test_every_track_the_player_names_is_in_the_folder_and_every_file_is_named():
    """Nine calm and five battle tracks. A name with no file would be a silent gap in the
    loop; a file with no name would ship 3 to 7 MB nobody ever hears."""
    lists = _lists()
    assert len(lists["ambient"]) == 9 and len(lists["battle"]) == 5
    for name, ids in lists.items():
        on_disk = sorted(p.stem for p in (STATIC / "audio" / "music" / name).glob("*.mp3"))
        assert sorted(ids) == on_disk, name


def test_a_track_is_served_whole_as_audio():
    """The player fetches each track whole into a blob (Django's static view ignores
    Range, and a stream it cannot range cannot be resumed mid-song). It must arrive as
    audio, every byte of it."""
    path = STATIC / "audio" / "music" / "battle" / "epic-sad-1.mp3"
    r = Client().get("/static/audio/music/battle/epic-sad-1.mp3")
    body = b"".join(r.streaming_content) if r.streaming else r.content
    assert r.status_code == 200 and r["Content-Type"].startswith("audio/")
    assert len(body) == path.stat().st_size


def test_the_music_has_its_own_level_and_switch_in_the_preferences():
    prefs = (STATIC / "js" / "prefs.js").read_text(encoding="utf-8")
    assert '"sound.music": 0.45' in prefs and '"music.on": true' in prefs
    home = (ROOT / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    assert 'key: "sound.music"' in home and 'data-pref="music.on"' in home


def test_the_table_plays_battle_music_in_an_encounter_and_the_calm_after():
    """The soundtrack follows the fight: the table's render hands the scene's own
    `in_encounter` to the player on every draw, and the player waits a few seconds of
    peace before the calm returns, so one turn reading as no encounter cannot flicker it."""
    state = (STATIC / "js" / "table" / "02-state.js").read_text(encoding="utf-8")
    assert 'Music.mode(s && s.scene && s.scene.in_encounter ? "battle" : "ambient")' in state
    assert "BACK_TO_CALM_MS" in MUSIC_JS


def test_every_page_with_music_loads_the_player_and_the_table_has_its_switch():
    for page in ("table.html", "home.html", "craft.html"):
        text = (ROOT / "play" / "templates" / "play" / page).read_text(encoding="utf-8")
        assert "js/music.js" in text, page
    table = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    assert 'id="musictoggle"' in table


_MUSIC_STUB = r"""
const made = [];
class Audio { constructor() { this.paused = true; this.volume = 0; this.dataset = {};
  this.readyState = 4; made.push(this); }
  addEventListener() {} play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; } }
const fetched = [];
const fetch = url => { fetched.push(url);
  return Promise.resolve({ ok: true, blob: () => Promise.resolve({}) }); };
const URL = { createObjectURL: () => "blob:x", revokeObjectURL() {} };
const sessionStorage = { getItem: () => null, setItem() {} };
const setInterval = () => 0, clearInterval = () => {}, setTimeout = () => 0, clearTimeout = () => {};
const document = { currentScript: null };
"""


def _music_in(tmp_path, frame: str, search: str) -> dict:
    """music.js run in node as a page would: `frame` sets up `window` (top or framed),
    `search` is the page's query string. Reports the decks made and the tracks fetched."""
    src = (_MUSIC_STUB + frame + f"\nconst location = {{ search: {json.dumps(search)} }};\n"
           + MUSIC_JS + r"""
    window.Music.start("ambient");
    window.Music.mode("battle");
    setImmediate(() => setImmediate(() => {
      console.log(JSON.stringify({ decks: made.length, playing: made.filter(a => !a.paused).length,
                                   fetched: fetched.length, embedded: !!window.Music.embedded }));
      process.exit(0);
    }));""")
    f = tmp_path / "music_probe.js"
    f.write_text(src, encoding="utf-8")
    done = subprocess.run([shutil.which("node"), str(f)], capture_output=True, text=True,
                          timeout=30)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout.strip().splitlines()[-1])


_TOP = "const window = { addEventListener() {} }; window.self = window; window.top = window;\n"
_FRAMED = ("const window = { addEventListener() {} }; window.self = window;"
           " window.top = { addEventListener() {} };\n")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on this machine")
def test_the_settings_frame_over_the_table_plays_no_music_of_its_own(tmp_path):
    """The owner, 2026-10-27: "The settings menu when you open it on the table plays its own
    music so you have overlapping instrumentation." Measured in the owner's save: with
    Settings open over the table, the top page and the frame each had one <audio> playing,
    the same track ("alone-in-the-garden-3"), the frame 2.7 seconds behind the table
    (13.38 s against 10.69 s), because the frame resumed from the position the table saved.
    music.js is a no-op inside a frame, or on a page opened with `embed=1`; the top page
    still plays."""
    top = _music_in(tmp_path, _TOP, "")
    assert top["decks"] >= 1 and top["fetched"] >= 1 and not top["embedded"], top
    framed = _music_in(tmp_path, _FRAMED, "?tab=settings&embed=1")
    assert framed == {"decks": 0, "playing": 0, "fetched": 0, "embedded": True}, framed
    # Either sign alone is enough: a frame without the flag, and the flag without a frame
    # (the embedded page opened on its own, as the Settings panel's URL can be).
    assert _music_in(tmp_path, _FRAMED, "?tab=settings")["decks"] == 0
    assert _music_in(tmp_path, _TOP, "?tab=settings&embed=1")["decks"] == 0


def test_the_settings_page_still_starts_music_where_it_is_the_top_page():
    """The standalone Settings page (the shelf) keeps its soundtrack; only the frame is
    silenced, and by music.js itself rather than by the page skipping the call, so every
    page that loads the player is covered, not only home.html."""
    home = (ROOT / "play" / "templates" / "play" / "home.html").read_text(encoding="utf-8")
    assert 'window.Music && Music.start("ambient");' in home
    assert "window.self !== window.top" in MUSIC_JS


def test_the_player_bundles_nothing_of_anyone_else_and_runs_no_idle_render_loop():
    """The app ships no third-party JavaScript (scene3d.js's header), and the fade is a
    timer that exists only while a fade runs."""
    assert "import " not in MUSIC_JS and "require(" not in MUSIC_JS
    assert "requestAnimationFrame" not in MUSIC_JS
