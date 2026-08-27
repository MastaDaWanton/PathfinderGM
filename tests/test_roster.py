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


def test_death_is_a_debt_not_a_wall(tmp_path, settings, monkeypatch, client):
    """The player's own design: "if the character dies they should be fast forwarded
    into the future where some person has paid to resurrect them because they needed
    their strength." Mechanics first, prose second: the raise clears the death
    conditions through the ordinary applicators, moves the world clock at least a
    week, hangs a clockless life debt (state.obligation.life-debt) naming the
    patron, un-ends the campaign, and puts the character back on the roster alive —
    with the epitaph kept, because the death still happened."""
    from play import campaign as campaign_mod, roster, views

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    monkeypatch.setattr(roster, "root", lambda: tmp_path / "roster")
    (tmp_path / "roster").mkdir()
    campaign_mod._LIVE.clear()

    c = campaign_mod.new_campaign("slice", seed=7)
    from rules.sheet import load_pc
    pc = load_pc("fixtures/pc-kesst.json")
    entry = roster.enrol(pc)
    c.character_id = entry.id
    if not c.scene.pc():
        c.scene.add(pc)
    pc = c.scene.pc()
    before_clock = c.scene.clock_minutes
    pc.hp = -100
    pc.apply_hp_state()
    views._end_campaign(c, pc)
    c.save()
    assert c.ended == "died" and roster.load(entry.id).status == roster.DEAD

    r = client.post("/api/resurrect", data="{}", content_type="application/json")
    assert r.status_code == 200, r.content[:300]
    c = campaign_mod.current()
    pc = c.scene.pc()
    assert c.ended == ""
    assert not pc.has_state("state.down.dead")
    assert pc.hp == pc.hp_max
    assert pc.has_state("state.obligation.life-debt")
    assert c.scene.clock_minutes - before_clock >= 8 * 24 * 60
    assert roster.load(entry.id).status == roster.ALIVE

    # Raising the living is refused, not crashed.
    again = client.post("/api/resurrect", data="{}", content_type="application/json")
    assert again.status_code == 409
