"""The roster: characters that outlive campaigns."""
import pytest  # noqa: F401



def test_a_character_remembers_which_world_they_were_made_for(tmp_path, monkeypatch):
    """Measured live: a character created through Fantasia's own page began in
    Pangrella. The choice was dropped at three points — the forge posted no world,
    create_character passed none, and the roster had nowhere to hold one — so
    `new_campaign` filled the gap with the shipped default, silently.

    ROSTER_VERSION is deliberately not bumped: `load` checks it for equality, and a bump
    would vanish every existing character."""
    from play import roster
    from rules.sheet import load_pc

    monkeypatch.setattr(roster, "root", lambda: tmp_path)
    entry = roster.enrol(load_pc("fixtures/pc-kesst.json"),
                         world_source="H:/worlds/fantasia.json")
    back = roster.load(entry.id)
    assert back.world_source == "H:/worlds/fantasia.json"

    # A file written before the field existed still loads, and empty means default.
    import json as _json

    p = roster.path_for(entry.id)
    d = _json.loads(p.read_text(encoding="utf-8"))
    del d["world_source"]
    p.write_text(_json.dumps(d), encoding="utf-8")
    assert roster.load(entry.id).world_source == ""


def test_a_shelved_character_is_played_in_their_own_world():
    """The other half: `switch_to`'s never-played branch called new_campaign with no
    world_source, so even a correctly-recorded character would have begun in the
    default. Source-inspected because a full campaign begin needs a world file on
    disk; the wiring is the fix."""
    import inspect

    from play import campaign

    src = inspect.getsource(campaign.switch_to)
    assert "world_source=entry.world_source or None" in src
