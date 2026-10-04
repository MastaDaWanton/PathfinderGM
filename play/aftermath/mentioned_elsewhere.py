"""A person an NPC places at a real place in this settlement becomes a population record:
heard of, not seen — as the beat reader read it (gm/beat_reader.py, the "places" call).

Measured on the 2026-09-28 playtest (item 5.2): the watchman said "The girl in the market
might know where the bigger coins are hidden", and a turn later "She's in the market, near
the well". Nothing wrote her down. When the player went to the market to find her, the
finder searched and missed (`population-miss`), and the beat gave itself to somebody else.

Eric Eve's Epistemology (Inform Recipe Book §5.5) gives a thing two flags, *seen* and
*familiar* — familiar being known about "for other reasons", heard of but not found. The
owner's ruling (Q5, 2026-09-28): a person an NPC places at a real place in THIS settlement
becomes a record, heard of and not seen — never beyond the settlement, and never at a place
the engine does not have (the engine, not the model, owns geography).

**The reader answers who and where; code checks it.** This step used to find "<person>
<in/at/by/near> <place>" with a pattern over the line and carry a "She's in …" to the same
speaker's last person (`phrases_at`, `_PRONOUN_AT`). The reader now names the person in the
speaker's own words (checked to be in that line, and more than a pronoun) and the place
from an enum of this town's own places. Recorded only when the finder holds nobody who
fits, never at the party's own place, with the place's name joined to the words when the
speaker left it off ("a man" at the counting house is recorded as "a man in the counting
house", the words the player will say back to find him).
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 20


def step(ctx) -> list[dict]:
    from gm import beat_reader
    from rules import population

    reading = ctx.attribution
    scene = ctx.scene
    if scene is None or not isinstance(reading, beat_reader.Reading) \
            or not reading.places_read:
        return []
    names = {}
    try:
        names = {p.id: str(p.name) for p in ctx.campaign.engine().places()}
    except Exception:  # noqa: BLE001 — no places to name: the reader's ids stand alone
        pass
    lines = {ln.id: ln for ln in reading.lines}
    rows: list[dict] = []
    for p in reading.placed:
        if p.at == getattr(scene, "at", None):
            continue                       # here: the page's own people, not this
        where = names.get(p.at, "")
        phrase = " ".join(p.words.split())
        phrase = phrase[:1].lower() + phrase[1:]
        if where and beat_reader._norm(where.removeprefix("the ")) not in \
                beat_reader._norm(phrase):
            phrase = f"{phrase} in {where if where.lower().startswith('the ') else 'the ' + where}"
        if population.find(scene, phrase, world=ctx.world, log_miss=False).scope \
                != population.NONE:
            continue
        who = p.said_by
        n = reading.newcomer(who)
        who = (n.ref if n is not None else who) or ""
        ln = lines.get(p.line)
        rec = population.note(scene, phrase, turn=int(ctx.turn or 0), spot=p.at,
                              heard_from=who, hint=ln.words if ln else "")
        if rec.get("seen") is False and not any(r.get("record") == rec["id"] for r in rows):
            rows.append({"kind": "heard-of", "record": rec["id"], "spot": p.at,
                         "from": who})
    return rows
