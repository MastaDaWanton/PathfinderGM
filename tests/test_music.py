"""The owner's soundtrack: two looped playlists, calm and battle, that follow the fight.

Added 2026-10-02 from the owner's own tracks. Each test names what it keeps from breaking:
a track named in the player and missing from the folder plays as silence with nothing
said, so the lists and the files are held to each other here.
"""
from __future__ import annotations

import re
from pathlib import Path

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


def test_the_player_bundles_nothing_of_anyone_else_and_runs_no_idle_render_loop():
    """The app ships no third-party JavaScript (scene3d.js's header), and the fade is a
    timer that exists only while a fade runs."""
    assert "import " not in MUSIC_JS and "require(" not in MUSIC_JS
    assert "requestAnimationFrame" not in MUSIC_JS
